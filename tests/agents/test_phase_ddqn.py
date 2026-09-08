import json

import numpy as np
import pytest

from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN


def test_greedy_action_never_selects_padding():
    net = PhaseScoringDDQN(12, hidden=16, lr=1e-3, seed=1)
    features = np.zeros((4, 12), np.float32)

    assert net.greedy_action(features, np.array([1, 1, 0, 0], bool)) in (0, 1)
    q_values = net.q_values(features, np.array([1, 1, 0, 0], bool))
    assert q_values.shape == (1, 4)
    assert np.all(q_values[0, 2:] < -1e8)


def test_double_dqn_uses_online_argmax_and_target_evaluation():
    net = PhaseScoringDDQN(1, hidden=1, lr=1e-3, seed=1,
                           huber_delta=10.0)
    net.W1[:] = 1.0
    net.b1[:] = 0.0
    net.W2[:] = 1.0
    net.b2[:] = 0.0
    net.W3[:] = 1.0
    net.b3[:] = 0.0
    net.tW1[:] = 1.0
    net.tb1[:] = 0.0
    net.tW2[:] = 1.0
    net.tb2[:] = 0.0
    net.tW3[:] = -1.0
    net.tb3[:] = 0.0

    loss = net.train_step(
        np.zeros((1, 2, 1), np.float32), np.array([0]),
        np.array([0.0], np.float32),
        np.array([[[1.0], [2.0]]], np.float32),
        np.array([0.0], np.float32), np.array([[True, True]]), gamma=1.0)

    # Online selects phase 1 (Q=2), target evaluates that phase at -2.
    assert loss == pytest.approx(2.0)


def test_loader_rejects_count_norm_drift(tmp_path):
    net = PhaseScoringDDQN(12, hidden=16, lr=1e-3, seed=1)
    contract = {"obs_schema_version": 2, "count_norm": 5.0}
    net.save_bundle(str(tmp_path), contract)
    assert json.loads((tmp_path / "contract.json").read_text()) == contract

    with pytest.raises(ValueError, match="count_norm"):
        PhaseScoringDDQN.load_bundle(
            str(tmp_path), {"obs_schema_version": 2, "count_norm": 40.0})


def test_bundle_round_trip_preserves_online_and_target_values(tmp_path):
    net = PhaseScoringDDQN(3, hidden=4, lr=2e-3, seed=2,
                           grad_clip=5.0, huber_delta=0.5)
    features = np.arange(18, dtype=np.float32).reshape(2, 3, 3) / 10.0
    mask = np.array([[True, True, False], [True, False, True]])
    contract = {"obs_schema_version": 2, "feature_order": ["a", "b", "c"]}
    before = net.q_values(features, mask)
    net.save_bundle(str(tmp_path), contract)

    loaded = PhaseScoringDDQN.load_bundle(str(tmp_path), contract)

    np.testing.assert_allclose(loaded.q_values(features, mask), before)
    assert loaded.feature_dim == 3
    assert loaded.hidden == 4


def test_loader_binds_canonical_contract_dimensions_to_weights(tmp_path):
    net = PhaseScoringDDQN(3, hidden=4, lr=2e-3, seed=2)
    contract = {
        "controller_family": "neighbor_phase_ddqn",
        "feature_dim": 3,
        "hidden_size": 4,
        "hidden": 4,
        "feature_order": ["a", "b", "c"],
    }
    net.save_bundle(str(tmp_path), contract)

    drifted = dict(contract)
    drifted["hidden_size"] = 5
    (tmp_path / "contract.json").write_text(json.dumps(drifted))
    with pytest.raises(ValueError, match="hidden_size"):
        PhaseScoringDDQN.load_bundle(str(tmp_path), drifted)


def test_loader_rejects_family_and_alias_drift(tmp_path):
    net = PhaseScoringDDQN(3, hidden=4, lr=2e-3, seed=2)
    wrong_family = {
        "controller_family": "shared_ddqn_legacy",
        "feature_dim": 3,
        "hidden_size": 4,
        "hidden": 4,
    }
    net.save_bundle(str(tmp_path), wrong_family)
    with pytest.raises(ValueError, match="controller_family"):
        PhaseScoringDDQN.load_bundle(str(tmp_path), wrong_family)

    aliases = {
        "controller_family": "neighbor_phase_ddqn",
        "feature_dim": 3,
        "hidden_size": 4,
        "hidden": 5,
    }
    net.save_bundle(str(tmp_path), aliases)
    with pytest.raises(ValueError, match="hidden alias"):
        PhaseScoringDDQN.load_bundle(str(tmp_path), aliases)


def test_synthetic_updates_remain_finite_and_reduce_loss():
    net = PhaseScoringDDQN(4, hidden=16, lr=1e-2, seed=3,
                           grad_clip=10.0, huber_delta=1.0)
    rng = np.random.RandomState(4)
    features = rng.randn(32, 3, 4).astype(np.float32)
    next_features = rng.randn(32, 3, 4).astype(np.float32)
    actions = rng.randint(0, 3, size=32)
    rewards = rng.randn(32).astype(np.float32)
    dones = np.zeros(32, np.float32)
    masks = np.ones((32, 3), bool)
    first = net.train_step(features, actions, rewards, next_features,
                           dones, masks, gamma=0.9)
    for _ in range(100):
        last = net.train_step(features, actions, rewards, next_features,
                              dones, masks, gamma=0.9)

    assert np.isfinite(last)
    assert last < first
