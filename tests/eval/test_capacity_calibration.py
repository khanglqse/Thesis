import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from traffic_rl.eval.capacity_calibration import (
    evaluate_run_gates,
    evaluate_stage_gates,
    execute_campaign,
    free_flow_eligible_by_snapshot,
    prepare_campaign,
    rollout_with_snapshots,
    scale_flow,
    scheduled_departures,
)


def _vehicle(max_speed=20.0):
    return {
        "length": 2.0, "width": 1.0, "maxPosAcc": 3.5,
        "maxNegAcc": 5.0, "usualPosAcc": 3.0, "usualNegAcc": 4.5,
        "minGap": 0.5, "maxSpeed": max_speed, "headwayTime": 0.8,
    }


def test_scale_flow_changes_rate_and_preserves_stream_structure_and_offset():
    source = [
        {"vehicle": _vehicle(), "route": ["r0"], "interval": 100.0,
         "startTime": 20, "endTime": 1199},
        {"vehicle": _vehicle(), "route": ["r1"], "interval": 80.0,
         "startTime": 1240, "endTime": 2399},
    ]
    original = copy.deepcopy(source)
    bins = [{"start": 0, "end": 1200}, {"start": 1200, "end": 2400}]

    scaled = scale_flow(source, 0.5, bins)

    assert source == original
    assert scaled == [
        {"vehicle": _vehicle(), "route": ["r0"], "interval": 200.0,
         "startTime": 40, "endTime": 1199},
        {"vehicle": _vehicle(), "route": ["r1"], "interval": 160.0,
         "startTime": 1280, "endTime": 2399},
    ]
    assert [scheduled_departures(row) for row in scaled] == [6, 7]


def test_scheduled_departures_uses_mathematical_floor_for_decimal_intervals():
    row = {"interval": 0.1, "startTime": 0.0, "endTime": 1.0}

    assert scheduled_departures(row) == 11


@pytest.mark.parametrize("scale", [0, -0.1, float("inf"), float("nan")])
def test_scale_flow_rejects_non_positive_or_non_finite_scale(scale):
    with pytest.raises(ValueError, match="scale"):
        scale_flow([], scale, [{"start": 0, "end": 1200}])


def test_free_flow_eligibility_uses_departure_time_route_length_and_speed_limit():
    flow = [{"vehicle": _vehicle(max_speed=20.0), "route": ["r0"],
             "interval": 50.0, "startTime": 0, "endTime": 100}]
    roadnet = {
        "roads": [{"id": "r0", "points": [{"x": 0, "y": 0},
                                                {"x": 100, "y": 0}],
                   "lanes": [{"maxSpeed": 10.0}]}],
        "intersections": [],
    }

    assert free_flow_eligible_by_snapshot(flow, roadnet, [50, 60, 110]) == {
        "50": 1, "60": 2, "110": 3,
    }


