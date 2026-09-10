"""Freeze, expand, verify, and summarize the V3 exploratory robustness appendix."""

import hashlib
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

import yaml

from traffic_rl.eval.network_campaign import canonical_sha256
from traffic_rl.eval.network_statistics import paired_bootstrap
from traffic_rl.eval.primary_v3_validation import (
    canonical_primary_protocol_path, canonical_primary_release_path,
    validate_primary_v3_reference,
)
from traffic_rl.eval.robustness_runtime import (
    materialize_demand_plus20, scheduled_departures,
)
from traffic_rl.sim.robustness_perturbations import select_topology_incident


LEARNING_SEEDS = (12, 13, 14, 15, 16)
CONDITIONS = (
    "demand_plus20", "sensor_gaussian", "sensor_dropout",
    "incident_lane_reduction50",
)
DETERMINISTIC_CONTROLLERS = ("tuned_fixed", "max_pressure")
SUPPORTED_PRIMARY_CONTROLLERS = ("neighbor_phase_ddqn", "schedule_residual_ddqn")


def _primary_controller(primary):
    controller = primary.get("primary_learned_controller")
    if controller not in SUPPORTED_PRIMARY_CONTROLLERS:
        raise ValueError("primary protocol selected controller is unsupported")
    return controller


def _controllers(primary):
    return DETERMINISTIC_CONTROLLERS + (_primary_controller(primary),)
RESULT_RELATIVE = Path("results/haichau_network_v2/robustness")
BOOTSTRAP_SAMPLES = 10000
BOOTSTRAP_SEED = 20260908


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _project_path(root, value, label):
    root = Path(root).resolve()
    path = Path(str(value or ""))
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return path


def _verified_file(root, value, expected, label):
    path = _project_path(root, value, label)
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected or "")) \
            or _sha256(path) != expected:
        raise ValueError("%s hash drift" % label)
    return path


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise ValueError("temporary output already exists")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _current_commit(root):
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, universal_newlines=True)
    if completed.returncode:
        raise ValueError("cannot resolve robustness source commit")
    commit = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("robustness source commit must be a full Git SHA")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
    if status.returncode or status.stdout.strip():
        raise ValueError("robustness freeze requires a clean Git checkout")
    return commit


def _validate_config(config, controllers):
    if not isinstance(config, dict):
        raise ValueError("robustness config must be an object")
    forbidden = set(config).intersection({
        "training", "selection", "acceptance", "acceptance_rules",
        "checkpoint_selection", "reselection",
    })
    if forbidden:
        raise ValueError("config contains forbidden training/selection/acceptance keys")
    if config.get("schema_version") != 1 \
            or config.get("study_role") != "exploratory_appendix":
        raise ValueError("config must label study_role exploratory_appendix")
    if tuple(config.get("controllers", ())) != tuple(controllers):
        raise ValueError("config controllers differ from the V3 appendix contract")
    bootstrap = config.get("bootstrap", {})
    if bootstrap != {"samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED}:
        raise ValueError("config bootstrap contract differs")
    expected = {
        "demand_plus20": {"kind": "demand_scale", "multiplier": 1.20},
        "sensor_gaussian": {"kind": "sensor_gaussian", "sigma": 0.15},
        "sensor_dropout": {"kind": "sensor_dropout", "probability": 0.10},
        "incident_lane_reduction50": {
            "kind": "lane_restriction_incident",
            "restricted_lane_fraction": 0.50,
            "start_step": 1200, "end_step": 2400,
            "target_rule": "topology_max_incoming_lanes_then_ids",
        },
    }
    if config.get("conditions") != expected:
        raise ValueError("config conditions differ from preregistration")
    return config


def _case_bindings(root, primary, roadnet):
    case_path = _verified_file(
        root, primary.get("case_manifest_path"),
        primary.get("case_manifest_sha256"), "case manifest")
    case_document = _json(case_path, "case manifest")
    cases = [dict(item) for item in case_document.get("cases", ())
             if item.get("split") == "test"]
    if len(cases) != 15 or len(set(item.get("case_id") for item in cases)) != 15:
        raise ValueError("case manifest must bind exactly 15 unique test cases")
    regimes = dict((name, 0) for name in ("normal", "am_peak", "pm_peak"))
    roads = dict((road["id"], road) for road in roadnet.get("roads", ()))
    for case in cases:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(case.get("case_id", ""))) \
                or case.get("case_id") in (".", ".."):
            raise ValueError("test case ID is unsafe")
        regime = case.get("regime")
        if regime not in regimes:
            raise ValueError("test case regime is invalid")
        regimes[regime] += 1
        flow = _verified_file(
            root, case.get("demand_path"), case.get("demand_sha256"),
            "case flow")
        rows = json.loads(flow.read_text())
        if not isinstance(rows, list) or not rows:
            raise ValueError("case flow must be a non-empty list")
        scheduled = 0
        for row in rows:
            route = row.get("route")
            if not isinstance(route, list) or not route \
                    or any(road_id not in roads for road_id in route):
                raise ValueError("case flow route is invalid")
            for before, after in zip(route, route[1:]):
                if roads[before].get("endIntersection") \
                        != roads[after].get("startIntersection"):
                    raise ValueError("case flow route is not topologically continuous")
            scheduled += scheduled_departures(row)
        if scheduled != case.get("scheduled_vehicles"):
            raise ValueError("case flow vehicle accounting does not conserve")
    if regimes != {"normal": 5, "am_peak": 5, "pm_peak": 5}:
        raise ValueError("test cases must contain five cases per regime")
    return cases, case_path


