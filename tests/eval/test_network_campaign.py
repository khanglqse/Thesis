import json
from pathlib import Path

import pytest

from traffic_rl.eval.network_campaign import expand_runs, run_pending


def _manifest():
    return {
        "protocol_version": 2,
        "network_sha256": "a" * 64,
        "runtime_digest": "sha256:" + "b" * 64,
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
    return {
        "resolved_config": {"case_id": run["case_id"]},
        "metrics": {
            "case_id": run["case_id"],
            "controller_id": run["controller_id"],
            "completed_steps": run["horizon_steps"],
            "queue_integral_vehicle_seconds": 123.0,
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


def test_resume_rechecks_hash_before_skipping(tmp_path):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    _write_campaign(tmp_path, runs)
    first = run_pending(tmp_path, _executor)
    assert first == {"completed": 2, "failed": 0, "skipped": 0, "total": 2}

    metrics_path = tmp_path / "runs" / runs[0]["run_id"] / "metrics.json"
    metrics_path.write_text("corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_pending(tmp_path, _executor)


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
