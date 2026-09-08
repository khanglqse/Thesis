import json
from pathlib import Path

import pytest

from traffic_rl.eval.network_campaign import expand_runs, run_pending, verify_campaign


def _manifest():
    return {
        "protocol_version": 2,
        "network_sha256": "a" * 64,
        "viewer_network_sha256": "a" * 64,
        "runtime_digest": "sha256:" + "b" * 64,
        "runtime_image": "cityflowproject/cityflow@sha256:" + "b" * 64,
        "runtime_image_id": "sha256:" + "b" * 64,
        "runtime_dockerfile_path": "docker/haichau-evaluation.Dockerfile",
        "runtime_dockerfile_sha256": "e" * 64,
        "code_commit": "1" * 40,
        "controlled_signals": 53,
        "agent_ids": ["N%02d" % index for index in range(53)],
        "default_horizon_steps": 3600,
        "cases": [
            {
                "case_id": "test-normal-101",
                "split": "test",
                "regime": "normal",
                "demand_seed": 101,
                "simulator_seed": 201,
                "demand_sha256": "c" * 64,
            },
            {
                "case_id": "test-pm-102",
                "split": "test",
                "regime": "pm_peak",
                "demand_seed": 102,
                "simulator_seed": 202,
                "demand_sha256": "d" * 64,
            },
            {
                "case_id": "train-normal-1",
                "split": "train",
                "regime": "normal",
                "demand_seed": 1,
                "simulator_seed": 1,
                "demand_sha256": "e" * 64,
            },
        ],
    }


def _write_campaign(path, runs):
    path.mkdir(parents=True, exist_ok=True)
    (path / "campaign-manifest.json").write_text(json.dumps({
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }))


def _executor(run, run_dir):
    nodes = dict((node_id, 0.0) for node_id in run["agent_ids"])
    return {
        "resolved_config": run["resolved_config"],
        "metrics": {
            "case_id": run["case_id"],
            "regime": run["regime"],
            "controller_id": run["controller_id"],
            "learning_seed": run["learning_seed"],
            "demand_seed": run["demand_seed"],
            "simulator_seed": run["simulator_seed"],
            "network_sha256": run["network_sha256"],
            "viewer_network_sha256": run["viewer_network_sha256"],
            "demand_sha256": run["demand_sha256"],
            "demand_path": run["demand_path"],
            "runtime_digest": run["runtime_digest"],
            "runtime_image": run["runtime_image"],
            "runtime_image_id": run["runtime_image_id"],
            "runtime_dockerfile_path": run["runtime_dockerfile_path"],
            "runtime_dockerfile_sha256": run["runtime_dockerfile_sha256"],
            "code_commit": run["code_commit"],
            "checkpoint_sha256": run.get("checkpoint_sha256"),
            "checkpoint_contract_sha256": run.get("checkpoint_contract_sha256"),
            "completed_steps": run["horizon_steps"],
            "observed_steps": run["horizon_steps"],
            "observed_seconds": run["horizon_steps"],
            "queue_integral_vehicle_seconds": 123.0,
            "queue_integral_vehicle_hours": 123.0 / 3600,
            "pending_integral_vehicle_seconds": 0.0,
            "per_node_queue_integral_vehicle_seconds": nodes,
            "per_node_max_queue": nodes,
            "spillback_lane_seconds": {},
            "scheduled": 0,
            "inserted": 0,
            "departed": 0,
            "arrived": 0,
            "running": 0,
            "pending": 0,
            "removed": 0,
            "censored_or_unfinished": 0,
            "completion_denominator": "scheduled",
            "completion_rate": None,
            "insertion_rate": None,
            "completed_travel_time_count": 0,
            "phase_switches": 0,
            "intergreen_seconds": 0.0,
            "max_red_seconds": 0.0,
            "travel_time_completed_mean": None,
            "travel_time_completed_median": None,
            "travel_time_completed_p95": None,
            "fresh_evaluation": True,
        },
        "stdout": "fresh run\n",
        "stderr": "",
    }


def test_deterministic_baseline_is_not_multiplied_by_learning_seed():
    runs = expand_runs(_manifest(), [11, 12, 13, 14, 15], ["tuned_fixed"])
    assert len(runs) == 2
    assert all(run["learning_seed"] is None for run in runs)


def test_learning_controller_crosses_test_cases_with_learning_seeds():
    runs = expand_runs(
        _manifest(), [11, 12], ["tuned_fixed", "neighbor_phase_ddqn"])
    assert len(runs) == 6
    learned = [run for run in runs
               if run["controller_id"] == "neighbor_phase_ddqn"]
    assert {run["learning_seed"] for run in learned} == {11, 12}
    assert all(run["fresh_evaluation"] is True for run in runs)
    assert all(run["evidence_namespace"] == "haichau_network_v2" for run in runs)