def _validate_phases(roadnet, agent_ids):
    intersections = dict((item["id"], item)
                         for item in roadnet.get("intersections", ()))
    if len(agent_ids) != 53 or len(set(agent_ids)) != 53:
        raise ValueError("primary protocol must bind 53 unique signal IDs")
    for agent_id in agent_ids:
        node = intersections.get(agent_id)
        if not node or node.get("virtual"):
            raise ValueError("controlled signal is absent from roadnet")
        links = node.get("roadLinks", ())
        phases = node.get("trafficLight", {}).get("lightphases", ())
        if len(phases) < 2:
            raise ValueError("controlled signal phase contract is invalid")
        for phase in phases:
            indexes = phase.get("availableRoadLinks", ())
            if any(type(index) is not int or not 0 <= index < len(links)
                   for index in indexes):
                raise ValueError("controlled signal phase references an invalid road link")


def _checkpoint_bindings(root, primary, controller):
    bindings = []
    entries = primary.get("checkpoints", ())
    for seed in LEARNING_SEEDS:
        matches = [item for item in entries
                   if item.get("controller_id") == controller
                   and item.get("learning_seed") == seed]
        if len(matches) != 1:
            raise ValueError("primary protocol requires one checkpoint per seed 12--16")
        item = matches[0]
        if controller != "schedule_residual_ddqn" \
                and item.get("validation_eligible") is not True:
            raise ValueError("primary checkpoint is not validation-eligible")
        path = _verified_file(
            root, item.get("path"), item.get("sha256"), "checkpoint")
        contract = item.get("checkpoint_contract")
        if not isinstance(contract, dict) \
                or contract.get("controller_family") != controller:
            raise ValueError("checkpoint contract is invalid")
        bindings.append({
            "controller_id": controller,
            "learning_seed": seed,
            "path": str(path.relative_to(Path(root).resolve())),
            "sha256": item["sha256"],
            "validation_eligible": True,
            "checkpoint_contract": contract,
            "checkpoint_contract_sha256": canonical_sha256(contract),
        })
    return bindings