def test_free_flow_eligibility_rejects_missing_route_road():
    flow = [{"vehicle": _vehicle(), "route": ["missing"],
             "interval": 50.0, "startTime": 0, "endTime": 100}]

    with pytest.raises(ValueError, match="unknown road"):
        free_flow_eligible_by_snapshot(
            flow, {"roads": [], "intersections": []}, [3600])


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _project(tmp_path):
    root = tmp_path / "project"
    (root / "inputs").mkdir(parents=True)
    (root / "src/traffic_rl/eval").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "src/traffic_rl/eval/capacity_calibration.py").write_text("module\n")
    (root / "scripts/calibrate_haichau_capacity.py").write_text("cli\n")
    roadnet = {
        "roads": [{"id": "r0", "points": [{"x": 0, "y": 0},
                                                {"x": 100, "y": 0}],
                   "lanes": [{"maxSpeed": 10.0}]}],
        "intersections": [],
    }
    (root / "inputs/roadnet.json").write_text(json.dumps(roadnet))
    (root / "inputs/phase.json").write_text("{}")
    (root / "inputs/generator.yaml").write_text("route_count: 1\n")
    (root / "inputs/Dockerfile").write_text("FROM fixture@sha256:test\n")
    (root / "inputs/training.yaml").write_text(
        "reward: {queue_weight: 1.0, downstream_block_weight: 0.2, "
        "switch_penalty: 0.05}\n")
    cases = []
    for scenario in ("normal", "am_peak", "pm_peak"):
        for seed in (31, 32):
            flow_path = root / "inputs" / ("validation_%s_%s.json" %
                                            (scenario, seed))
            flow = [{"vehicle": _vehicle(), "route": ["r0"],
                     "interval": 100.0, "startTime": 20,
                     "endTime": 1199}]
            flow_path.write_text(json.dumps(flow))
            cases.append({
                "case_id": "validation_%s_demand%s" % (scenario, seed),
                "split": "validation", "scenario": scenario,
                "demand_seed": seed, "sim_seed": seed + 100,
                "flow_path": str(flow_path.relative_to(root)),
                "flow_sha256": _sha(flow_path), "flow_streams": 1,
                "scheduled_vehicles": 12,
                "temporal_profile": [{"start": 0, "end": 1200}],
            })
    cases.append({
        "case_id": "never_open_test", "split": "test", "scenario": "normal",
        "demand_seed": 101, "sim_seed": 201,
        "flow_path": "inputs/missing-secret-test.json", "flow_sha256": "0" * 64,
        "flow_streams": 1, "scheduled_vehicles": 12,
        "temporal_profile": [{"start": 0, "end": 1200}],
    })
    manifest = {
        "protocol_version": 2,
        "dataset_id": "fixture",
        "generator_config_path": "inputs/generator.yaml",
        "generator_config_sha256": _sha(root / "inputs/generator.yaml"),
        "network": {"path": "inputs/roadnet.json",
                    "sha256": _sha(root / "inputs/roadnet.json"),
                    "controlled_signals": 1, "agent_ids": ["A"]},
        "phase_contract": {"path": "inputs/phase.json",
                           "sha256": _sha(root / "inputs/phase.json")},
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
        "simulation": {"action_interval": 10, "yellow_time": 3,
                       "min_green": 20, "maximum_red": 180},
        "runtime": {"base_image_digest": "sha256:" + "b" * 64,
                    "derived_image_tag": "traffic-rl-cityflow-research:v2",
                    "platform": "linux/amd64",
                    "dockerfile": {"path": "inputs/Dockerfile",
                                   "sha256": _sha(root / "inputs/Dockerfile")}},
        "cases": cases,
    }
    manifest_path = root / "inputs/manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    subprocess.check_call(["git", "init", "-q", str(root)])
    subprocess.check_call(["git", "-C", str(root), "config", "user.name", "Test"])
    subprocess.check_call(["git", "-C", str(root), "config", "user.email",
                           "test@example.invalid"])
    subprocess.check_call(["git", "-C", str(root), "add", "."])
    subprocess.check_call(["git", "-C", str(root), "commit", "-qm", "fixture"])
    return root, manifest_path, root / "inputs/training.yaml"


