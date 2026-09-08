import json

from scripts import train_haichau_network
from scripts.train_haichau_network import _pilot_profile


def test_env_factory_wires_fresh_network_metrics_observer(monkeypatch, tmp_path):
    class FakeRoadNet(object):
        def signalized_ids(self):
            return ["signal-a", "signal-b"]

        def incoming_lanes(self, node_id):
            return {"signal-a": ["lane-a0", "lane-a1"],
                    "signal-b": ["lane-b0"]}[node_id]

    captured = []

    class FakeEnv(object):
        def __init__(self, *args, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(train_haichau_network.RoadNet, "load",
                        lambda *args, **kwargs: FakeRoadNet())
    monkeypatch.setattr(train_haichau_network, "PhaseFeatureEncoder",
                        lambda *args, **kwargs: object())
    monkeypatch.setattr(train_haichau_network, "CityFlowEngine",
                        lambda *args, **kwargs: object())
    monkeypatch.setattr(train_haichau_network, "MultiAgentTrafficEnv", FakeEnv)
    manifest = {
        "network": {"path": "network.json"},
        "phase_contract": {"path": "phases.json", "sha256": "a" * 64},
        "preprocessing": {"count_norm": 20, "capacity_norm": 12},
        "simulation": {"action_interval": 10, "yellow_time": 3,
                       "min_green": 10, "maximum_red": 120},
    }
    resolved = {"reward": {"queue_weight": 1.0,
                           "downstream_block_weight": 0.2,
                           "switch_penalty": 0.05}}
    factory = train_haichau_network._make_env_factory(
        manifest, resolved, tmp_path, "neighbor_phase_ddqn")
    case = {"case_id": "validation_normal_demand31", "sim_seed": 311,
            "flow_path": "flow.json", "scheduled_vehicles": 7509}

    factory(case, 3600)
    factory(case, 3600)

    first = captured[0]["network_metric_observer"]
    second = captured[1]["network_metric_observer"]
    assert first is not second
    assert first.scheduled_vehicles == 7509
    assert first.step_seconds == 1.0
    assert first.lane_to_node == {
        "lane-a0": "signal-a", "lane-a1": "signal-a", "lane-b0": "signal-b"}
    assert first.spillback_thresholds == {
        "lane-a0": 12.0, "lane-a1": 12.0, "lane-b0": 12.0}


def test_makefile_exposes_all_pinned_training_modes():
    makefile = open("Makefile").read()
    for mode in ("smoke", "pilot", "final"):
        assert "haichau-train-%s: haichau-foundation-verify" % mode in makefile
        assert "--mode %s --learning-seed $(LEARNING_SEED)" % mode in makefile
        assert "haichau-train-legacy-%s: haichau-foundation-verify" % mode in makefile
    assert "--controller-family shared_ddqn_legacy" in makefile


def test_five_seed_projection_uses_end_to_end_wall_time():
    summary = {
        "wall_time_seconds": 120.0,
        "baseline_tuning_wall_time_seconds": 80.0,
        "simulated_seconds_per_second": 2.0,
        "updates_per_second": 3.0,
        "validation_wall_time_seconds": 20.0,
    }

    profile = _pilot_profile(summary, learning_seed=11, peak_rss_kb=1000,
                             source_summary="summary.json")

    assert profile["measured_end_to_end_wall_time_seconds"] == 120.0
    assert profile["baseline_tuning_wall_time_seconds"] == 80.0
    assert profile["projected_five_seed_campaign_seconds"] == 600.0


def test_cli_passes_precomputed_baseline_artifact_to_trainer(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"simulation": {"action_interval": 10}}))
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 2\ntiers:\n  final: {episodes: 1, horizon_seconds: 20, eval_every: 1}\n")
    cache = tmp_path / "baseline-tuning.json"
    cache.write_text("{}")
    captured = {}
    monkeypatch.setattr(train_haichau_network, "_make_env_factory",
                        lambda *args: "fake-env-factory")

    def fake_train(*args, **kwargs):
        captured["artifact"] = kwargs["baseline_tuning_artifact"]
        return {"status": "complete"}

    monkeypatch.setattr(train_haichau_network, "train_network", fake_train)

    result = train_haichau_network.main([
        "--mode", "final", "--learning-seed", "11",
        "--manifest", str(manifest), "--config", str(config),
        "--output", str(tmp_path / "run"),
        "--baseline-tuning-artifact", str(cache),
    ])

    assert result == 0
    assert captured["artifact"] == str(cache)


def test_cli_can_precompute_baseline_artifact_once(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"simulation": {"action_interval": 10}}))
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 2\ntiers:\n  final: {episodes: 1, horizon_seconds: 20, eval_every: 1}\n")
    cache = tmp_path / "precomputed-baseline.json"
    captured = {}
    monkeypatch.setattr(train_haichau_network, "_make_env_factory",
                        lambda *args: "fake-env-factory")

    def fake_precompute(factory, loaded_manifest, resolved, artifact_path,
                        foundation_root=None):
        captured["factory"] = factory
        captured["artifact_path"] = artifact_path
        return {"tuning_sha256": "a" * 64}

    monkeypatch.setattr(train_haichau_network, "precompute_baseline_tuning",
                        fake_precompute)

    result = train_haichau_network.main([
        "--mode", "final", "--learning-seed", "11",
        "--manifest", str(manifest), "--config", str(config),
        "--precompute-baseline-tuning", str(cache),
    ])

    assert result == 0
    assert captured == {"factory": "fake-env-factory", "artifact_path": str(cache)}