def freeze_robustness_protocol(root, primary_protocol_path, config_path,
                               output_dir, robustness_code_commit=None):
    """Freeze immutable appendix inputs without executing a simulator episode."""
    root = Path(root).resolve()
    output = Path(output_dir).resolve()
    expected_output = (root / RESULT_RELATIVE).resolve()
    if output != expected_output:
        raise ValueError("robustness output must use the separate robustness namespace")
    if output.exists():
        raise ValueError("robustness output already exists")
    primary_path = canonical_primary_protocol_path(root, primary_protocol_path)
    config_file = _project_path(root, config_path, "robustness config")
    primary = _json(primary_path, "primary protocol")
    controllers = _controllers(primary)
    config = _validate_config(yaml.safe_load(config_file.read_text()), controllers)
    primary_reference = validate_primary_v3_reference(
        root, primary_path, primary=primary)
    primary_campaign = primary_reference["campaign_manifest_path"]
    primary_summary = primary_reference["summary_path"]
    seeds = tuple(primary.get("confirmatory_learning_seeds", ()))
    rule_seeds = tuple(primary.get("acceptance_rules", {}).get(
        "required_learning_seeds", ()))
    if seeds != LEARNING_SEEDS or rule_seeds != LEARNING_SEEDS or 11 in seeds:
        raise ValueError("primary protocol must derive exact learning seeds 12--16")

    resolved = primary.get("resolved_config", {})
    roadnet_path = _verified_file(
        root, primary.get("network_path", resolved.get("network_path")),
        primary.get("network_sha256"), "network")
    phase_path = _verified_file(
        root, primary.get("phase_contract_path", resolved.get("phase_contract_path")),
        primary.get("phase_contract_sha256"), "phase contract")
    roadnet = json.loads(roadnet_path.read_text())
    _validate_phases(roadnet, list(primary.get("agent_ids", ())))
    cases, case_path = _case_bindings(root, primary, roadnet)
    checkpoints = _checkpoint_bindings(root, primary, controllers[-1])
    target = select_topology_incident(
        roadnet, controlled_signal_ids=primary.get("agent_ids", ()))
    conditions = json.loads(json.dumps(config["conditions"]))
    conditions["incident_lane_reduction50"]["target"] = target
    code_commit = robustness_code_commit or _current_commit(root)
    if not re.fullmatch(r"[0-9a-f]{40}", str(code_commit)):
        raise ValueError("robustness source commit must be a full Git SHA")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".robustness-freeze-",
                                     dir=str(output.parent)))
    try:
        demand_bindings = {}
        for case in cases:
            source = _project_path(root, case["demand_path"], "case flow")
            temp_target = temporary / "inputs/demand_plus20" / (
                str(case["case_id"]) + ".json")
            record = materialize_demand_plus20(source, temp_target, 1.2)
            record["path"] = str(
                RESULT_RELATIVE / "inputs/demand_plus20" /
                (str(case["case_id"]) + ".json"))
            demand_bindings[case["case_id"]] = record
        protocol = {
            "schema_version": 1,
            "study_role": "exploratory_appendix",
            "evidence_namespace": "haichau_network_v2/robustness",
            "episode_count": 420,
            "primary_protocol_path": str(primary_path.relative_to(root)),
            "primary_protocol_sha256": _sha256(primary_path),
            "primary_code_commit": primary.get("code_commit"),
            "primary_results_reference": {
                "usage": "reference_only",
                "fresh_episode_credit": 0,
                "campaign_manifest_path": str(primary_campaign.relative_to(root)),
                "campaign_manifest_sha256": _sha256(primary_campaign),
                "summary_path": str(primary_summary.relative_to(root)),
                "summary_sha256": _sha256(primary_summary),
            },
            "robustness_code_commit": code_commit,
            "config_path": str(config_file.relative_to(root)),
            "config_sha256": _sha256(config_file),
            "case_manifest_path": str(case_path.relative_to(root)),
            "case_manifest_sha256": _sha256(case_path),
            "network_path": str(roadnet_path.relative_to(root)),
            "network_sha256": _sha256(roadnet_path),
            "phase_contract_path": str(phase_path.relative_to(root)),
            "phase_contract_sha256": _sha256(phase_path),
            "viewer_network_sha256": primary.get("viewer_network_sha256"),
            "runtime_digest": primary.get("runtime_digest"),
            "runtime_image": primary.get("runtime_image"),
            "runtime_image_id": primary.get("runtime_image_id"),
            "runtime_dockerfile_path": primary.get("runtime_dockerfile_path"),
            "runtime_dockerfile_sha256": primary.get(
                "runtime_dockerfile_sha256"),
            "agent_ids": list(primary.get("agent_ids", ())),
            "controlled_signals": 53,
            "controllers": list(controllers),
            "learning_seeds": list(LEARNING_SEEDS),
            "cases": cases,
            "conditions": conditions,
            "demand_plus20_bindings": demand_bindings,
            "checkpoint_bindings": checkpoints,
            "resolved_config": resolved,
            "normalization": primary.get("normalization"),
            "controller_configs": dict(
                (name, primary.get("controller_configs", {}).get(name, {}))
                for name in controllers),
            "controller_commands": dict(
                (name, ["python3", "scripts/evaluate_haichau_robustness.py"])
                for name in controllers),
            "bootstrap": {"samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED},
            "primary_results_usage": "reference_only_not_counted_as_fresh_episode",
            "changes_to_training_selection_or_acceptance": False,
        }
        _write_json(temporary / "frozen-robustness-protocol.json", protocol)
        os.rename(str(temporary), str(output))
    except Exception:
        if temporary.exists():
            shutil.rmtree(str(temporary))
        raise
    return protocol


def _perturbation_seed(condition_id, case):
    identity = "%s|%s|%s|%s" % (
        condition_id, case["case_id"], case["demand_seed"],
        case["simulator_seed"])
    return int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16)


