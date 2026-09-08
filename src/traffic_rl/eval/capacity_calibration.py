"""Validation-only Hai Chau capacity calibration utilities.

The module is importable outside the CityFlow container. Simulator imports are
kept inside the default executor so preparation and verification remain host
safe. Python 3.6 compatible.
"""

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

import yaml


LADDER_SCALES = (0.25, 0.30, 0.35)
CODE_PATHS = (
    "scripts/calibrate_haichau_capacity.py",
    "src/traffic_rl/eval/capacity_calibration.py",
)
GATE_POLICY = {
    "snapshot_conservation": True,
    "at_3600": {"unreleased": 0, "removed": 0},
    "normal": {
        "minimum_insertion_rate": 0.95,
        "maximum_pending_rate": 0.05,
        "minimum_free_flow_eligible_completion": 0.70,
    },
    "drain_5400": {
        "minimum_completion_rate": 0.90,
        "maximum_pending_rate": 0.01,
    },
    "drain_7200": {
        "minimum_completion_rate": 0.98,
        "maximum_pending_rate": 0.01,
    },
    "pm_peak": {"minimum_insertion_rate": 0.90},
    "aggregate": {
        "pm_queue_integral_greater_than_normal": True,
        "pm_completion_less_than_normal": True,
    },
}


def _positive_finite(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be finite and positive" % label)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("%s must be finite and positive" % label)
    return number


def scheduled_departures(row):
    """Return CityFlow's number of requested departures for one flow row."""
    start = float(row["startTime"])
    end = float(row["endTime"])
    interval = _positive_finite(row["interval"], "flow interval")
    if start > end:
        return 0
    return 1 + int(math.floor((end - start) / interval))


def _profile_bin(row, profile_bins):
    start = int(row["startTime"])
    end = int(row["endTime"])
    matches = [item for item in profile_bins
               if int(item["start"]) <= start < int(item["end"])
               and end == int(item["end"]) - 1]
    if len(matches) != 1:
        raise ValueError("flow row does not match exactly one temporal profile bin")
    return matches[0]


def scale_flow(flow, scale, profile_bins):
    """Scale departure rates while retaining stream routes and temporal bins."""
    factor = _positive_finite(scale, "scale")
    result = []
    for source in flow:
        row = copy.deepcopy(source)
        profile_bin = _profile_bin(row, profile_bins)
        old_interval = _positive_finite(row["interval"], "flow interval")
        new_interval = old_interval / factor
        bin_start = int(profile_bin["start"])
        relative_offset = float(row["startTime"] - bin_start) / old_interval
        new_start = bin_start + int(round(relative_offset * new_interval))
        new_start = min(new_start, int(profile_bin["end"]) - 1)
        row["interval"] = new_interval
        row["startTime"] = new_start
        result.append(row)
    return result


def _road_length(road):
    points = road.get("points", [])
    if len(points) < 2:
        raise ValueError("road geometry requires at least two points")
    return sum(math.hypot(float(end["x"]) - float(start["x"]),
                          float(end["y"]) - float(start["y"]))
               for start, end in zip(points, points[1:]))


def _route_free_flow_seconds(row, roads):
    vehicle_speed = _positive_finite(
        row.get("vehicle", {}).get("maxSpeed"), "vehicle maxSpeed")
    seconds = 0.0
    for road_id in row.get("route", []):
        if road_id not in roads:
            raise ValueError("flow route references unknown road: %s" % road_id)
        road = roads[road_id]
        lane_speeds = [_positive_finite(lane.get("maxSpeed"), "lane maxSpeed")
                       for lane in road.get("lanes", [])]
        if not lane_speeds:
            raise ValueError("route road has no lanes: %s" % road_id)
        seconds += _road_length(road) / min([vehicle_speed] + lane_speeds)
    return seconds


def free_flow_eligible_by_snapshot(flow, roadnet_payload, snapshot_seconds):
    """Count scheduled vehicles able to finish by each snapshot at free flow."""
    roads = dict((road["id"], road) for road in roadnet_payload.get("roads", []))
    snapshots = sorted(set(int(value) for value in snapshot_seconds))
    if any(value <= 0 for value in snapshots):
        raise ValueError("snapshot seconds must be positive")
    eligible = dict((str(value), 0) for value in snapshots)
    for row in flow:
        travel_seconds = _route_free_flow_seconds(row, roads)
        interval = float(row["interval"])
        start = float(row["startTime"])
        for index in range(scheduled_departures(row)):
            finish = start + index * interval + travel_seconds
            for snapshot in snapshots:
                if finish <= snapshot:
                    eligible[str(snapshot)] += 1
    return eligible


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _project_path(project_root, path, label, must_exist=True):
    root = Path(project_root).resolve()
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("%s path escapes project root" % label)
    if must_exist and not candidate.is_file():
        raise ValueError("%s artifact is missing" % label)
    return candidate


def _verified_file(project_root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is required" % label)
    path = _project_path(project_root, record.get("path", ""), label)
    if _sha256(path) != record.get("sha256"):
        raise ValueError("%s sha256 mismatch" % label)
    return path


def _relative(project_root, path):
    return str(Path(path).resolve().relative_to(Path(project_root).resolve()))


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_immutable_json(path, value, label):
    path = Path(path)
    encoded = _json_bytes(value)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("refusing to change existing %s" % label)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def _write_immutable_bytes(path, encoded, label):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("refusing to change existing %s" % label)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def _git_commit(project_root):
    try:
        value = subprocess.check_output(
            ["git", "-C", str(Path(project_root).resolve()), "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT).decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("capacity calibration requires a git commit")
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("capacity calibration git commit is invalid")
    return value


def _load_json(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except ValueError:
        raise ValueError("%s is not valid JSON" % label)
    return value


def _validation_cases(manifest):
    cases = manifest.get("cases", [])
    selected = [case for case in cases if case.get("split") == "validation"]
    by_id = dict((case.get("case_id"), case) for case in selected)
    if len(by_id) != len(selected):
        raise ValueError("validation case IDs must be unique")
    expected = set("validation_%s_demand%d" % (scenario, seed)
                   for scenario in ("normal", "am_peak", "pm_peak")
                   for seed in (31, 32))
    if set(by_id) != expected:
        raise ValueError("manifest must contain exactly six registered validation cases")
    return by_id


def _chosen_scales(stage, chosen_scales):
    if stage != "stage-d":
        if chosen_scales not in (None, [], ()):
            raise ValueError("chosen scales are only valid for stage-d")
        return []
    values = [] if chosen_scales is None else [float(value) for value in chosen_scales]
    if (not values or len(values) != len(set(values))
            or any(value not in LADDER_SCALES for value in values)):
        raise ValueError("chosen scales must be unique registered ladder values")
    return sorted(values)


def _stage_requests(stage, cases, chosen_scales, drain_horizon):
    if stage == "scale1":
        if drain_horizon not in (5400, 7200):
            raise ValueError("drain horizon must be 5400 or 7200")
        return [
            (cases["validation_normal_demand31"], "fixed_time_30", 1.0, 3600),
            (cases["validation_normal_demand32"], "fixed_time_30", 1.0, 3600),
            (cases["validation_normal_demand31"], "fixed_time_30", 1.0,
             int(drain_horizon)),
        ]
    if stage == "ladder":
        case = cases["validation_normal_demand31"]
        return [(case, "fixed_time_30", scale, 3600)
                for scale in LADDER_SCALES]
    if stage == "stage-d":
        ordered = [cases["validation_%s_demand%d" % (scenario, seed)]
                   for scenario in ("normal", "am_peak", "pm_peak")
                   for seed in (31, 32)]
        return [(case, controller, scale, 3600)
                for scale in chosen_scales
                for controller in ("fixed_time_30", "max_pressure_masked_v2")
                for case in ordered]
    raise ValueError("unknown calibration stage: %s" % stage)


def _scale_token(scale):
    return ("%.2f" % float(scale)).replace(".", "p")


def _source_case_flow(project_root, case, route_count):
    # This helper is called only after `_validation_cases` and stage selection.
    record = {"path": case.get("flow_path"), "sha256": case.get("flow_sha256")}
    path = _verified_file(project_root, record, "selected validation flow")
    flow = _load_json(path, "selected validation flow")
    if not isinstance(flow, list) or len(flow) != int(case.get("flow_streams", -1)):
        raise ValueError("selected validation flow stream count mismatch")
    bins = case.get("temporal_profile", [])
    counts = dict((int(item["start"]), 0) for item in bins)
    for row in flow:
        profile_bin = _profile_bin(row, bins)
        counts[int(profile_bin["start"])] += 1
    if (len(flow) != int(route_count) * len(bins)
            or any(count != int(route_count) for count in counts.values())):
        raise ValueError("selected validation flow stream count per bin mismatch")
    return flow


def prepare_campaign(project_root, manifest_path, config_path, output_dir,
                     stage, chosen_scales=None, drain_horizon=5400):
    """Materialize one immutable diagnostic stage without importing CityFlow."""
    root = Path(project_root).resolve()
    manifest_path = _project_path(root, manifest_path, "source manifest")
    config_path = _project_path(root, config_path, "training config")
    output = _project_path(root, output_dir, "output", must_exist=False)
    if "diagnostics" not in output.relative_to(root).parts:
        raise ValueError("capacity calibration output must be under diagnostics")
    manifest = _load_json(manifest_path, "source manifest")
    if manifest.get("protocol_version") != 2:
        raise ValueError("source manifest protocol_version must be 2")
    cases = _validation_cases(manifest)
    scales = _chosen_scales(stage, chosen_scales)
    requests = _stage_requests(stage, cases, scales, int(drain_horizon))

    generator_path = _verified_file(root, {
        "path": manifest.get("generator_config_path"),
        "sha256": manifest.get("generator_config_sha256")}, "generator config")
    network_path = _verified_file(root, manifest.get("network"), "network")
    phase_path = _verified_file(root, manifest.get("phase_contract"), "phase contract")
    roadnet_payload = _load_json(network_path, "network")
    try:
        generator = yaml.safe_load(generator_path.read_text()) or {}
        training = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError:
        raise ValueError("calibration config is not valid YAML")
    route_count = generator.get("route_count")
    if (isinstance(route_count, bool) or not isinstance(route_count, int)
            or route_count <= 0):
        raise ValueError("generator route_count must be a positive integer")
    reward = training.get("reward", {})
    required_reward = ("queue_weight", "downstream_block_weight", "switch_penalty")
    if any(field not in reward for field in required_reward):
        raise ValueError("training reward config is incomplete")

    code_sha256 = {}
    for relative in CODE_PATHS:
        code_sha256[relative] = _sha256(_project_path(root, relative, "calibration code"))
    runtime = manifest.get("runtime", {})
    runtime_fields = ("base_image_digest", "derived_image_tag", "platform")
    if any(not runtime.get(field) for field in runtime_fields):
        raise ValueError("source runtime binding is incomplete")
    runtime_dockerfile = _verified_file(
        root, runtime.get("dockerfile"), "runtime Dockerfile")
    runtime_binding = dict((field, runtime[field]) for field in runtime_fields)
    runtime_binding["dockerfile"] = {
        "path": _relative(root, runtime_dockerfile),
        "sha256": _sha256(runtime_dockerfile),
    }
    binding = {
        "source_manifest_path": _relative(root, manifest_path),
        "source_manifest_sha256": _sha256(manifest_path),
        "training_config_path": _relative(root, config_path),
        "training_config_sha256": _sha256(config_path),
        "generator_config_path": _relative(root, generator_path),
        "generator_config_sha256": _sha256(generator_path),
        "network_path": _relative(root, network_path),
        "network_sha256": _sha256(network_path),
        "phase_contract_path": _relative(root, phase_path),
        "phase_contract_sha256": _sha256(phase_path),
        "code_commit": _git_commit(root),
        "code_sha256": code_sha256,
        "runtime": runtime_binding,
        "gate_policy": copy.deepcopy(GATE_POLICY),
    }

    runs = []
    for case, controller, scale, horizon in requests:
        source_flow = _source_case_flow(root, case, route_count)
        scaled_flow = scale_flow(source_flow, scale, case["temporal_profile"])
        run_id = "%s__%s__%s__s%s__h%d" % (
            stage, case["case_id"], controller, _scale_token(scale), horizon)
        run_dir = output / "runs" / run_id
        demand_path = run_dir / "flow.json"
        demand_bytes = _json_bytes(scaled_flow)
        _write_immutable_bytes(demand_path, demand_bytes, "scaled validation flow")
        snapshots = list(range(300, horizon + 1, 300))
        if horizon not in snapshots:
            snapshots.append(horizon)
        eligible = free_flow_eligible_by_snapshot(
            scaled_flow, roadnet_payload, snapshots)
        run_payload = {
            "schema_version": 1,
            "evidence_namespace": "haichau_capacity_calibration_diagnostic",
            "eligible_for_release": False,
            "eligible_for_test_evaluation": False,
            "stage": stage,
            "run_id": run_id,
            "case_id": case["case_id"],
            "split": "validation",
            "scenario": case["scenario"],
            "demand_seed": int(case["demand_seed"]),
            "simulator_seed": int(case["sim_seed"]),
            "controller_id": controller,
            "fixed_green_duration": 30 if controller == "fixed_time_30" else None,
            "controller_version": ("mask_aware_queue_pressure_v2"
                                   if controller == "max_pressure_masked_v2"
                                   else "shared_nominal_fixed_time_v1"),
            "scale": float(scale),
            "injection_horizon_seconds": 3600,
            "horizon_steps": int(horizon),
            "snapshot_interval_seconds": 300,
            "source_flow_path": case["flow_path"],
            "source_flow_sha256": case["flow_sha256"],
            "demand_path": _relative(root, demand_path),
            "demand_sha256": hashlib.sha256(demand_bytes).hexdigest(),
            "scheduled_vehicles": sum(scheduled_departures(row)
                                      for row in scaled_flow),
            "free_flow_eligible_by_snapshot": eligible,
            "network_path": binding["network_path"],
            "network_sha256": binding["network_sha256"],
            "phase_contract_path": binding["phase_contract_path"],
            "phase_contract_sha256": binding["phase_contract_sha256"],
            "controlled_signals": int(manifest["network"]["controlled_signals"]),
            "agent_ids": list(manifest["network"]["agent_ids"]),
            "simulation": copy.deepcopy(manifest["simulation"]),
            "normalization": copy.deepcopy(manifest["preprocessing"]),
            "reward": dict((field, float(reward[field])) for field in required_reward),
            "code_commit": binding["code_commit"],
            "code_sha256": copy.deepcopy(code_sha256),
            "runtime": copy.deepcopy(runtime_binding),
            "gate_policy": copy.deepcopy(GATE_POLICY),
        }
        run_manifest_path = run_dir / "run-manifest.json"
        _write_immutable_json(run_manifest_path, run_payload, "run manifest")
        run_record = copy.deepcopy(run_payload)
        run_record["run_manifest_path"] = _relative(root, run_manifest_path)
        run_record["run_manifest_sha256"] = _sha256(run_manifest_path)
        runs.append(run_record)

    campaign = {
        "schema_version": 1,
        "evidence_namespace": "haichau_capacity_calibration_diagnostic",
        "eligible_for_release": False,
        "eligible_for_test_evaluation": False,
        "stage": stage,
        "chosen_scales": scales,
        "drain_horizon": int(drain_horizon) if stage == "scale1" else None,
        "binding": binding,
        "runs": runs,
    }
    campaign["campaign_identity_sha256"] = _canonical_sha256(campaign)
    _write_immutable_json(
        output / "campaign-manifest.json", campaign, "campaign manifest")
    return campaign


def rollout_with_snapshots(env, controller, snapshot_interval=300):
    """Run one controller and retain cumulative metric snapshots."""
    interval = int(_positive_finite(snapshot_interval, "snapshot interval"))
    observations = env.reset()
    controller.reset()
    done = False
    info = None
    snapshots = []
    next_snapshot = interval
    while not done:
        actions = controller.act({
            "observations": observations,
            "waiting_counts": env.current_waiting_counts(),
            "action_masks": env.action_masks(),
        })
        observations, _, done, info = env.step(actions)
        step = int(info["step"])
        if step > next_snapshot:
            raise ValueError("rollout skipped an exact snapshot step")
        if step >= next_snapshot or done:
            metrics = copy.deepcopy(info.get("network_metrics"))
            if not isinstance(metrics, dict):
                raise ValueError("network metrics are required at every snapshot")
            snapshots.append({"step": step, "metrics": metrics})
            while next_snapshot <= step:
                next_snapshot += interval
    if info is None:
        raise ValueError("calibration rollout produced no steps")
    terminal = copy.deepcopy(info.get("network_metrics"))
    if not isinstance(terminal, dict):
        raise ValueError("calibration terminal network metrics are required")
    return terminal, snapshots


def _accounting(metrics, scheduled):
    fields = ("scheduled", "due", "unreleased", "inserted", "departed",
              "arrived", "running", "pending", "removed")
    values = {}
    for field in fields:
        raw = metrics.get(field)
        if isinstance(raw, bool):
            raise ValueError("accounting counters must be non-negative integers")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError("accounting counters must be non-negative integers")
        if value < 0 or value != raw:
            raise ValueError("accounting counters must be non-negative integers")
        values[field] = value
    if values["scheduled"] != int(scheduled):
        raise ValueError("snapshot scheduled count differs from run")
    if values["departed"] != values["inserted"]:
        raise ValueError("inserted must equal departed")
    if values["scheduled"] != values["due"] + values["unreleased"]:
        raise ValueError("scheduled = due + unreleased is required")
    if values["due"] != values["inserted"] + values["pending"]:
        raise ValueError("due = inserted + pending is required")
    if values["inserted"] != (values["arrived"] + values["running"]
                              + values["removed"]):
        raise ValueError("inserted = arrived + running + removed is required")
    return values


def _check(value, operator, threshold):
    passed = value >= threshold if operator == ">=" else value <= threshold
    return {"value": value, "operator": operator, "threshold": threshold,
            "passed": bool(passed)}


def evaluate_run_gates(run, snapshots):
    """Apply the pre-registered individual-run gates without inference."""
    if not snapshots:
        raise ValueError("at least one calibration snapshot is required")
    scheduled = int(run["scheduled_vehicles"])
    by_step = {}
    for item in snapshots:
        step = int(item.get("step", -1))
        if step in by_step:
            raise ValueError("snapshot steps must be unique")
        metrics = item.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError("snapshot metrics are required")
        if int(metrics.get("observed_steps", -1)) != step:
            raise ValueError("snapshot observed_steps differs from snapshot step")
        _accounting(metrics, scheduled)
        by_step[step] = metrics
    horizon = int(run["horizon_steps"])
    if horizon not in by_step:
        raise ValueError("terminal calibration snapshot is missing")
    if 3600 not in by_step:
        raise ValueError("3600-second calibration snapshot is missing")

    at_3600 = _accounting(by_step[3600], scheduled)
    checks = {
        "snapshot_conservation": {"passed": True},
        "unreleased_at_3600": _check(float(at_3600["unreleased"]), "<=", 0.0),
        "removed_at_3600": _check(float(at_3600["removed"]), "<=", 0.0),
    }
    values = {
        "insertion_rate_at_3600": (
            float(at_3600["inserted"]) / scheduled if scheduled else 0.0),
        "pending_rate_at_3600": (
            float(at_3600["pending"]) / scheduled if scheduled else 0.0),
        "completion_rate_at_3600": (
            float(at_3600["arrived"]) / scheduled if scheduled else 0.0),
    }
    scenario = run.get("scenario")
    if scenario == "normal":
        eligible = int(run.get("free_flow_eligible_by_snapshot", {}).get(
            "3600", 0))
        ratio = float(at_3600["arrived"]) / eligible if eligible else 0.0
        values["free_flow_eligible_at_3600"] = eligible
        values["free_flow_eligible_completion"] = ratio
        normal = GATE_POLICY["normal"]
        checks.update({
            "normal_insertion_rate": _check(
                values["insertion_rate_at_3600"], ">=",
                normal["minimum_insertion_rate"]),
            "normal_pending_rate": _check(
                values["pending_rate_at_3600"], "<=",
                normal["maximum_pending_rate"]),
            "normal_free_flow_completion": _check(
                ratio, ">=", normal["minimum_free_flow_eligible_completion"]),
        })
    if scenario == "pm_peak":
        checks["pm_insertion_rate"] = _check(
            values["insertion_rate_at_3600"], ">=",
            GATE_POLICY["pm_peak"]["minimum_insertion_rate"])

    if horizon in (5400, 7200):
        terminal = _accounting(by_step[horizon], scheduled)
        completion = float(terminal["arrived"]) / scheduled if scheduled else 0.0
        pending_rate = float(terminal["pending"]) / scheduled if scheduled else 0.0
        values["drain_completion_rate"] = completion
        values["drain_pending_rate"] = pending_rate
        policy = GATE_POLICY["drain_%d" % horizon]
        checks["drain_completion"] = _check(
            completion, ">=", policy["minimum_completion_rate"])
        checks["drain_pending_rate"] = _check(
            pending_rate, "<=", policy["maximum_pending_rate"])
    return {
        "policy": copy.deepcopy(GATE_POLICY),
        "checks": checks,
        "values": values,
        "passed": all(item["passed"] for item in checks.values()),
    }


def evaluate_stage_gates(campaign, completed_results):
    """Evaluate completeness and per-scale aggregate gates for one stage."""
    expected_ids = [run["run_id"] for run in campaign.get("runs", [])]
    by_id = {}
    for result in completed_results:
        run_id = result.get("run", {}).get("run_id")
        if run_id in by_id:
            raise ValueError("completed calibration result IDs must be unique")
        by_id[run_id] = result
    if any(run_id not in expected_ids for run_id in by_id):
        raise ValueError("completed result does not belong to calibration campaign")
    scales = {}
    for scale in sorted(set(float(run["scale"]) for run in campaign.get("runs", []))):
        key = str(scale)
        expected = [run for run in campaign["runs"] if float(run["scale"]) == scale]
        results = [by_id[run["run_id"]] for run in expected if run["run_id"] in by_id]
        checks = {
            "all_runs_complete": {
                "passed": len(results) == len(expected),
                "completed": len(results), "expected": len(expected),
            },
            "all_individual_gates": {
                "passed": len(results) == len(expected) and all(
                    result.get("gates", {}).get("passed") is True
                    for result in results),
            },
        }
        if campaign.get("stage") == "stage-d" and len(results) == len(expected):
            ordering_passed = True
            ordering = {}
            for controller in ("fixed_time_30", "max_pressure_masked_v2"):
                normal = [result for result in results
                          if result["run"]["controller_id"] == controller
                          and result["run"]["scenario"] == "normal"]
                peak = [result for result in results
                        if result["run"]["controller_id"] == controller
                        and result["run"]["scenario"] == "pm_peak"]
                if len(normal) != 2 or len(peak) != 2:
                    ordering_passed = False
                    continue
                normal_queue = sum(float(item["metrics"][
                    "queue_integral_vehicle_seconds"]) for item in normal) / 2.0
                peak_queue = sum(float(item["metrics"][
                    "queue_integral_vehicle_seconds"]) for item in peak) / 2.0
                normal_completion = sum(float(item["metrics"][
                    "completion_rate"]) for item in normal) / 2.0
                peak_completion = sum(float(item["metrics"][
                    "completion_rate"]) for item in peak) / 2.0
                controller_passed = (peak_queue > normal_queue
                                     and peak_completion < normal_completion)
                ordering[controller] = {
                    "normal_mean_queue_integral_vehicle_seconds": normal_queue,
                    "pm_mean_queue_integral_vehicle_seconds": peak_queue,
                    "normal_mean_completion_rate": normal_completion,
                    "pm_mean_completion_rate": peak_completion,
                    "passed": controller_passed,
                }
                ordering_passed = ordering_passed and controller_passed
            checks["pm_normal_aggregate_ordering"] = {
                "passed": ordering_passed, "controllers": ordering}
        scales[key] = {"checks": checks,
                       "passed": all(item["passed"] for item in checks.values())}
    passing = [float(key) for key, value in scales.items() if value["passed"]]
    return {
        "complete": len(by_id) == len(expected_ids),
        "completed_runs": len(by_id),
        "expected_runs": len(expected_ids),
        "scales": scales,
        "highest_passing_scale": (max(passing)
                                  if campaign.get("stage") == "stage-d" and passing
                                  else None),
    }


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_json_bytes(value))
    temporary.replace(path)


def _verify_campaign_inputs(project_root, campaign_dir, campaign):
    root = Path(project_root).resolve()
    identity = campaign.get("campaign_identity_sha256")
    unsigned = copy.deepcopy(campaign)
    unsigned.pop("campaign_identity_sha256", None)
    if identity != _canonical_sha256(unsigned):
        raise ValueError("campaign identity sha256 mismatch")
    binding = campaign["binding"]
    for path_field, sha_field, label in (
            ("source_manifest_path", "source_manifest_sha256", "source manifest"),
            ("training_config_path", "training_config_sha256", "training config"),
            ("generator_config_path", "generator_config_sha256", "generator config"),
            ("network_path", "network_sha256", "network"),
            ("phase_contract_path", "phase_contract_sha256", "phase contract")):
        path = _project_path(root, binding[path_field], label)
        if _sha256(path) != binding[sha_field]:
            raise ValueError("%s sha256 mismatch" % label)
    _verified_file(root, binding["runtime"]["dockerfile"],
                   "runtime Dockerfile")
    if _git_commit(root) != binding["code_commit"]:
        raise ValueError("calibration code commit changed")
    for relative, expected in binding["code_sha256"].items():
        if _sha256(_project_path(root, relative, "calibration code")) != expected:
            raise ValueError("calibration code sha256 mismatch")

    for record in campaign["runs"]:
        manifest_path = _project_path(root, record["run_manifest_path"], "run manifest")
        if _sha256(manifest_path) != record["run_manifest_sha256"]:
            raise ValueError("run manifest sha256 mismatch")
        payload = _load_json(manifest_path, "run manifest")
        expected = copy.deepcopy(record)
        expected.pop("run_manifest_path")
        expected.pop("run_manifest_sha256")
        if payload != expected:
            raise ValueError("run manifest differs from campaign")
        for prefix in ("source_flow", "demand"):
            path = _project_path(root, payload[prefix + "_path"], prefix)
            if _sha256(path) != payload[prefix + "_sha256"]:
                raise ValueError("%s sha256 mismatch" % prefix)


def _default_run_executor(project_root, run, run_dir):
    from traffic_rl.agents.fixed_time import FixedTimeController
    from traffic_rl.agents.max_pressure import MaxPressureController
    from traffic_rl.eval.network_metrics import NetworkMetricsObserver
    from traffic_rl.network.roadnet import RoadNet
    from traffic_rl.sim.engine import CityFlowEngine
    from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

    root = Path(project_root).resolve()
    roadnet = RoadNet.load(
        str(root / run["network_path"]), str(root / run["phase_contract_path"]),
        require_phase_contract=True,
        expected_phase_contract_sha256=run["phase_contract_sha256"])
    if list(roadnet.signalized_ids()) != list(run["agent_ids"]):
        raise ValueError("calibration agent IDs differ from network")
    lane_to_node = {}
    for node_id in roadnet.signalized_ids():
        for lane_id in roadnet.incoming_lanes(node_id):
            lane_to_node[lane_id] = node_id
    observer = NetworkMetricsObserver(
        run["scheduled_vehicles"], step_seconds=1.0,
        lane_to_node=lane_to_node,
        spillback_thresholds=dict((lane, run["normalization"]["capacity_norm"])
                                  for lane in lane_to_node))
    runtime_dir = Path(run_dir) / "runtime-configs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_config = {
        "interval": 1.0, "seed": int(run["simulator_seed"]),
        "dir": str(root) + "/", "roadnetFile": run["network_path"],
        "flowFile": run["demand_path"], "rlTrafficLight": True,
        "laneChange": False, "saveReplay": False,
    }
    runtime_path = runtime_dir / "cityflow.json"
    _write_immutable_json(runtime_path, runtime_config, "CityFlow runtime config")
    simulation = run["simulation"]
    reward = run["reward"]
    env = MultiAgentTrafficEnv(
        roadnet, CityFlowEngine(str(runtime_path)),
        action_interval=int(simulation["action_interval"]),
        max_steps=int(run["horizon_steps"]),
        yellow_time=int(simulation.get("yellow_time", 0)),
        min_green=int(simulation["min_green"]),
        maximum_red=int(simulation["maximum_red"]),
        count_norm=float(run["normalization"]["count_norm"]),
        reward_type="queue_norm", queue_weight=float(reward["queue_weight"]),
        downstream_block_weight=float(reward["downstream_block_weight"]),
        switch_penalty=float(reward["switch_penalty"]),
        network_metric_observer=observer,
        scheduled_vehicles=int(run["scheduled_vehicles"]))
    if run["controller_id"] == "fixed_time_30":
        controller = FixedTimeController(
            env.num_actions, green_duration=30,
            action_interval=int(simulation["action_interval"]))
    elif run["controller_id"] == "max_pressure_masked_v2":
        controller = MaxPressureController(roadnet)
    else:
        raise ValueError("unsupported calibration controller")
    try:
        return rollout_with_snapshots(
            env, controller, run["snapshot_interval_seconds"])
    finally:
        close = getattr(env, "close", None)
        if close is not None:
            close()


def execute_campaign(project_root, campaign_dir, run_executor=None):
    """Execute or hash-safely resume an already prepared diagnostic campaign."""
    root = Path(project_root).resolve()
    output = _project_path(root, campaign_dir, "campaign directory", must_exist=False)
    campaign_path = output / "campaign-manifest.json"
    if not campaign_path.is_file():
        raise ValueError("prepared campaign manifest is required")
    campaign = _load_json(campaign_path, "campaign manifest")
    if campaign.get("eligible_for_release") is not False \
            or campaign.get("eligible_for_test_evaluation") is not False:
        raise ValueError("capacity calibration must remain diagnostic")
    _verify_campaign_inputs(root, output, campaign)
    executor = run_executor or _default_run_executor
    completed_results = []
    failed = 0
    skipped = 0
    for record in campaign["runs"]:
        run_dir = output / "runs" / record["run_id"]
        status_path = run_dir / "status.json"
        result_path = run_dir / "result.json"
        status = _load_json(status_path, "run status") if status_path.is_file() else None
        if status is not None and status.get("status") == "completed":
            if not result_path.is_file() \
                    or _sha256(result_path) != status.get("result_sha256"):
                raise ValueError("completed result sha256 mismatch")
            result = _load_json(result_path, "completed result")
            if result.get("run_manifest_sha256") != record["run_manifest_sha256"]:
                raise ValueError("completed result run manifest mismatch")
            completed_results.append(result)
            skipped += 1
            continue
        if result_path.exists():
            raise ValueError("refusing to overwrite unbound calibration result")
        _atomic_json(status_path, {
            "status": "running", "run_id": record["run_id"],
            "run_manifest_sha256": record["run_manifest_sha256"],
        })
        run_payload = _load_json(
            root / record["run_manifest_path"], "run manifest")
        try:
            metrics, snapshots = executor(root, run_payload, run_dir)
            if not snapshots or snapshots[-1].get("metrics") != metrics:
                raise ValueError(
                    "terminal metrics differ from terminal calibration snapshot")
            if int(metrics.get("observed_steps", -1)) != int(
                    run_payload["horizon_steps"]):
                raise ValueError("calibration did not complete the requested horizon")
            gates = evaluate_run_gates(run_payload, snapshots)
            result = {
                "schema_version": 1,
                "evidence_namespace": "haichau_capacity_calibration_diagnostic",
                "eligible_for_release": False,
                "eligible_for_test_evaluation": False,
                "run_manifest_sha256": record["run_manifest_sha256"],
                "run": run_payload,
                "metrics": metrics,
                "snapshots": snapshots,
                "gates": gates,
            }
            _write_immutable_json(result_path, result, "calibration result")
            result_sha256 = _sha256(result_path)
            _atomic_json(status_path, {
                "status": "completed", "run_id": record["run_id"],
                "run_manifest_sha256": record["run_manifest_sha256"],
                "result_sha256": result_sha256,
            })
            completed_results.append(result)
        except Exception as error:
            failed += 1
            _atomic_json(status_path, {
                "status": "failed", "run_id": record["run_id"],
                "run_manifest_sha256": record["run_manifest_sha256"],
                "error": "%s: %s" % (type(error).__name__, error),
            })
    stage_gates = evaluate_stage_gates(campaign, completed_results)
    summary = {
        "schema_version": 1,
        "evidence_namespace": "haichau_capacity_calibration_diagnostic",
        "eligible_for_release": False,
        "eligible_for_test_evaluation": False,
        "campaign_identity_sha256": campaign["campaign_identity_sha256"],
        "status": ("diagnostic_complete"
                   if len(completed_results) == len(campaign["runs"]) and not failed
                   else "diagnostic_partial"),
        "completed": len(completed_results),
        "failed": failed,
        "skipped": skipped,
        "total": len(campaign["runs"]),
        "stage_gates": stage_gates,
    }
    _atomic_json(output / "summary.json", summary)
    return summary
