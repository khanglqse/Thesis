import json
from pathlib import Path

import numpy as np
import pytest

from traffic_rl.agents.schedule_residual import (
    MACRO_FEATURES, CRITIC_UNITS, ResidualDDQN, ScheduleResidualController,
    macro_reward, select_macro, smdp_targets)
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder
from traffic_rl.sim.schedule_residual import EmptySignalEngine, signal_state
from tests.sim.test_schedule_residual import network


def test_baseline_tie_break_nonfinite_and_invalid_macro_abstain():
    assert select_macro([3, 3, 2], [True, True, True]) == (0, "baseline_tie_or_best")
    assert select_macro([0, 2, 100], [True, True, False]) == (1, "learned_macro")
    assert select_macro([0, np.nan, 1], [True, True, True]) == (0, "nonfinite_scores")


@pytest.mark.parametrize("weights", ["random", "nan"])
def test_normal_all_53_signals_exact_every_second_for_arbitrary_weights(network, weights):
    encoder = PhaseFeatureEncoder(network, 20, 40)
    env = MultiAgentTrafficEnv(network, EmptySignalEngine(), encoder=encoder,
                               max_steps=600, min_green=20)
    net = ResidualDDQN(len(MACRO_FEATURES), 8, 0.001, seed=42)
    if weights == "nan":
        net.W1[:] = np.nan
    controller = ScheduleResidualController(env, net, time_of_day="normal")
    obs = env.reset()
    controller.reset()
    done = False
    while not done:
        actions = controller.act({"observations": obs, "action_masks": env.action_masks()})
        obs, _, done, _ = env.step(actions)
    audit = controller.finalize()
    assert audit["observed_node_seconds"] == 53 * 600
    assert audit["state_divergence_seconds"] == 0
    assert audit["phase_divergence_seconds"] == 0
    assert audit["service_divergence_seconds"] == 0
    assert audit["nonzero_macros"] == 0
    assert audit["illegal_requests"] == 0
    assert audit["anchor_violations"] == 0
    assert len(audit["macro_events"]) == 53 * 2
    assert all(x["reason"] == "normal_exact_reference" for x in audit["macro_events"])


def test_controller_rejects_undeclared_time_of_day(network):
    env = MultiAgentTrafficEnv(network, EmptySignalEngine(), max_steps=300)
    with pytest.raises(ValueError, match="time_of_day"):
        ScheduleResidualController(env, None, time_of_day="validation_normal_seed31")


def test_macro_reward_uses_whole_network_and_pending_not_local_rewards():
    before = {"queue_integral_vehicle_seconds": 100,
              "network_queue_integral_vehicle_seconds": 80,
              "pending_integral_vehicle_seconds": 20}
    after = {"queue_integral_vehicle_seconds": 500,
             "network_queue_integral_vehicle_seconds": 350,
             "pending_integral_vehicle_seconds": 150}
    assert macro_reward(before, after) == -400
    after["queue_integral_vehicle_seconds"] = 490
    with pytest.raises(ValueError, match="integral"):
        macro_reward(before, after)


def test_smdp_terminal_target_never_bootstraps_even_nonfinite_future():
    result = smdp_targets([-10, -20], [np.nan, 4], [True, False], [300, 150], .99)
    np.testing.assert_allclose(result, [-.0001, -.0002 + .99 ** .5 * 4])


def test_residual_checkpoint_reload_contract_and_macro_scores(tmp_path):
    net = ResidualDDQN(len(MACRO_FEATURES), 8, 0.001, seed=42)
    contract = {"controller_family": "schedule_residual_ddqn",
                "critic_units": CRITIC_UNITS,
                "feature_order": MACRO_FEATURES, "feature_dim": len(MACRO_FEATURES)}
    net.save_bundle(str(tmp_path), contract)
    restored = ResidualDDQN.load_bundle(str(tmp_path), contract)
    features = np.ones((3, len(MACRO_FEATURES)), np.float32)
    np.testing.assert_array_equal(net.q_values(features, [1, 1, 1]),
                                  restored.q_values(features, [1, 1, 1]))
    wrong = dict(contract, controller_family="neighbor_phase_ddqn")
    with pytest.raises(ValueError, match="contract"):
        ResidualDDQN.load_bundle(str(tmp_path), wrong)


