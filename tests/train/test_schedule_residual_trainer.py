import json

import numpy as np
import pytest

from traffic_rl.agents.schedule_residual import MACRO_FEATURES, CRITIC_UNITS, ResidualDDQN
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder
from traffic_rl.sim.schedule_residual import EmptySignalEngine, _NodeRoadnet
from traffic_rl.train.schedule_residual_trainer import (
    run_macro_episode, training_cases, validate_config, train_residual,
    operational_time_of_day, OPERATIONAL_MODE)
from tests.sim.test_schedule_residual import network, representative


def test_training_selection_uses_only_declared_peak_training_cases():
    cases = [{"case_id": "misleading-normal-name", "scenario": "am_peak", "split": "train"},
             {"case_id": "p", "scenario": "pm_peak", "split": "train"},
             {"case_id": "forbidden", "scenario": "am_peak", "split": "test"},
             {"case_id": "n", "scenario": "normal", "split": "train"},
             {"case_id": "v", "scenario": "am_peak", "split": "validation"}]
    assert [x["case_id"] for x in training_cases({"cases": cases})] == ["misleading-normal-name", "p"]


def test_preregistered_pilot_config_rejects_protocol_drift():
    config = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
              "macro": {"duration_seconds": 300, "shift_seconds": 10, "baseline_green_seconds": 25},
              "mode": "pilot", "learning_seed": 11,
              "operational_mode": OPERATIONAL_MODE,
              "critic_units": CRITIC_UNITS,
              "run": {"episodes": 4, "horizon_seconds": 3600, "eval_every": 2},
              "reward": {"type": "negative_network_queue_plus_pending_integral"}}
    validate_config(config)
    config["run"]["horizon_seconds"] = 600
    with pytest.raises(ValueError, match="pilot"):
        validate_config(config)


def test_native_macro_episode_records_exact_reward_and_terminal_no_bootstrap(network):
    roadnet = _NodeRoadnet(network, representative(network, 2))

    class QueueEngine(EmptySignalEngine):
        def lane_waiting_counts(self):
            return {"outside_signal_projection": 3}

    env = MultiAgentTrafficEnv(roadnet, QueueEngine(), max_steps=600, min_green=20,
                               encoder=PhaseFeatureEncoder(roadnet, 20, 40))
    net = ResidualDDQN(len(MACRO_FEATURES), 8, .001, 5)
    transitions = []
    result = run_macro_episode(env, net, "am_peak", epsilon=0.0,
                               transition_callback=transitions.append)
    assert len(transitions) == 2
    assert [x["reward"] for x in transitions] == [-900, -900]
    assert [x["raw_objective_vehicle_seconds"] for x in transitions] == [900, 900]
    assert [x["scaled_reward"] for x in transitions] == [-.009, -.009]
    assert [x["duration_seconds"] for x in transitions] == [300, 300]
    assert [x["done"] for x in transitions] == [False, True]
    assert np.count_nonzero(transitions[-1]["next_features"]) == 0
    assert transitions[-1]["next_mask"].tolist() == [True] + [False] * 58
    assert result["policy_audit"]["anchor_violations"] == 0
    assert result["queue_integral_vehicle_seconds"] == 1800