def test_expansion_requires_frozen_code_and_runtime_identity():
    manifest = _manifest()
    manifest.pop("code_commit")
    with pytest.raises(ValueError, match="code_commit"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expanded_run_freezes_resolved_config_and_checkpoint_contract():
    manifest = _manifest()
    manifest["controller_configs"] = {
        "neighbor_phase_ddqn": {"gamma": 0.95, "hidden_size": 64},
    }
    manifest["checkpoints"] = [{
        "controller_id": "neighbor_phase_ddqn",
        "learning_seed": 11,
        "path": "checkpoints/seed-11.npz",
        "sha256": "f" * 64,
        "checkpoint_contract": {"obs_schema_version": 2},
    }]

    run = expand_runs(manifest, [11], ["neighbor_phase_ddqn"])[0]

    assert run["resolved_config"]["gamma"] == 0.95
    assert run["resolved_config"]["simulator_seed"] == 201
    assert run["checkpoint_sha256"] == "f" * 64
    assert len(run["checkpoint_contract_sha256"]) == 64
    assert run["code_commit"] == "1" * 40
    assert run["resolved_config"]["code_commit"] == "1" * 40
    assert run["runtime_image"].endswith(run["runtime_digest"])


def test_resume_rechecks_hash_before_skipping(tmp_path):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    _write_campaign(tmp_path, runs)
    first = run_pending(tmp_path, _executor)
    assert first == {"completed": 2, "failed": 0, "skipped": 0, "total": 2}

    metrics_path = tmp_path / "runs" / runs[0]["run_id"] / "metrics.json"
    metrics_path.write_text("corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_pending(tmp_path, _executor)


def test_resume_and_verify_reject_relabelled_complete_run(tmp_path):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    _write_campaign(tmp_path, runs)
    assert run_pending(tmp_path, _executor)["completed"] == 2

    runs[0]["demand_sha256"] = "9" * 64
    runs[0]["simulator_seed"] = 999
    _write_campaign(tmp_path, runs)

    with pytest.raises(ValueError, match="run spec"):
        run_pending(tmp_path, _executor)
    with pytest.raises(ValueError, match="run spec"):
        verify_campaign(tmp_path)


def test_completed_run_status_binds_code_and_runtime_identity(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])
    assert run_pending(tmp_path, _executor)["completed"] == 1

    status_path = tmp_path / "runs" / run["run_id"] / "status.json"
    status = json.loads(status_path.read_text())
    assert status["code_commit"] == run["code_commit"]
    assert status["runtime_image"] == run["runtime_image"]
    assert status["runtime_image_id"] == run["runtime_image_id"]

    status["code_commit"] = "2" * 40
    status_path.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="status code/runtime identity"):
        verify_campaign(tmp_path)


def test_incomplete_network_metric_schema_is_never_marked_complete(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def incomplete_executor(run, run_dir):
        return {
            "resolved_config": run["resolved_config"],
            "metrics": {
                "case_id": run["case_id"],
                "regime": run["regime"],
                "controller_id": run["controller_id"],
                "learning_seed": run["learning_seed"],
                "demand_seed": run["demand_seed"],
                "simulator_seed": run["simulator_seed"],
                "network_sha256": run["network_sha256"],
                "viewer_network_sha256": run["viewer_network_sha256"],
                "demand_sha256": run["demand_sha256"],
                "demand_path": run["demand_path"],
                "runtime_digest": run["runtime_digest"],
                "runtime_image": run["runtime_image"],
                "runtime_image_id": run["runtime_image_id"],
                "runtime_dockerfile_path": run["runtime_dockerfile_path"],
                "runtime_dockerfile_sha256": run["runtime_dockerfile_sha256"],
                "code_commit": run["code_commit"],
                "checkpoint_sha256": run.get("checkpoint_sha256"),
                "checkpoint_contract_sha256": run.get(
                    "checkpoint_contract_sha256"),
                "completed_steps": run["horizon_steps"],
                "fresh_evaluation": True,
            },
        }

    result = run_pending(tmp_path, incomplete_executor)

    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["status"] == "failed"
    assert "network metric" in status["error"]


def test_incomplete_run_is_rebuilt_and_only_then_marked_complete(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])
    stale = tmp_path / "runs" / run["run_id"]
    stale.mkdir(parents=True)
    (stale / "status.json").write_text(json.dumps({"status": "running"}))
    (stale / "metrics.json").write_text("stale")

    result = run_pending(tmp_path, _executor)

    assert result["completed"] == 1
    status = json.loads((stale / "status.json").read_text())
    assert status["status"] == "complete"
    assert set(status["artifact_sha256"]) == {
        "run-manifest.json", "resolved-config.json", "metrics.json",
        "stdout.log", "stderr.log",
    }
    assert json.loads((stale / "metrics.json").read_text())["fresh_evaluation"] is True


@pytest.mark.parametrize("values", [(-1.0, 1.0, 1.0), (2.0, 3.0, 2.0)])
def test_invalid_completed_travel_aggregates_are_never_complete(tmp_path, values):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def invalid_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"].update({
            "scheduled": 1, "inserted": 1, "departed": 1, "arrived": 1,
            "completed_travel_time_count": 1, "completion_rate": 1.0,
            "insertion_rate": 1.0,
            "travel_time_completed_mean": values[0],
            "travel_time_completed_median": values[1],
            "travel_time_completed_p95": values[2],
        })
        return result

    assert run_pending(tmp_path, invalid_executor)["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert "travel-time" in status["error"]


def test_horizon_mismatch_records_failure_without_complete_status(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])

    def short_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"]["completed_steps"] -= 1
        return result

    result = run_pending(tmp_path, short_executor)

    assert result == {"completed": 0, "failed": 1, "skipped": 0, "total": 1}
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["status"] == "failed"
    assert "horizon" in status["error"]


def test_campaign_rejects_legacy_source_rows(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def legacy_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"]["source_run_dir"] = "results/haichau_rush/evaluation"
        return result

    result = run_pending(tmp_path, legacy_executor)
    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert "legacy" in status["error"]


def test_executor_replay_is_part_of_the_immutable_hash_set(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])

    def replay_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["replay"] = {
            "sample_seconds": 5,
            "frames": [{"t": 0, "nodes": {}}, {"t": 5, "nodes": {}}],
            "metrics": {"queue_integral_vehicle_seconds": 123.0},
        }
        return result

    assert run_pending(tmp_path, replay_executor)["completed"] == 1
    run_dir = tmp_path / "runs" / run["run_id"]
    status = json.loads((run_dir / "status.json").read_text())
    assert "replay.json" in status["artifact_sha256"]
    assert (run_dir / "replay.json").is_file()