def test_prepare_scale1_opens_only_validation_and_materializes_three_runs(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/scale1"

    campaign = prepare_campaign(
        root, manifest, config, output, "scale1", drain_horizon=5400)

    assert campaign["eligible_for_release"] is False
    assert campaign["eligible_for_test_evaluation"] is False
    assert campaign["stage"] == "scale1"
    assert len(campaign["runs"]) == 3
    identities = {(run["case_id"], run["horizon_steps"])
                  for run in campaign["runs"]}
    assert identities == {
        ("validation_normal_demand31", 3600),
        ("validation_normal_demand32", 3600),
        ("validation_normal_demand31", 5400),
    }
    for run in campaign["runs"]:
        assert run["split"] == "validation"
        assert run["controller_id"] == "fixed_time_30"
        assert run["snapshot_interval_seconds"] == 300
        assert run["scale"] == 1.0
        assert run["run_manifest_sha256"] == _sha(
            root / run["run_manifest_path"])
        assert run["demand_sha256"] == _sha(root / run["demand_path"])
    binding = campaign["binding"]
    assert len(binding["code_commit"]) == 40
    assert binding["source_manifest_sha256"] == _sha(manifest)
    assert binding["training_config_sha256"] == _sha(config)
    assert set(binding["code_sha256"]) == {
        "scripts/calibrate_haichau_capacity.py",
        "src/traffic_rl/eval/capacity_calibration.py",
    }
    assert binding["runtime"]["derived_image_tag"] == \
        "traffic-rl-cityflow-research:v2"


def test_prepare_ladder_and_stage_d_expand_only_registered_validation_runs(tmp_path):
    root, manifest, config = _project(tmp_path)
    ladder = prepare_campaign(
        root, manifest, config, root / "diagnostics/ladder", "ladder")
    assert [(run["scale"], run["case_id"], run["controller_id"])
            for run in ladder["runs"]] == [
        (0.25, "validation_normal_demand31", "fixed_time_30"),
        (0.3, "validation_normal_demand31", "fixed_time_30"),
        (0.35, "validation_normal_demand31", "fixed_time_30"),
    ]

    full = prepare_campaign(
        root, manifest, config, root / "diagnostics/stage-d", "stage-d",
        chosen_scales=[0.25, 0.3])
    assert len(full["runs"]) == 24
    assert {run["case_id"] for run in full["runs"]} == {
        "validation_%s_demand%s" % (scenario, seed)
        for scenario in ("normal", "am_peak", "pm_peak") for seed in (31, 32)
    }
    assert {run["controller_id"] for run in full["runs"]} == {
        "fixed_time_30", "max_pressure_masked_v2"}
    assert {run["scale"] for run in full["runs"]} == {0.25, 0.3}


def test_prepare_is_idempotent_but_refuses_hash_drift(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/ladder"
    first = prepare_campaign(root, manifest, config, output, "ladder")
    assert prepare_campaign(root, manifest, config, output, "ladder") == first

    config.write_text(config.read_text() + "changed: true\n")
    with pytest.raises(ValueError, match="existing campaign manifest"):
        prepare_campaign(root, manifest, config, output, "ladder")


def test_prepare_requires_diagnostic_output_and_declared_streams_per_bin(tmp_path):
    root, manifest, config = _project(tmp_path)
    with pytest.raises(ValueError, match="diagnostics"):
        prepare_campaign(root, manifest, config, root / "final", "ladder")

    payload = json.loads(manifest.read_text())
    case = next(item for item in payload["cases"]
                if item["case_id"] == "validation_normal_demand31")
    case["flow_streams"] = 2
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="stream count"):
        prepare_campaign(root, manifest, config, root / "diagnostics/bad", "ladder")


@pytest.mark.parametrize("scales", [[], [0.2], [0.25, 0.25]])
def test_stage_d_rejects_missing_unregistered_or_duplicate_scales(tmp_path, scales):
    root, manifest, config = _project(tmp_path)
    with pytest.raises(ValueError, match="chosen scales"):
        prepare_campaign(root, manifest, config, root / "diagnostics/stage-d",
                         "stage-d", chosen_scales=scales)


def _metrics(step, scheduled=100, due=100, inserted=95, arrived=56,
             running=39, pending=5, removed=0, queue=100.0):
    return {
        "observed_steps": step, "observed_seconds": step,
        "scheduled": scheduled, "due": due,
        "unreleased": scheduled - due, "inserted": inserted,
        "departed": inserted, "arrived": arrived, "running": running,
        "pending": pending, "removed": removed,
        "completion_rate": float(arrived) / scheduled,
        "insertion_rate": float(inserted) / scheduled,
        "network_queue_integral_vehicle_seconds": queue,
        "pending_integral_vehicle_seconds": 0.0,
        "queue_integral_vehicle_seconds": queue,
        "queue_integral_vehicle_hours": queue / 3600.0,
        "per_node_queue_integral_vehicle_seconds": {"A": queue},
        "per_node_max_queue": {"A": 10.0},
        "spillback_lane_seconds": {},
    }


def test_rollout_records_fixed_intervals_and_terminal_snapshot():
    class Controller(object):
        def reset(self):
            self.reset_called = True

        def act(self, context):
            assert context["waiting_counts"] == {"lane": 1}
            return {"A": 0}

    class Environment(object):
        agent_ids = ["A"]

        def __init__(self):
            self.step_number = 0

        def reset(self):
            return {"A": [0]}

        def current_waiting_counts(self):
            return {"lane": 1}

        def action_masks(self):
            return {"A": [True]}

        def step(self, actions):
            self.step_number += 100
            done = self.step_number == 500
            return ({"A": [self.step_number]}, {}, done,
                    {"step": self.step_number,
                     "network_metrics": _metrics(self.step_number)})

    terminal, snapshots = rollout_with_snapshots(
        Environment(), Controller(), snapshot_interval=300)

    assert [item["step"] for item in snapshots] == [300, 500]
    assert terminal["observed_steps"] == 500


def test_rollout_refuses_to_label_a_late_sample_as_an_exact_snapshot():
    class Controller(object):
        def reset(self):
            pass

        def act(self, context):
            return {"A": 0}

    class Environment(object):
        def __init__(self):
            self.step_number = 0

        def reset(self):
            return {"A": [0]}

        def current_waiting_counts(self):
            return {}

        def action_masks(self):
            return {"A": [True]}

        def step(self, actions):
            self.step_number += 200
            return ({"A": [self.step_number]}, {}, self.step_number == 400,
                    {"step": self.step_number,
                     "network_metrics": _metrics(self.step_number)})

    with pytest.raises(ValueError, match="exact snapshot"):
        rollout_with_snapshots(
            Environment(), Controller(), snapshot_interval=300)


def test_normal_and_drain_gates_use_pre_registered_thresholds():
    normal_run = {
        "scenario": "normal", "horizon_steps": 3600,
        "scheduled_vehicles": 100,
        "free_flow_eligible_by_snapshot": {"3600": 80},
    }
    normal = evaluate_run_gates(
        normal_run, [{"step": 3600, "metrics": _metrics(3600)}])
    assert normal["passed"] is True
    assert normal["values"]["free_flow_eligible_completion"] == 0.7

    drain_run = dict(normal_run, horizon_steps=5400)
    drain_run["free_flow_eligible_by_snapshot"] = {"3600": 80, "5400": 100}
    snapshots = [
        {"step": 3600, "metrics": _metrics(3600)},
        {"step": 5400, "metrics": _metrics(
            5400, inserted=99, arrived=90, running=9, pending=1)},
    ]
    drain = evaluate_run_gates(drain_run, snapshots)
    assert drain["passed"] is True
    assert drain["checks"]["drain_completion"]["threshold"] == 0.90


def test_run_gates_fail_closed_on_accounting_or_operating_threshold_failure():
    run = {"scenario": "normal", "horizon_steps": 3600,
           "scheduled_vehicles": 100,
           "free_flow_eligible_by_snapshot": {"3600": 80}}
    bad = _metrics(3600, inserted=94, arrived=55, running=39, pending=6)
    result = evaluate_run_gates(run, [{"step": 3600, "metrics": bad}])
    assert result["passed"] is False
    assert result["checks"]["normal_insertion_rate"]["passed"] is False
    assert result["checks"]["normal_pending_rate"]["passed"] is False
    assert result["checks"]["normal_free_flow_completion"]["passed"] is False

    impossible = dict(bad, inserted=95, departed=95)
    with pytest.raises(ValueError, match=r"due = inserted \+ pending"):
        evaluate_run_gates(run, [{"step": 3600, "metrics": impossible}])


def test_run_gates_require_metrics_observed_at_the_declared_snapshot_step():
    run = {"scenario": "normal", "horizon_steps": 3600,
           "scheduled_vehicles": 100,
           "free_flow_eligible_by_snapshot": {"3600": 80}}
    metrics = _metrics(3599)

    with pytest.raises(ValueError, match="observed_steps"):
        evaluate_run_gates(run, [{"step": 3600, "metrics": metrics}])


def _stage_d_result(run, queue, completion, insertion=0.95):
    scheduled = 100
    inserted = int(insertion * scheduled)
    arrived = int(completion * scheduled)
    pending = scheduled - inserted
    running = inserted - arrived
    metrics = _metrics(3600, scheduled=scheduled, inserted=inserted,
                       arrived=arrived, running=running, pending=pending,
                       queue=queue)
    snapshot = {"step": 3600, "metrics": metrics}
    enriched = dict(run)
    enriched["scheduled_vehicles"] = scheduled
    enriched["free_flow_eligible_by_snapshot"] = {"3600": 100}
    return {"run": enriched, "metrics": metrics, "snapshots": [snapshot],
            "gates": evaluate_run_gates(enriched, [snapshot])}


def test_stage_d_gate_requires_pm_queue_and_completion_ordering_for_each_controller():
    runs = []
    results = []
    for controller in ("fixed_time_30", "max_pressure_masked_v2"):
        for scenario in ("normal", "am_peak", "pm_peak"):
            for seed in (31, 32):
                run = {"run_id": "%s-%s-%s" % (controller, scenario, seed),
                       "scale": 0.3, "controller_id": controller,
                       "scenario": scenario, "horizon_steps": 3600}
                runs.append(run)
                queue = 200.0 if scenario == "pm_peak" else 100.0
                completion = 0.6 if scenario == "pm_peak" else 0.7
                results.append(_stage_d_result(run, queue, completion))
    campaign = {"stage": "stage-d", "chosen_scales": [0.3], "runs": runs}

    gate = evaluate_stage_gates(campaign, results)
    assert gate["complete"] is True
    assert gate["scales"]["0.3"]["passed"] is True
    assert gate["highest_passing_scale"] == 0.3

    for result in results:
        if result["run"]["scenario"] == "pm_peak":
            result["metrics"]["queue_integral_vehicle_seconds"] = 50.0
    failed = evaluate_stage_gates(campaign, results)
    assert failed["scales"]["0.3"]["passed"] is False


def _successful_executor(project_root, run, run_dir):
    eligible = run["free_flow_eligible_by_snapshot"][str(run["horizon_steps"])]
    scheduled = run["scheduled_vehicles"]
    metrics = _metrics(
        run["horizon_steps"], scheduled=scheduled, due=scheduled,
        inserted=scheduled, arrived=eligible, running=scheduled - eligible,
        pending=0, queue=100.0)
    return metrics, [{"step": run["horizon_steps"], "metrics": metrics}]


def test_execution_preserves_completed_runs_and_resumes_failed_runs(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/ladder"
    prepare_campaign(root, manifest, config, output, "ladder")
    calls = []

    def fail_second(project_root, run, run_dir):
        calls.append(run["run_id"])
        if len(calls) == 2:
            raise RuntimeError("interrupted")
        return _successful_executor(project_root, run, run_dir)

    first = execute_campaign(root, output, run_executor=fail_second)
    assert first["status"] == "diagnostic_partial"
    assert first["completed"] == 2
    assert first["failed"] == 1

    calls[:] = []
    resumed = execute_campaign(root, output, run_executor=lambda *args: (
        calls.append(args[1]["run_id"]) or _successful_executor(*args)))
    assert resumed["status"] == "diagnostic_complete"
    assert resumed["completed"] == 3
    assert resumed["failed"] == 0
    assert len(calls) == 1


def test_execution_refuses_changed_completed_result(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/ladder"
    campaign = prepare_campaign(root, manifest, config, output, "ladder")
    execute_campaign(root, output, run_executor=_successful_executor)
    first = campaign["runs"][0]
    result_path = output / "runs" / first["run_id"] / "result.json"
    result_path.write_text("{}\n")

    with pytest.raises(ValueError, match="completed result sha256"):
        execute_campaign(root, output, run_executor=_successful_executor)


def test_execution_refuses_changed_bound_runtime_dockerfile(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/ladder"
    prepare_campaign(root, manifest, config, output, "ladder")
    (root / "inputs/Dockerfile").write_text("FROM changed@sha256:test\n")

    with pytest.raises(ValueError, match="runtime Dockerfile sha256 mismatch"):
        execute_campaign(root, output, run_executor=_successful_executor)


def test_execution_rejects_terminal_metrics_that_differ_from_terminal_snapshot(tmp_path):
    root, manifest, config = _project(tmp_path)
    output = root / "diagnostics/ladder"
    prepare_campaign(root, manifest, config, output, "ladder")

    def inconsistent(project_root, run, run_dir):
        metrics, snapshots = _successful_executor(project_root, run, run_dir)
        changed = dict(metrics)
        changed["queue_integral_vehicle_seconds"] += 1
        return changed, snapshots

    summary = execute_campaign(root, output, run_executor=inconsistent)
    assert summary["completed"] == 0
    assert summary["failed"] == 3