def test_smoke_artifacts_bind_checkpoints_and_never_open_test_cases(network, tmp_path, monkeypatch):
    import traffic_rl.train.schedule_residual_trainer as trainer
    from traffic_rl.train.network_trainer import _tuning_binding, canonical_json_sha256

    node = representative(network, 2)
    roadnet = _NodeRoadnet(network, node)
    cases = [{"case_id": split + "_" + scenario + str(seed), "split": split,
              "scenario": scenario, "flow_sha256": scenario + str(seed)}
             for split, seeds in (("train", [11]), ("validation", [31, 32]), ("test", [101]))
             for scenario in ("normal", "am_peak", "pm_peak") for seed in seeds]
    manifest = {"cases": cases, "network": {"agent_ids": [node], "sha256": "network"},
                "phase_contract": {"sha256": "phase"}, "runtime": {"base_image_digest": "runtime"},
                "preprocessing": {"count_norm": 20, "capacity_norm": 40},
                "simulation": {"action_interval": 10, "min_green": 20, "maximum_red": 180},
                "generator_config_sha256": "generator"}
    config = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
              "macro": {"duration_seconds": 300, "shift_seconds": 10, "baseline_green_seconds": 25},
              "mode": "smoke", "learning_seed": 11,
              "operational_mode": OPERATIONAL_MODE,
              "critic_units": CRITIC_UNITS,
              "run": {"episodes": 2, "horizon_seconds": 600, "eval_every": 2},
              "reward": {"type": "negative_network_queue_plus_pending_integral"},
              "baseline": {"controller": "validation_tuned_fixed", "search_green_durations": [25]},
              "model": {"hidden": 8, "lr": .001, "gamma_per_macro": .99},
              "optimizer": {"grad_clip": 10, "huber_delta": 1, "buffer_capacity": 100,
                    "train_start": 1, "updates_per_macro": 1, "batch_size": 2, "target_sync": 2},
              "exploration": {"epsilon": .2}}
    validation = [x for x in cases if x["split"] == "validation"]
    tuning = {"schema_version": 1, "method": "validation_grid_search",
        "binding": _tuning_binding(manifest, validation, 3600,
                                    dict(config, simulation=manifest["simulation"])),
        "search_space": {"fixed_green_duration": [25]}, "selected": {"fixed_green_duration": 25},
        "candidates": [{"fixed_green_duration": 25, "mean_queue_integral_vehicle_seconds": 1800,
            "rows": [{"case_id": c["case_id"], "scenario": c["scenario"],
                      "queue_integral_vehicle_seconds": 1800, "completion_rate": 1,
                      "insertion_rate": 1} for c in validation]}]}
    tuning["tuning_sha256"] = canonical_json_sha256(tuning)
    monkeypatch.setattr(trainer, "_tracked_tree_attestation", lambda root: {
        "git_commit": "f" * 40, "tracked_worktree": "clean", "index": "clean"})

    class QueueEngine(EmptySignalEngine):
        def lane_waiting_counts(self):
            return {"outside_projection": 3}

    accessed = []

    def factory(case, horizon):
        assert case["split"] != "test"
        accessed.append(case["case_id"])
        return MultiAgentTrafficEnv(roadnet, QueueEngine(), max_steps=horizon, min_green=20,
                                   encoder=PhaseFeatureEncoder(roadnet, 20, 40))

    def foundation(root, manifest):
        return {"status": "verified", "network_sha256": "network",
                "generator_config_sha256": "generator", "runtime_digest": "runtime"}

    output = tmp_path / "run"
    result = train_residual(factory, manifest, config, str(output), str(tmp_path), tuning, foundation)
    assert result["episodes"] == 2
    assert result["optimizer_updates"] == 4
    assert set(result["replay_coverage"]) == {"am_peak", "pm_peak"}
    artifact = json.loads((output / "validation-step-0002.json").read_text())
    assert len(artifact["rows"]) == 3
    assert all(x["baseline_policy"] == "forced_macro0_counterfactual" for x in artifact["rows"])
    for row in artifact["rows"]:
        for policy in ("candidate", "baseline"):
            costs = row[policy + "_macro_rewards"]
            assert sum(x["raw_objective_vehicle_seconds"] for x in costs) == row[policy]["queue_integral_vehicle_seconds"]
            for cost in costs:
                assert cost["raw_objective_vehicle_seconds"] == cost["network_queue_vehicle_seconds"] + cost["entry_pending_vehicle_seconds"]
                assert cost["scaled_reward"] == -cost["raw_objective_vehicle_seconds"] / 100000
    assert artifact["reload_score_identity"] is True
    status = json.loads((output / "status.json").read_text())
    assert status["status"] == "complete"
    assert status["eligible_for_final"] is False
    assert "checkpoints/step-0002/weights.npz" in status["artifact_sha256"]
    with pytest.raises(ValueError, match="immutable"):
        train_residual(factory, manifest, config, str(output), str(tmp_path), tuning, foundation)


def test_operational_mode_binds_explicit_declaration_and_rejects_mismatch():
    assert operational_time_of_day({"scenario": "normal", "case_id": "am_peak", "sim_seed": 9}) == "normal"
    with pytest.raises(ValueError, match="time.of.day"):
        operational_time_of_day({"scenario": "unrecognized"})
    with pytest.raises(ValueError, match="mismatch"):
        operational_time_of_day({"scenario": "normal", "operational_time_of_day": "am_peak"})


def test_learned_feature_schema_excludes_case_identity_and_future_demand():
    from traffic_rl.agents.schedule_residual import POLICY_INPUT_SCHEMA
    assert POLICY_INPUT_SCHEMA["learned_features"] == MACRO_FEATURES
    assert POLICY_INPUT_SCHEMA["operational_context"] == {"time_of_day": ["normal", "am_peak", "pm_peak"]}
    for forbidden in ("case_id", "learning_seed", "demand_seed", "simulator_seed", "filename", "future_flow"):
        assert not any(forbidden in feature for feature in MACRO_FEATURES)
        assert forbidden in POLICY_INPUT_SCHEMA["excluded_features"]


def test_reusing_environment_cannot_mutate_previously_returned_signal_audit(network):
    roadnet = _NodeRoadnet(network, representative(network, 2))
    env = MultiAgentTrafficEnv(roadnet, EmptySignalEngine(), max_steps=300, min_green=20)
    first = run_macro_episode(env, None, "normal")
    assert env.signal_observer is None
    second = run_macro_episode(env, None, "normal")
    assert first["policy_audit"]["observed_node_seconds"] == 300
    assert second["policy_audit"]["observed_node_seconds"] == 300