def _verify_frozen_inputs(root, protocol):
    forbidden = set(protocol).intersection({
        "training", "selection", "acceptance", "acceptance_rules",
        "checkpoint_selection", "reselection",
    })
    if forbidden:
        raise ValueError(
            "robustness protocol cannot change training/selection/acceptance")
    if protocol.get("study_role") != "exploratory_appendix" \
            or protocol.get("changes_to_training_selection_or_acceptance") is not False \
            or protocol.get("episode_count") != 420:
        raise ValueError("robustness protocol scope is invalid")
    canonical_primary = canonical_primary_protocol_path(
        root, protocol["primary_protocol_path"])
    primary_path = _verified_file(
        root, canonical_primary,
        protocol["primary_protocol_sha256"], "primary protocol")
    config_path = _verified_file(
        root, protocol["config_path"], protocol["config_sha256"], "config")
    case_path = _verified_file(
        root, protocol["case_manifest_path"],
        protocol["case_manifest_sha256"], "case manifest")
    roadnet_path = _verified_file(
        root, protocol["network_path"], protocol["network_sha256"], "network")
    phase_path = _verified_file(
        root, protocol["phase_contract_path"],
        protocol["phase_contract_sha256"], "phase contract")
    primary = _json(primary_path, "primary protocol")
    controllers = _controllers(primary)
    config = _validate_config(yaml.safe_load(config_path.read_text()), controllers)
    primary_reference = validate_primary_v3_reference(
        root, primary_path, primary=primary)
    if (tuple(primary.get("confirmatory_learning_seeds", ())) != LEARNING_SEEDS
            or tuple(primary.get("acceptance_rules", {}).get(
                "required_learning_seeds", ())) != LEARNING_SEEDS
):
        raise ValueError("primary protocol no longer binds exact seeds 12--16")
    if protocol.get("primary_code_commit") != primary.get("code_commit") \
            or not re.fullmatch(r"[0-9a-f]{40}", str(
                protocol.get("robustness_code_commit", ""))):
        raise ValueError("robustness source commit binding is invalid")
    identity_fields = (
        "network_sha256", "viewer_network_sha256", "phase_contract_sha256",
        "runtime_digest", "runtime_image", "runtime_image_id",
        "runtime_dockerfile_path", "runtime_dockerfile_sha256",
    )
    if any(protocol.get(field) != primary.get(field) for field in identity_fields):
        raise ValueError("robustness protocol identity differs from primary protocol")
    resolved = primary.get("resolved_config", {})
    if (protocol.get("network_path")
            != primary.get("network_path", resolved.get("network_path"))
            or protocol.get("phase_contract_path")
            != primary.get("phase_contract_path", resolved.get("phase_contract_path"))
            or protocol.get("agent_ids") != primary.get("agent_ids")
            or protocol.get("normalization") != primary.get("normalization")):
        raise ValueError("robustness path/agent/normalization binding differs")
    roadnet = json.loads(roadnet_path.read_text())
    _validate_phases(roadnet, protocol.get("agent_ids", ()))
    expected_cases, expected_case_path = _case_bindings(root, primary, roadnet)
    if expected_case_path != case_path or protocol.get("cases") != expected_cases:
        raise ValueError("robustness cases differ from the hash-bound primary cases")
    if protocol.get("checkpoint_bindings") != _checkpoint_bindings(root, primary, controllers[-1]):
        raise ValueError("robustness checkpoint bindings differ from primary")
    expected_conditions = json.loads(json.dumps(config["conditions"]))
    target = select_topology_incident(
        roadnet, controlled_signal_ids=protocol.get("agent_ids", ()))
    expected_conditions["incident_lane_reduction50"]["target"] = target
    if protocol.get("conditions") != expected_conditions:
        raise ValueError("robustness condition differs from preregistration")
    expected_configs = dict(
        (name, primary.get("controller_configs", {}).get(name, {}))
        for name in controllers)
    if protocol.get("controller_configs") != expected_configs \
            or protocol.get("resolved_config") != primary.get("resolved_config"):
        raise ValueError("robustness runtime configuration differs from primary")
    expected_commands = dict(
        (name, ["python3", "scripts/evaluate_haichau_robustness.py"])
        for name in controllers)
    if protocol.get("controller_commands") != expected_commands \
            or protocol.get("bootstrap") != {
                "samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED}:
        raise ValueError("robustness command/statistics binding differs")
    reference = protocol.get("primary_results_reference", {})
    if reference.get("usage") != "reference_only" \
            or reference.get("fresh_episode_credit") != 0:
        raise ValueError("primary results may be used only as a zero-credit reference")
    canonical_campaign = canonical_primary_release_path(
        root, "campaign-manifest.json",
        supplied=reference.get("campaign_manifest_path"))
    canonical_summary = canonical_primary_release_path(
        root, "summary.json", supplied=reference.get("summary_path"))
    reference_campaign = _verified_file(
        root, canonical_campaign,
        reference.get("campaign_manifest_sha256"),
        "primary campaign manifest")
    reference_summary = _verified_file(
        root, canonical_summary,
        reference.get("summary_sha256"), "primary summary")
    if (reference_campaign
            != primary_reference["campaign_manifest_path"].resolve()
            or reference.get("campaign_manifest_sha256")
            != primary_reference["campaign_manifest_sha256"]
            or reference_summary
            != primary_reference["summary_path"].resolve()
            or reference.get("summary_sha256")
            != primary_reference["summary_sha256"]):
        raise ValueError("primary verified release reference differs")
    for checkpoint in protocol.get("checkpoint_bindings", ()):
        _verified_file(root, checkpoint["path"], checkpoint["sha256"], "checkpoint")
    for binding in protocol.get("demand_plus20_bindings", {}).values():
        _verified_file(root, binding["path"], binding["sha256"],
                       "demand_plus20 input")
    if set(protocol.get("demand_plus20_bindings", {})) != set(
            case["case_id"] for case in expected_cases):
        raise ValueError("demand_plus20 bindings do not cover all frozen cases")
    for case in expected_cases:
        binding = protocol["demand_plus20_bindings"][case["case_id"]]
        expected_path = str(
            RESULT_RELATIVE / "inputs/demand_plus20" /
            (str(case["case_id"]) + ".json"))
        if binding.get("source_sha256") != case["demand_sha256"] \
                or binding.get("source_scheduled_vehicles") \
                != case["scheduled_vehicles"] \
                or binding.get("path") != expected_path:
            raise ValueError("demand_plus20 source binding differs from primary case")
        source_rows = json.loads(_project_path(
            root, case["demand_path"], "case flow").read_text())
        scaled_rows = json.loads(_project_path(
            root, binding["path"], "demand_plus20 input").read_text())
        if len(source_rows) != len(scaled_rows):
            raise ValueError("demand_plus20 stream count differs from primary")
        for source, scaled in zip(source_rows, scaled_rows):
            if (scaled.get("route") != source.get("route")
                    or scaled.get("vehicle") != source.get("vehicle")
                    or scaled.get("startTime") != source.get("startTime")
                    or scaled.get("endTime") != source.get("endTime")
                    or abs(float(scaled.get("interval")) * 1.2
                           - float(source.get("interval"))) > 1e-12):
                raise ValueError("demand_plus20 semantics differ from preregistration")
        if binding.get("scheduled_vehicles") != sum(
                scheduled_departures(row) for row in scaled_rows):
            raise ValueError("demand_plus20 vehicle accounting does not conserve")


def expand_robustness_runs(root, protocol):
    """Expand the frozen 4 x 15 x (2 deterministic + 5 learned) matrix."""
    root = Path(root).resolve()
    _verify_frozen_inputs(root, protocol)
    primary_controller = _primary_controller({
        "primary_learned_controller": protocol.get("controllers", [None])[-1]
    })
    controllers = DETERMINISTIC_CONTROLLERS + (primary_controller,)
    if tuple(protocol.get("learning_seeds", ())) != LEARNING_SEEDS \
            or tuple(protocol.get("controllers", ())) != controllers:
        raise ValueError("frozen appendix seed/controller contract drift")
    if set(protocol.get("conditions", {})) != set(CONDITIONS):
        raise ValueError("frozen appendix condition contract drift")
    cases = protocol.get("cases", ())
    if len(cases) != 15:
        raise ValueError("frozen appendix requires exactly 15 cases")
    protocol_sha = canonical_sha256(protocol)
    runs = []
    for condition_id in CONDITIONS:
        condition = protocol["conditions"][condition_id]
        for controller_id in controllers:
            seeds = LEARNING_SEEDS if controller_id == primary_controller else (None,)
            for learning_seed in seeds:
                for case in cases:
                    demand = {
                        "path": case["demand_path"],
                        "sha256": case["demand_sha256"],
                        "scheduled_vehicles": case["scheduled_vehicles"],
                    }
                    if condition_id == "demand_plus20":
                        demand = protocol["demand_plus20_bindings"][case["case_id"]]
                    suffix = "det" if learning_seed is None else "ls%d" % learning_seed
                    run_id = "%s__%s__%s__%s" % (
                        condition_id, controller_id, case["case_id"], suffix)
                    run = {
                        "run_id": run_id,
                        "condition_id": condition_id,
                        "robustness_condition": condition,
                        "perturbation_seed": _perturbation_seed(condition_id, case),
                        "study_role": "exploratory_appendix",
                        "case_id": case["case_id"],
                        "regime": case["regime"],
                        "controller_id": controller_id,
                        "learning_seed": learning_seed,
                        "demand_seed": case["demand_seed"],
                        "simulator_seed": case["simulator_seed"],
                        "scheduled_vehicles": demand["scheduled_vehicles"],
                        "horizon_steps": case.get("horizon_steps", 3600),
                        "network_sha256": protocol["network_sha256"],
                        "viewer_network_sha256": protocol["viewer_network_sha256"],
                        "demand_path": demand["path"],
                        "demand_sha256": demand["sha256"],
                        "runtime_digest": protocol["runtime_digest"],
                        "runtime_image": protocol["runtime_image"],
                        "runtime_image_id": protocol["runtime_image_id"],
                        "runtime_dockerfile_path": protocol["runtime_dockerfile_path"],
                        "runtime_dockerfile_sha256": protocol[
                            "runtime_dockerfile_sha256"],
                        "code_commit": protocol["robustness_code_commit"],
                        "primary_protocol_sha256": protocol[
                            "primary_protocol_sha256"],
                        "robustness_protocol_sha256": protocol_sha,
                        "evidence_namespace": "haichau_network_v2/robustness",
                        "fresh_evaluation": True,
                        "controlled_signals": 53,
                        "agent_ids": list(protocol["agent_ids"]),
                        "command": ["python3", "scripts/evaluate_haichau_robustness.py"],
                    }
                    resolved = dict(protocol["resolved_config"])
                    resolved.update(protocol["controller_configs"][controller_id])
                    resolved.update(dict((key, run[key]) for key in (
                        "case_id", "regime", "controller_id", "learning_seed",
                        "demand_seed", "simulator_seed", "scheduled_vehicles",
                        "horizon_steps", "network_sha256", "viewer_network_sha256",
                        "demand_path", "demand_sha256", "runtime_digest",
                        "runtime_image", "runtime_image_id",
                        "runtime_dockerfile_path", "runtime_dockerfile_sha256",
                        "code_commit")))
                    resolved["robustness"] = {
                        "condition_id": condition_id,
                        "condition": condition,
                        "perturbation_seed": run["perturbation_seed"],
                        "study_role": "exploratory_appendix",
                    }
                    if learning_seed is not None:
                        checkpoint = next(item for item in
                                          protocol["checkpoint_bindings"]
                                          if item["learning_seed"] == learning_seed)
                        run.update({
                            "checkpoint_path": checkpoint["path"],
                            "checkpoint_sha256": checkpoint["sha256"],
                            "checkpoint_contract": checkpoint["checkpoint_contract"],
                            "checkpoint_contract_sha256": checkpoint[
                                "checkpoint_contract_sha256"],
                        })
                        resolved["checkpoint"] = dict((key, run[key]) for key in (
                            "checkpoint_path", "checkpoint_sha256",
                            "checkpoint_contract", "checkpoint_contract_sha256"))
                    run["resolved_config"] = resolved
                    runs.append(run)
    if len(runs) != 420 or len(set(item["run_id"] for item in runs)) != 420:
        raise ValueError("robustness expansion must produce exactly 420 unique episodes")
    return runs


def _metric_summary(values):
    values = [float(value) for value in values]
    low, high = paired_bootstrap(
        values, seed=BOOTSTRAP_SEED, samples=BOOTSTRAP_SAMPLES)
    return {
        "n_independent": len(values),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "bootstrap_ci95": [low, high],
        "independent_values": values,
    }


def _controller_summary_cell(condition_id, controller_id, group, baseline,
                             matched_case_count, primary_controller):
    learning = controller_id == primary_controller
    expected = matched_case_count * (len(LEARNING_SEEDS) if learning else 1)
    if len(group) != expected:
        raise ValueError("robustness controller/case expansion is incomplete")
    if learning:
        by_seed = []
        for seed in LEARNING_SEEDS:
            seeded = [row for row in group if row["learning_seed"] == seed]
            if len(seeded) != matched_case_count:
                raise ValueError("learning seed lacks matched cases")
            by_seed.append(seeded)
        queue_values = [statistics.mean(
            float(row["queue_integral_vehicle_seconds"]) for row in seeded)
            for seeded in by_seed]
        completion_values = [statistics.mean(
            float(row["completion_rate"]) for row in seeded)
            for seeded in by_seed]
    else:
        queue_values = [float(row["queue_integral_vehicle_seconds"])
                        for row in group]
        completion_values = [float(row["completion_rate"]) for row in group]
    cell = {
        "episodes": len(group),
        "queue": _metric_summary(queue_values),
        "completion_rate": _metric_summary(completion_values),
    }
    if controller_id == "tuned_fixed":
        return cell
    if learning:
        paired = [statistics.mean(
            float(row["queue_integral_vehicle_seconds"])
            - float(baseline[(condition_id, row["case_id"])][
                "queue_integral_vehicle_seconds"])
            for row in seeded) for seeded in by_seed]
        completion = [statistics.mean(
            float(row["completion_rate"])
            - float(baseline[(condition_id, row["case_id"])]["completion_rate"])
            for row in seeded) for seeded in by_seed]
        unit = "learning_seed_after_matched_case_mean"
    else:
        paired = [
            float(row["queue_integral_vehicle_seconds"])
            - float(baseline[(condition_id, row["case_id"])][
                "queue_integral_vehicle_seconds"])
            for row in group]
        completion = [
            float(row["completion_rate"])
            - float(baseline[(condition_id, row["case_id"])]["completion_rate"])
            for row in group]
        unit = "matched_demand_simulator_case"
    cell["statistical_unit"] = unit
    cell["queue_difference_vs_tuned_fixed"] = _metric_summary(paired)
    cell["completion_difference_vs_tuned_fixed"] = _metric_summary(completion)
    return cell


def summarize_robustness(rows):
    """Report exploratory effects with seed-level hierarchical pairing."""
    if len(rows) != 420:
        raise ValueError("robustness summary requires exactly 420 fresh episodes")
    keys = set()
    baseline = {}
    for row in rows:
        identity = (row.get("condition_id"), row.get("controller_id"),
                    row.get("case_id"), row.get("learning_seed"))
        if identity in keys:
            raise ValueError("robustness rows contain a duplicate episode")
        keys.add(identity)
        if row.get("condition_id") not in CONDITIONS:
            raise ValueError("robustness row condition is invalid")
        if row.get("controller_id") == "tuned_fixed":
            baseline[(row["condition_id"], row["case_id"])] = row
    if len(baseline) != 60:
        raise ValueError("robustness summary requires all matched fixed references")
    controllers = tuple(sorted(set(row.get("controller_id") for row in rows)))
    primary = [name for name in controllers if name not in DETERMINISTIC_CONTROLLERS]
    if len(primary) != 1 or primary[0] not in SUPPORTED_PRIMARY_CONTROLLERS:
        raise ValueError("robustness rows require one supported learned controller")
    primary_controller = primary[0]
    output = {}
    for condition_id in CONDITIONS:
        output[condition_id] = {}
        for controller_id in controllers:
            group = [row for row in rows
                     if row["condition_id"] == condition_id
                     and row["controller_id"] == controller_id]
            cell = _controller_summary_cell(
                condition_id, controller_id, group, baseline, 15, primary_controller)
            cell["by_regime"] = {}
            for regime in ("normal", "am_peak", "pm_peak"):
                regime_group = [row for row in group if row["regime"] == regime]
                cell["by_regime"][regime] = _controller_summary_cell(
                    condition_id, controller_id, regime_group, baseline, 5, primary_controller)
            output[condition_id][controller_id] = cell
    return {
        "schema_version": 1,
        "study_role": "exploratory_appendix",
        "interpretation": "descriptive_sensitivity_without_confirmatory_decision",
        "episodes": 420,
        "conditions": output,
        "inference": {
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "interval": "two_sided_percentile_95",
            "learning_statistical_unit": "learning_seed_after_matched_case_mean",
            "matched_cases_per_seed": 15,
        },
    }


def validate_robustness_directory(root, directory):
    path = Path(directory)
    if not path.is_absolute():
        path = Path(root) / path
    path = path.resolve()
    if path != (Path(root).resolve() / RESULT_RELATIVE).resolve():
        raise ValueError("output must remain in the separate robustness namespace")
    return path


def _assert_robustness_directory(directory):
    path = Path(directory).resolve()
    try:
        root = path.parents[2]
    except IndexError:
        raise ValueError("output must remain in the separate robustness namespace")
    return validate_robustness_directory(root, path)


def write_campaign_manifest(directory, runs):
    """Write the 420-run campaign exactly once."""
    path = _assert_robustness_directory(directory)
    target = path / "campaign-manifest.json"
    if target.exists():
        raise ValueError("refusing to replace immutable robustness campaign")
    if len(runs) != 420 or len(set(run.get("run_id") for run in runs)) != 420:
        raise ValueError("robustness campaign requires exactly 420 unique runs")
    document = {
        "campaign_version": 3,
        # The shared trusted runner recognizes this release family. The nested
        # appendix namespace remains explicit in every run and in this envelope.
        "evidence_namespace": "haichau_network_v2",
        "appendix_evidence_namespace": "haichau_network_v2/robustness",
        "study_role": "exploratory_appendix",
        "episode_count": 420,
        "runs": list(runs),
    }
    _write_json(target, document)
    return document


def write_robustness_summary(directory, summary):
    """Write descriptive appendix JSON and CSV exactly once."""
    path = _assert_robustness_directory(directory)
    json_path = path / "summary.json"
    csv_path = path / "summary.csv"
    if json_path.exists() or csv_path.exists():
        raise ValueError("refusing to replace immutable robustness summary")
    json_temporary = json_path.with_name(json_path.name + ".tmp")
    csv_temporary = csv_path.with_name(csv_path.name + ".tmp")
    if json_temporary.exists() or csv_temporary.exists():
        raise ValueError("temporary robustness summary output already exists")
    json_temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    fieldnames = [
        "condition_id", "controller_id", "episodes", "statistical_unit",
        "queue_mean", "queue_difference_mean", "queue_difference_ci95_low",
        "queue_difference_ci95_high", "completion_rate_mean",
    ]
    with csv_temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for condition_id, controllers in sorted(
                summary.get("conditions", {}).items()):
            for controller_id, cell in sorted(controllers.items()):
                effect = cell.get("queue_difference_vs_tuned_fixed", {})
                interval = effect.get("bootstrap_ci95", ("", ""))
                writer.writerow({
                    "condition_id": condition_id,
                    "controller_id": controller_id,
                    "episodes": cell.get("episodes", ""),
                    "statistical_unit": cell.get("statistical_unit", ""),
                    "queue_mean": cell.get("queue", {}).get("mean", ""),
                    "queue_difference_mean": effect.get("mean", ""),
                    "queue_difference_ci95_low": interval[0],
                    "queue_difference_ci95_high": interval[1],
                    "completion_rate_mean": cell.get(
                        "completion_rate", {}).get("mean", ""),
                })
    json_temporary.replace(json_path)
    csv_temporary.replace(csv_path)
    return {"summary_json": str(json_path), "summary_csv": str(csv_path)}