def test_scripted_peak_macro_rejoins_and_reload_repeats_actions(network, tmp_path):
    traces = []
    audits = []
    for repeat in range(2):
        env = MultiAgentTrafficEnv(network, EmptySignalEngine(),
                encoder=PhaseFeatureEncoder(network, 20, 40), max_steps=600, min_green=20)
        net = ResidualDDQN(len(MACRO_FEATURES), 8, .001, seed=19)
        # Encode an early-boundary preference in real model parameters. The
        # repeated rollout therefore tests NPZ weights through runtime actions.
        for name in net.params:
            getattr(net, name)[:] = 0
        net.W1[-3, 0], net.W1[-2, 0], net.W1[-1, 0] = -10, -1, -1000
        net.b1[0], net.W2[0, 0], net.W3[0, 0] = 100, 1, 1
        contract = {"controller_family": "schedule_residual_ddqn", "critic_units": CRITIC_UNITS}
        if repeat == 0:
            net.save_bundle(str(tmp_path), contract)
        else:
            net = ResidualDDQN.load_bundle(str(tmp_path), contract)
        controller = ScheduleResidualController(env, net, time_of_day="am_peak")
        obs = env.reset()
        controller.reset()
        actions_seen = []
        done = False
        while not done:
            actions = controller.act({"observations": obs})
            actions_seen.append(actions)
            obs, _, done, _ = env.step(actions)
        traces.append(actions_seen)
        audits.append(controller.finalize())
    assert traces[0] == traces[1]
    assert audits[0]["macro_events"] == audits[1]["macro_events"]
    assert audits[0]["nonzero_macros"] > 0
    assert audits[0]["phase_divergence_seconds"] > 0
    assert audits[0]["illegal_requests"] == 0
    assert audits[0]["anchor_violations"] == 0
    assert audits[0]["unlogged_divergence_seconds"] == 0


def test_real_environment_reward_includes_all_2340_lanes_and_entry_pending(network):
    class QueueEngine(EmptySignalEngine):
        def lane_waiting_counts(self):
            return {road["id"] + "_" + str(i): 1
                    for road in network.roads for i in range(len(road["lanes"]))}

        def vehicle_ids(self):
            return []

        def due_vehicle_ids(self):
            return ["entry_pending"]

    env = MultiAgentTrafficEnv(network, QueueEngine(), max_steps=300,
                              scheduled_vehicles=1, min_green=20)
    controller = ScheduleResidualController(env, None, "normal")
    obs = env.reset()
    before = {name: 0 for name in ("queue_integral_vehicle_seconds",
              "network_queue_integral_vehicle_seconds", "pending_integral_vehicle_seconds")}
    done = False
    while not done:
        obs, _, done, info = env.step(controller.act({"observations": obs}))
    assert len(env.engine.lane_waiting_counts()) == 2340
    assert info["network_queue_integral_vehicle_seconds"] == 2340 * 300
    assert info["pending_integral_vehicle_seconds"] == 300
    assert macro_reward(before, info) == -(2340 + 1) * 300


def test_large_physical_costs_keep_distinct_proportional_critic_targets_and_gradients():
    raw = np.asarray([-1000., -2000.])
    targets = smdp_targets(raw, [np.nan, np.nan], [True, True], [300, 300], .99)
    np.testing.assert_allclose(targets, [-.01, -.02])
    np.testing.assert_allclose(smdp_targets(raw * 2, [0, 0], [True, True], [300, 300], .99),
                               targets * 2)
    x = np.random.RandomState(8).randn(2, 3, len(MACRO_FEATURES)).astype(np.float32)
    nets = [ResidualDDQN(len(MACRO_FEATURES), 8, .0003, 11, huber_delta=1) for _ in range(2)]
    for net, rewards in zip(nets, (raw, raw * 2)):
        net.W3[:] = 0
        net.b3[:] = 0
        net.train_macro_step(x, [0, 1], rewards, x, [True, True],
                             np.ones((2, 3), bool), [300, 300], .99)
    # The real optimizer retains magnitude-sensitive gradients (before
    # saturation); raw-cost delta1 had exactly identical moments here.
    np.testing.assert_allclose(nets[1]._adam["b3"][0], nets[0]._adam["b3"][0] * 2)
    assert float(nets[0]._adam["b3"][0][0]) < .01
    assert not np.array_equal(nets[0]._adam["W3"][0], nets[1]._adam["W3"][0])


def test_zero_physical_reward_terminal_target_is_exact_zero():
    assert smdp_targets([0], [np.nan], [True], [300], .99).tolist() == [0]


def test_checkpoint_rejects_critic_unit_mismatch_in_contract_or_weights(tmp_path):
    net = ResidualDDQN(len(MACRO_FEATURES), 8, .001, 11)
    contract = {"controller_family": "schedule_residual_ddqn", "critic_units": CRITIC_UNITS}
    net.save_bundle(str(tmp_path), contract)
    wrong = dict(contract, critic_units=dict(CRITIC_UNITS, vehicle_seconds_per_unit=1))
    with pytest.raises(ValueError, match="critic"):
        ResidualDDQN.load_bundle(str(tmp_path), wrong)
    path = tmp_path / "weights.npz"
    with np.load(path) as source:
        arrays = {key: source[key].copy() for key in source.files}
    arrays["meta_critic_vehicle_seconds_per_unit"] = np.asarray(1.0)
    np.savez(path, **arrays)
    with pytest.raises(ValueError, match="critic"):
        ResidualDDQN.load_bundle(str(tmp_path), contract)
