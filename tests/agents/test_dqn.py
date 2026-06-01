import numpy as np
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
