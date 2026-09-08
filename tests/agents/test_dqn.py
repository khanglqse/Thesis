import json

import numpy as np
import pytest
from traffic_rl.agents.dqn import SharedDQN, ReplayBuffer

def test_qvalues_shape():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    q = net.q_values(np.zeros((4, 5), dtype=np.float32))
    assert q.shape == (4, 3)

def test_greedy_respects_mask():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    obs = np.ones(5, dtype=np.float32)
    mask = np.array([False, False, True])     # only action 2 valid
    assert net.greedy_action(obs, mask) == 2

def test_train_step_reduces_loss_on_fixed_batch():
    net = SharedDQN(obs_dim=4, n_actions=2, hidden=16, seed=1, lr=1e-2)
    rng = np.random.RandomState(0)
    obs = rng.randn(32, 4).astype(np.float32)
    next_obs = rng.randn(32, 4).astype(np.float32)
    acts = rng.randint(0, 2, size=32)
    rew = rng.randn(32).astype(np.float32)
    done = np.zeros(32, dtype=np.float32)
    nmask = np.ones((32, 2), dtype=np.bool_)
    net.sync_target()
    first = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    for _ in range(200):
        last = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    assert last < first * 0.5                  # loss meaningfully decreased

def test_replay_buffer_sample_shapes():
    buf = ReplayBuffer(capacity=100, obs_dim=4, n_actions=2, seed=0)
    for i in range(50):
        buf.add(np.zeros(4, np.float32), 1, 0.5, np.ones(4, np.float32), 0.0,
                np.array([True, True]))
    batch = buf.sample(16)
    assert batch["obs"].shape == (16, 4)
    assert batch["actions"].shape == (16,)
    assert batch["next_mask"].shape == (16, 2)
    assert len(buf) == 50


from traffic_rl.agents.dqn import DQNController

def test_dqn_controller_greedy_actions_are_masked():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    ctrl = DQNController(net, agent_ids=["A"])
    import numpy as np
    ctx = {"observations": {"A": np.ones(5, np.float32)},
           "waiting_counts": {}, "action_masks": {"A": np.array([True, False, False])}}
    assert ctrl.act(ctx) == {"A": 0}          # only valid action


def test_dueling_qvalues_shape_and_params():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0, dueling=True)
    assert net.dueling and "Wv" in net.params and "Wa" in net.params
    q = net.q_values(np.zeros((4, 5), dtype=np.float32))
    assert q.shape == (4, 3)


def test_dueling_train_step_reduces_loss():
    net = SharedDQN(obs_dim=4, n_actions=2, hidden=16, seed=1, lr=1e-2, dueling=True)
    rng = np.random.RandomState(0)
    obs = rng.randn(32, 4).astype(np.float32)
    next_obs = rng.randn(32, 4).astype(np.float32)
    acts = rng.randint(0, 2, size=32)
    rew = rng.randn(32).astype(np.float32)
    done = np.zeros(32, dtype=np.float32)
    nmask = np.ones((32, 2), dtype=np.bool_)
    net.sync_target()
    first = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    for _ in range(200):
        last = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    assert last < first * 0.5


def test_dueling_save_load_roundtrip(tmp_path):
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0, dueling=True)
    x = np.ones((2, 5), dtype=np.float32)
    before = net.q_values(x)
    p = str(tmp_path / "d.npz")
    net.save(p)
    net2 = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=7, dueling=True)
    net2.load(p)
    assert np.allclose(before, net2.q_values(x))


def test_shared_dqn_bundle_roundtrip_and_contract_binding(tmp_path):
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0, dueling=True)
    contract = {
        "controller_family": "shared_ddqn_legacy",
        "feature_order": ["f%d" % index for index in range(5)],
        "hidden_size": 8,
        "action_contract": {"n_actions": 3},
    }
    before = net.q_values(np.ones((2, 5), np.float32))
    net.save_bundle(str(tmp_path), contract)

    loaded = SharedDQN.load_bundle(str(tmp_path), contract)

    np.testing.assert_allclose(loaded.q_values(np.ones((2, 5), np.float32)), before)
    assert json.loads((tmp_path / "contract.json").read_text()) == contract


@pytest.mark.parametrize("field,value,message", [
    ("controller_family", "neighbor_phase_ddqn", "controller_family"),
    ("hidden_size", 9, "hidden_size"),
    ("feature_order", ["short"], "feature_order"),
    ("action_contract", {"n_actions": 2}, "n_actions"),
])
def test_shared_dqn_bundle_rejects_contract_weight_drift(
        tmp_path, field, value, message):
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0, dueling=True)
    contract = {
        "controller_family": "shared_ddqn_legacy",
        "feature_order": ["f%d" % index for index in range(5)],
        "hidden_size": 8,
        "action_contract": {"n_actions": 3},
    }
    net.save_bundle(str(tmp_path), contract)
    contract[field] = value
    (tmp_path / "contract.json").write_text(json.dumps(contract))

    with pytest.raises(ValueError, match=message):
        SharedDQN.load_bundle(str(tmp_path), contract)


from traffic_rl.agents.dqn import NStepAccumulator


def test_nstep_emits_discounted_return_and_tplusn_state():
    acc = NStepAccumulator(n=3, gamma=0.5)
    m = np.array([True, True])
    # push 2 transitions: not enough yet for a 3-step window
    assert acc.push("s0", 0, 1.0, "s1", 0.0, m) == []
    assert acc.push("s1", 1, 2.0, "s2", 0.0, m) == []
    out = acc.push("s2", 0, 4.0, "s3", 0.0, m)        # window full
    assert len(out) == 1
    s, a, R, snext, done, mask = out[0]
    assert s == "s0" and a == 0 and snext == "s3" and done == 0.0
    assert abs(R - (1.0 + 0.5 * 2.0 + 0.25 * 4.0)) < 1e-9   # 1 + 1 + 1 = 3.0


def test_nstep_flushes_tail_on_done():
    acc = NStepAccumulator(n=3, gamma=1.0)
    m = np.array([True])
    acc.push("s0", 0, 1.0, "s1", 0.0, m)
    out = acc.push("s1", 1, 2.0, "s2", 1.0, m)     # done -> flush remaining tail
    # two transitions emitted: from s0 (1+2=3) and from s1 (2), both terminal
    assert [(o[0], o[2], o[4]) for o in out] == [("s0", 3.0, 1.0), ("s1", 2.0, 1.0)]


def test_nstep_n1_is_one_step():
    acc = NStepAccumulator(n=1, gamma=0.9)
    out = acc.push("s0", 1, 5.0, "s1", 0.0, np.array([True]))
    assert len(out) == 1 and out[0][2] == 5.0 and out[0][3] == "s1"


def test_imitate_step_pushes_q_argmax_toward_teacher():
    net = SharedDQN(obs_dim=4, n_actions=3, hidden=16, seed=2, lr=5e-2)
    rng = np.random.RandomState(0)
    obs = rng.randn(16, 4).astype(np.float32)
    target = rng.randint(0, 3, size=16)
    mask = np.ones((16, 3), dtype=np.bool_)
    first = net.imitate_step(obs, target, mask)
    for _ in range(300):
        last = net.imitate_step(obs, target, mask)
    assert last < first
    preds = np.argmax(net.q_values(obs), axis=1)
    assert (preds == target).mean() > 0.9      # net learned to mimic the teacher
