import hashlib
import json

import pytest

from scripts.export_haichau_replays import export_bundle
from traffic_rl.eval.network_campaign import expand_runs, run_pending


def _network():
    nodes = [
        {"id": "N%02d" % index, "x": index % 9, "y": index // 9,
         "neighbors": (["N%02d" % (index - 1)] if index else [])}
        for index in range(53)
    ]
    return {
        "network_id": "haichau-test-fixture",
        "controlled_signals": 53,
        "nodes": nodes,
        "links": [
            {"source": "N%02d" % index, "target": "N%02d" % (index + 1)}
            for index in range(52)
        ],
    }


def _campaign(tmp_path, wrong_replay_metric=False):
    manifest = {
        "protocol_version": 2,
        "network_sha256": "a" * 64,
        "runtime_digest": "sha256:" + "b" * 64,
        "default_horizon_steps": 10,
        "cases": [{
            "case_id": "test-normal-101", "split": "test", "regime": "normal",
            "demand_seed": 101, "simulator_seed": 201,
            "demand_sha256": "c" * 64,
        }],
    }
    runs = expand_runs(
        manifest, [11], ["tuned_fixed", "neighbor_phase_ddqn"])
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    (campaign_dir / "campaign-manifest.json").write_text(json.dumps({
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }))

    def executor(run, run_dir):
        queue = 100.0 if run["controller_id"] == "tuned_fixed" else 90.0
        replay_queue = queue + 1 if wrong_replay_metric else queue
        nodes = {"N%02d" % index: {"queue": index % 7, "phase": index % 3}
                 for index in range(53)}
        return {
            "resolved_config": {"case_id": run["case_id"]},
            "metrics": {
                "case_id": run["case_id"],
                "controller_id": run["controller_id"],
                "completed_steps": 10,
                "queue_integral_vehicle_seconds": queue,
                "completion_rate": 0.95,
                "fresh_evaluation": True,
            },
            "replay": {
                "sample_seconds": 5,
                "frames": [
                    {"t": 0, "nodes": nodes, "vehicles": []},
                    {"t": 5, "nodes": nodes, "vehicles": []},
                    {"t": 10, "nodes": nodes, "vehicles": []},
                ],
                "metrics": {
                    "queue_integral_vehicle_seconds": replay_queue,
                    "completion_rate": 0.95,
                },
            },
            "stdout": "",
            "stderr": "",
        }

    assert run_pending(campaign_dir, executor)["failed"] == 0
    (campaign_dir / "summary.json").write_text(json.dumps({
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
        },
        "summary": {},
        "acceptance": {"accepted": False},
    }))
    return campaign_dir, runs


def test_export_reproduces_run_metrics_and_hashes_every_path(tmp_path):
    campaign_dir, runs = _campaign(tmp_path)
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    output = tmp_path / "demo"

    manifest = export_bundle(
        campaign_dir, output, network_path,
        selected_run_ids=[run["run_id"] for run in runs],
    )

    assert manifest["controlled_signals"] == 53
    assert manifest["demand_label"] == (
        "synthetic network demand constrained by Da Nang evidence")
    assert len(manifest["replays"]) == 2
    for relative, expected in manifest["files"].items():
        payload = (output / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected
    exported = json.loads(
        (output / manifest["replays"][0]["path"]).read_text())
    original = json.loads(
        (campaign_dir / "runs" / manifest["replays"][0]["run_id"] /
         "metrics.json").read_text())
    assert exported["metrics"]["queue_integral_vehicle_seconds"] == (
        original["queue_integral_vehicle_seconds"])


def test_export_rejects_replay_metric_drift(tmp_path):
    campaign_dir, runs = _campaign(tmp_path, wrong_replay_metric=True)
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    with pytest.raises(ValueError, match="replay metric mismatch"):
        export_bundle(
            campaign_dir, tmp_path / "demo", network_path,
            selected_run_ids=[run["run_id"] for run in runs],
        )

