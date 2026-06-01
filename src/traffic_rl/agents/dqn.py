"""Parameter-shared DQN as a small from-scratch NumPy MLP (Adam + target net).

NumPy because the CityFlow Docker image is Python 3.6 (no modern PyTorch). The
simulator is the bottleneck, so a NumPy net costs little. 3.6-safe.
"""
import numpy as np

NEG = -1e9


def _relu(x):
    return np.maximum(x, 0.0)


class SharedDQN(object):
    def __init__(self, obs_dim, n_actions, hidden=64, lr=1e-3, seed=0):
        rng = np.random.RandomState(seed)

        def he(fan_in, fan_out):
            return (rng.randn(fan_in, fan_out) * np.sqrt(2.0 / fan_in)).astype(np.float32)

        self.W1, self.b1 = he(obs_dim, hidden), np.zeros(hidden, np.float32)
        self.W2, self.b2 = he(hidden, hidden), np.zeros(hidden, np.float32)
        self.W3, self.b3 = he(hidden, n_actions), np.zeros(n_actions, np.float32)
        self.params = ["W1", "b1", "W2", "b2", "W3", "b3"]
        self.lr = lr
        self._adam = {p: [np.zeros_like(getattr(self, p)),
                          np.zeros_like(getattr(self, p))] for p in self.params}
        self._t = 0
        self.sync_target()

    def _forward(self, X, W1, b1, W2, b2, W3, b3):
        z1 = X.dot(W1) + b1; a1 = _relu(z1)
        z2 = a1.dot(W2) + b2; a2 = _relu(z2)
        q = a2.dot(W3) + b3
        return q, (X, z1, a1, z2, a2)

    def q_values(self, X):
        X = np.atleast_2d(X).astype(np.float32)
        q, _ = self._forward(X, self.W1, self.b1, self.W2, self.b2, self.W3, self.b3)
        return q

    def _target_q(self, X):
        return self._forward(X, self.tW1, self.tb1, self.tW2, self.tb2,
                             self.tW3, self.tb3)[0]

    def greedy_action(self, obs, mask):
        q = self.q_values(obs)[0].copy()
        q[~np.asarray(mask, dtype=bool)] = NEG
        return int(np.argmax(q))

    def sync_target(self):
        self.tW1, self.tb1 = self.W1.copy(), self.b1.copy()
        self.tW2, self.tb2 = self.W2.copy(), self.b2.copy()
        self.tW3, self.tb3 = self.W3.copy(), self.b3.copy()

    def train_step(self, obs, actions, rewards, next_obs, dones, next_mask, gamma=0.99):
        obs = obs.astype(np.float32); next_obs = next_obs.astype(np.float32)
        B = obs.shape[0]
        q, cache = self._forward(obs, self.W1, self.b1, self.W2, self.b2, self.W3, self.b3)
        X, z1, a1, z2, a2 = cache

        nq = self._target_q(next_obs).copy()
        nq[~np.asarray(next_mask, dtype=bool)] = NEG
        target = rewards + (1.0 - dones) * gamma * np.max(nq, axis=1)

        chosen = q[np.arange(B), actions]
        diff = (chosen - target).astype(np.float32)
        loss = float(np.mean(diff ** 2))

        dq = np.zeros_like(q)
        dq[np.arange(B), actions] = (2.0 / B) * diff
        dW3 = a2.T.dot(dq); db3 = dq.sum(axis=0)
        da2 = dq.dot(self.W3.T); dz2 = da2 * (z2 > 0)
        dW2 = a1.T.dot(dz2); db2 = dz2.sum(axis=0)
        da1 = dz2.dot(self.W2.T); dz1 = da1 * (z1 > 0)
        dW1 = X.T.dot(dz1); db1 = dz1.sum(axis=0)

        self._adam_step({"W1": dW1, "b1": db1, "W2": dW2, "b2": db2,
                         "W3": dW3, "b3": db3})
        return loss

    def _adam_step(self, grads, beta1=0.9, beta2=0.999, eps=1e-8):
        self._t += 1
        for p in self.params:
            g = grads[p]
            m, v = self._adam[p]
            m[:] = beta1 * m + (1 - beta1) * g
            v[:] = beta2 * v + (1 - beta2) * (g * g)
            mhat = m / (1 - beta1 ** self._t)
            vhat = v / (1 - beta2 ** self._t)
            setattr(self, p, getattr(self, p) - self.lr * mhat / (np.sqrt(vhat) + eps))

    def save(self, path):
        np.savez(path, **{p: getattr(self, p) for p in self.params})

    def load(self, path):
        d = np.load(path)
        for p in self.params:
            setattr(self, p, d[p].astype(np.float32))
        self.sync_target()


class ReplayBuffer(object):
    def __init__(self, capacity, obs_dim, n_actions, seed=0):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), np.float32)
        self.actions = np.zeros(capacity, np.int64)
        self.rewards = np.zeros(capacity, np.float32)
        self.dones = np.zeros(capacity, np.float32)
        self.next_mask = np.zeros((capacity, n_actions), np.bool_)
        self._rng = np.random.RandomState(seed)
        self._n = 0; self._i = 0

    def add(self, obs, action, reward, next_obs, done, next_mask):
        i = self._i
        self.obs[i] = obs; self.next_obs[i] = next_obs
        self.actions[i] = action; self.rewards[i] = reward; self.dones[i] = done
        self.next_mask[i] = next_mask
        self._i = (i + 1) % self.capacity
        self._n = min(self._n + 1, self.capacity)

    def sample(self, batch_size):
        idx = self._rng.randint(0, self._n, size=batch_size)
        return {"obs": self.obs[idx], "actions": self.actions[idx],
                "rewards": self.rewards[idx], "next_obs": self.next_obs[idx],
                "dones": self.dones[idx], "next_mask": self.next_mask[idx]}

    def __len__(self):
        return self._n


from traffic_rl.agents.base import Controller


class DQNController(Controller):
    """Greedy (eval-time) wrapper around a trained SharedDQN."""
    name = "DQN"

    def __init__(self, net, agent_ids):
        self.net = net
        self.agent_ids = list(agent_ids)

    def act(self, context):
        obs = context["observations"]; masks = context["action_masks"]
        return {a: self.net.greedy_action(obs[a], masks[a]) for a in self.agent_ids}
