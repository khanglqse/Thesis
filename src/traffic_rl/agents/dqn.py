"""Parameter-shared DQN as a small from-scratch NumPy MLP (Adam + target net).

NumPy because the CityFlow Docker image is Python 3.6 (no modern PyTorch). The
simulator is the bottleneck, so a NumPy net costs little. 3.6-safe.
"""
import numpy as np

NEG = -1e9


def _relu(x):
    return np.maximum(x, 0.0)


class SharedDQN(object):
    def __init__(self, obs_dim, n_actions, hidden=64, lr=1e-3, seed=0,
                 grad_clip=None, huber_delta=1.0, dueling=False):
        rng = np.random.RandomState(seed)
        # grad_clip: global L2-norm cap on the gradient (None = off). huber_delta:
        # TD-error threshold beyond which the loss is linear (bounds the gradient
        # so large rewards / TD errors can't blow Q-values up). Both stabilise
        # training on the dense, large-reward Vietnamese-flow scenario.
        # dueling: split the head into a state-value V(s) and an advantage A(s,a),
        # recombined as Q = V + (A - mean_a A). Decouples "is this state good"
        # from "which action is best", which often learns faster when many
        # actions have similar value (common at traffic signals).
        self.grad_clip = grad_clip
        self.huber_delta = float(huber_delta)
        self.dueling = bool(dueling)
        self.n_actions = n_actions

        def he(fan_in, fan_out):
            return (rng.randn(fan_in, fan_out) * np.sqrt(2.0 / fan_in)).astype(np.float32)

        # shared trunk (both architectures)
        self.W1, self.b1 = he(obs_dim, hidden), np.zeros(hidden, np.float32)
        self.W2, self.b2 = he(hidden, hidden), np.zeros(hidden, np.float32)
        if self.dueling:
            self.Wv, self.bv = he(hidden, 1), np.zeros(1, np.float32)          # value stream
            self.Wa, self.ba = he(hidden, n_actions), np.zeros(n_actions, np.float32)  # advantage
            self.params = ["W1", "b1", "W2", "b2", "Wv", "bv", "Wa", "ba"]
        else:
            self.W3, self.b3 = he(hidden, n_actions), np.zeros(n_actions, np.float32)
            self.params = ["W1", "b1", "W2", "b2", "W3", "b3"]
        self.lr = lr
        self._adam = {p: [np.zeros_like(getattr(self, p)),
                          np.zeros_like(getattr(self, p))] for p in self.params}
        self._t = 0
        self.sync_target()

    def _forward(self, X, P):
        """Forward pass using the param dict P (online or target). Returns (q, cache)."""
        z1 = X.dot(P["W1"]) + P["b1"]; a1 = _relu(z1)
        z2 = a1.dot(P["W2"]) + P["b2"]; a2 = _relu(z2)
        if self.dueling:
            v = a2.dot(P["Wv"]) + P["bv"]            # (B, 1)
            adv = a2.dot(P["Wa"]) + P["ba"]          # (B, n)
            q = v + (adv - adv.mean(axis=1, keepdims=True))
        else:
            q = a2.dot(P["W3"]) + P["b3"]
        return q, (X, z1, a1, z2, a2)

    def _online(self):
        return {p: getattr(self, p) for p in self.params}

    def _target(self):
        return {p: getattr(self, "t" + p) for p in self.params}

    def q_values(self, X):
        X = np.atleast_2d(X).astype(np.float32)
        return self._forward(X, self._online())[0]

    def _target_q(self, X):
        return self._forward(X, self._target())[0]

    def greedy_action(self, obs, mask):
        q = self.q_values(obs)[0].copy()
        q[~np.asarray(mask, dtype=bool)] = NEG
        return int(np.argmax(q))

    def sync_target(self):
        for p in self.params:
            setattr(self, "t" + p, getattr(self, p).copy())

    def train_step(self, obs, actions, rewards, next_obs, dones, next_mask, gamma=0.99):
        obs = obs.astype(np.float32); next_obs = next_obs.astype(np.float32)
        B = obs.shape[0]
        q, cache = self._forward(obs, self._online())
        X, z1, a1, z2, a2 = cache

        # Double DQN: pick next action with the ONLINE net, evaluate it with the
        # TARGET net -> reduces Q-value overestimation, usually a stronger policy.
        mask = np.asarray(next_mask, dtype=bool)
        online_nq = self.q_values(next_obs).copy()
        online_nq[~mask] = NEG
        next_act = np.argmax(online_nq, axis=1)
        tnq = self._target_q(next_obs)
        next_val = tnq[np.arange(B), next_act]
        target = rewards + (1.0 - dones) * gamma * next_val

        chosen = q[np.arange(B), actions]
        diff = (chosen - target).astype(np.float32)
        # Huber loss: quadratic within +-delta, linear beyond -> bounded gradient.
        d = self.huber_delta
        absd = np.abs(diff)
        quad = np.minimum(absd, d)
        loss = float(np.mean(0.5 * quad ** 2 + d * (absd - quad)))

        dq = np.zeros_like(q)
        # d/dpred Huber = clip(diff, -delta, delta)
        dq[np.arange(B), actions] = (1.0 / B) * np.clip(diff, -d, d)

        grads = {}
        if self.dueling:
            # Q = V + (A - mean_a A): dV = sum_a dQ ; dA = dQ - mean_a dQ
            dv = dq.sum(axis=1, keepdims=True)
            dadv = dq - dq.mean(axis=1, keepdims=True)
            grads["Wv"] = a2.T.dot(dv); grads["bv"] = dv.sum(axis=0)
            grads["Wa"] = a2.T.dot(dadv); grads["ba"] = dadv.sum(axis=0)
            da2 = dv.dot(self.Wv.T) + dadv.dot(self.Wa.T)
        else:
            grads["W3"] = a2.T.dot(dq); grads["b3"] = dq.sum(axis=0)
            da2 = dq.dot(self.W3.T)
        dz2 = da2 * (z2 > 0)
        grads["W2"] = a1.T.dot(dz2); grads["b2"] = dz2.sum(axis=0)
        da1 = dz2.dot(self.W2.T); dz1 = da1 * (z1 > 0)
        grads["W1"] = X.T.dot(dz1); grads["b1"] = dz1.sum(axis=0)

        self._adam_step(grads)
        return loss

    def _adam_step(self, grads, beta1=0.9, beta2=0.999, eps=1e-8):
        self._t += 1
        if self.grad_clip is not None:
            total = np.sqrt(sum(float(np.sum(grads[p] ** 2)) for p in self.params))
            if total > self.grad_clip and total > 0:
                scale = self.grad_clip / total
                for p in self.params:
                    grads[p] = grads[p] * scale
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
