import hashlib
import json

import pytest

from scripts.export_haichau_replays import export_bundle
from traffic_rl.eval.network_campaign import CONTROLLERS, expand_runs, run_pending
from traffic_rl.eval.network_replay import validate_network


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _campaign(tmp_path, network_sha256, wrong_replay_metric=False,
              replay_times=(0, 5, 10)):
    agent_ids = ["N%02d" % index for index in range(53)]
    manifest = {
        "protocol_version": 2,
        "network_sha256": network_sha256,
        "viewer_network_sha256": network_sha256,
        "phase_contract_sha256": "e" * 64,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "runtime_digest": "sha256:" + "b" * 64,
        "runtime_image": "cityflowproject/cityflow@sha256:" + "b" * 64,
        "runtime_image_id": "sha256:" + "b" * 64,
        "runtime_dockerfile_path": "docker/haichau-evaluation.Dockerfile",
        "runtime_dockerfile_sha256": "d" * 64,
        "code_commit": "1" * 40,
        "controlled_signals": 53,
        "agent_ids": agent_ids,
        "default_horizon_steps": 10,
        "resolved_config": {
            "network_path": "roadnet.json",
            "phase_contract_path": "phase-contract.json",
            "phase_contract_sha256": "e" * 64,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {
                "action_interval": 10, "yellow_time": 3,
                "min_green": 20, "maximum_red": 180,
            },
            "reward": {
                "queue_weight": 1.0, "downstream_block_weight": 0.1,
                "switch_penalty": 0.05,
            },
        },
        "controller_configs": {
            "tuned_fixed": {"green_duration": 30},
            "max_pressure": {"controller_version": 2},
            "hysteretic_mp": {
                "min_hold_decisions": 3, "switch_threshold": 2.5,
            },
            "shared_ddqn_legacy": {"controller_version": 2},
            "neighbor_phase_ddqn": {"controller_version": 2},
        },
        "controller_commands": dict(
            (controller, ["python3", "scripts/evaluate_haichau_network.py"])
            for controller in CONTROLLERS),
        "cases": [{
            "case_id": "test-normal-101", "split": "test", "regime": "normal",
            "demand_seed": 101, "simulator_seed": 201,
            "scheduled_vehicles": 1000,
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
        per_node = dict((node_id, 0.0) for node_id in agent_ids)
        metrics = {
                "case_id": run["case_id"],
                "regime": run["regime"],
                "controller_id": run["controller_id"],
                "learning_seed": run["learning_seed"],
                "demand_seed": run["demand_seed"],
                "simulator_seed": run["simulator_seed"],
                "scheduled_vehicles": run["scheduled_vehicles"],
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
                "completed_steps": 10,
                "observed_steps": 10,
                "observed_seconds": 10,
                "queue_integral_vehicle_seconds": queue,
                "network_queue_integral_vehicle_seconds": queue,
                "queue_integral_vehicle_hours": queue / 3600,
                "pending_integral_vehicle_seconds": 0.0,
                "per_node_queue_integral_vehicle_seconds": per_node,
                "per_node_max_queue": per_node,
                "spillback_lane_seconds": {},
                "scheduled": run["scheduled_vehicles"],
                "inserted": 0, "departed": 0,
                "arrived": 0, "running": 0,
                "pending": run["scheduled_vehicles"], "removed": 0,
                "censored_or_unfinished": run["scheduled_vehicles"],
                "completion_denominator": "scheduled",
                "completion_rate": 0.0,
                "insertion_rate": 0.0,
                "completed_travel_time_count": 0,
                "phase_switches": 0,
                "intergreen_seconds": 0.0,
                "max_red_seconds": 0.0,
                "travel_time_completed_mean": None,
                "travel_time_completed_median": None,
                "travel_time_completed_p95": None,
                "fresh_evaluation": True,
        }
        return {
            "resolved_config": run["resolved_config"],
            "metrics": metrics,
            "replay": {
                "sample_seconds": 5,
                "frames": [
                    {"t": value, "nodes": nodes, "vehicles": []}
                    for value in replay_times
                ],
                "metrics": {
                    "queue_integral_vehicle_seconds": replay_queue,
                    "completion_rate": 0.0,
                    "arrived": 0,
                    "running": 0,
                    "pending": run["scheduled_vehicles"],
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
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    campaign_dir, runs = _campaign(tmp_path, _digest(network_path))
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
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    campaign_dir, runs = _campaign(
        tmp_path, _digest(network_path), wrong_replay_metric=True)
    with pytest.raises(ValueError, match="replay metric mismatch"):
        export_bundle(
            campaign_dir, tmp_path / "demo", network_path,
            selected_run_ids=[run["run_id"] for run in runs],
        )


def test_export_rejects_network_unrelated_to_campaign(tmp_path):
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    campaign_dir, runs = _campaign(tmp_path, "a" * 64)

    with pytest.raises(ValueError, match="network hash"):
        export_bundle(
            campaign_dir, tmp_path / "demo", network_path,
            selected_run_ids=[run["run_id"] for run in runs],
        )


def test_export_rejects_replay_that_does_not_cover_full_horizon(tmp_path):
    network_path = tmp_path / "network.json"
    network_path.write_text(json.dumps(_network()))
    campaign_dir, runs = _campaign(
        tmp_path, _digest(network_path), replay_times=(0,))

    with pytest.raises(ValueError, match="full horizon"):
        export_bundle(
            campaign_dir, tmp_path / "demo", network_path,
            selected_run_ids=[run["run_id"] for run in runs],
        )


@pytest.mark.parametrize("mutation, message", [
    (lambda network: network["nodes"][0].pop("x"), "finite x/y"),
    (lambda network: network["nodes"][0].update({"x": float("nan")}),
     "finite x/y"),
    (lambda network: network["nodes"][0].pop("neighbors"), "neighbor list"),
    (lambda network: network["nodes"][0].update({"neighbors": "N01"}),
     "neighbor list"),
    (lambda network: network["nodes"][0].update({"neighbors": ["missing"]}),
     "unknown neighbor"),
])
def test_network_contract_rejects_unusable_viewer_topology(mutation, message):
    network = _network()
    mutation(network)

    with pytest.raises(ValueError, match=message):
        validate_network(network)
