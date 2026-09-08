"""Parameter-shared DQN as a small from-scratch NumPy MLP (Adam + target net).

NumPy because the CityFlow Docker image is Python 3.6 (no modern PyTorch). The
simulator is the bottleneck, so a NumPy net costs little. 3.6-safe.
"""
from collections import deque
import json
import os

import numpy as np

NEG = -1e9


class NStepAccumulator(object):
    """Per-agent n-step return accumulator.

    Buffers 1-step transitions and emits n-step transitions
    (s_t, a_t, R^(n), s_{t+n}, done, next_mask) where R^(n)=Σ_{k<n} γ^k r_{t+k}.
    The learner then bootstraps with γ^n from s_{t+n}. At episode end the tail is
    flushed as shorter Monte-Carlo returns (done=1 zeroes the bootstrap, so the
    same γ^n passed to train_step stays correct). n=1 reproduces 1-step DQN.
    """
    def __init__(self, n, gamma):
        self.n = int(n); self.gamma = float(gamma); self.q = deque()

    def _make(self, length):
        R, g = 0.0, 1.0
        for i in range(length):
            R += g * self.q[i][2]; g *= self.gamma
        first, last = self.q[0], self.q[length - 1]
        return (first[0], first[1], R, last[3], last[4], last[5])

    def push(self, obs, action, reward, next_obs, done, next_mask):
        self.q.append((obs, action, reward, next_obs, done, next_mask))
        out = []
        if len(self.q) >= self.n:
            out.append(self._make(self.n)); self.q.popleft()
        if done:
            while self.q:
                out.append(self._make(len(self.q))); self.q.popleft()
        return out


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
        self.obs_dim = int(obs_dim)
        self.hidden = int(hidden)
        self.n_actions = int(n_actions)

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
        self._adam_step(self._backprop(dq, cache))
        return loss

    def _backprop(self, dq, cache):
        """Backprop a dL/dq gradient through head + trunk; returns grad dict."""
        X, z1, a1, z2, a2 = cache
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
        return grads

    def imitate_step(self, obs, target_actions, masks):
        """One supervised step making argmax_a Q(s,a) match a teacher's action.

        Cross-entropy over the masked softmax of Q (treated as logits). Used to
        warm-start the net from Max-Pressure so RL fine-tuning starts at the
        heuristic's level instead of cold. Returns the cross-entropy loss.
        """
        obs = np.atleast_2d(obs).astype(np.float32)
        B = obs.shape[0]
        q, cache = self._forward(obs, self._online())
        masks = np.asarray(masks, dtype=bool)
        logits = np.where(masks, q, NEG)
        logits = logits - logits.max(axis=1, keepdims=True)
        ex = np.exp(logits); p = ex / ex.sum(axis=1, keepdims=True)
        ta = np.asarray(target_actions, dtype=np.int64)
        loss = float(np.mean(-np.log(p[np.arange(B), ta] + 1e-12)))
        dq = p.copy()
        dq[np.arange(B), ta] -= 1.0
        dq /= B
        self._adam_step(self._backprop(dq, cache))
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

    def save_bundle(self, directory, contract):
        if not isinstance(contract, dict):
            raise ValueError("checkpoint contract must be a dictionary")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(os.path.join(directory, "contract.json"), "w") as output:
            json.dump(contract, output, indent=2, sort_keys=True)
            output.write("\n")
        arrays = {name: getattr(self, name) for name in self.params}
        arrays.update({"target_" + name: getattr(self, "t" + name)
                       for name in self.params})
        arrays.update({
            "meta_obs_dim": np.asarray(self.obs_dim, np.int64),
            "meta_n_actions": np.asarray(self.n_actions, np.int64),
            "meta_hidden": np.asarray(self.hidden, np.int64),
            "meta_lr": np.asarray(self.lr, np.float64),
            "meta_grad_clip": np.asarray(
                np.nan if self.grad_clip is None else self.grad_clip, np.float64),
            "meta_huber_delta": np.asarray(self.huber_delta, np.float64),
            "meta_dueling": np.asarray(self.dueling, np.bool_),
        })
        np.savez(os.path.join(directory, "weights.npz"), **arrays)

    @classmethod
    def load_bundle(cls, directory, expected_contract):
        with open(os.path.join(directory, "contract.json")) as source:
            stored_contract = json.load(source)
        if stored_contract != expected_contract:
            keys = sorted(set(stored_contract) | set(expected_contract))
            drift = [key for key in keys
                     if stored_contract.get(key) != expected_contract.get(key)]
            raise ValueError("checkpoint contract mismatch: %s" % ", ".join(drift))
        data = np.load(os.path.join(directory, "weights.npz"))
        obs_dim = int(data["meta_obs_dim"])
        n_actions = int(data["meta_n_actions"])
        hidden = int(data["meta_hidden"])
        if expected_contract.get("controller_family") != "shared_ddqn_legacy":
            raise ValueError("checkpoint controller_family is not shared_ddqn_legacy")
        if len(expected_contract.get("feature_order", ())) != obs_dim:
            raise ValueError("checkpoint feature_order differs from weights")
        if int(expected_contract.get("hidden_size", 0)) != hidden:
            raise ValueError("checkpoint hidden_size differs from weights")
        action_contract = expected_contract.get("action_contract", {})
        if int(action_contract.get("n_actions", 0)) != n_actions:
            raise ValueError("checkpoint n_actions differs from weights")
        grad_clip = float(data["meta_grad_clip"])
        if np.isnan(grad_clip):
            grad_clip = None
        net = cls(
            obs_dim, n_actions, hidden=hidden, lr=float(data["meta_lr"]), seed=0,
            grad_clip=grad_clip, huber_delta=float(data["meta_huber_delta"]),
            dueling=bool(data["meta_dueling"]))
        for name in net.params:
            if data[name].shape != getattr(net, name).shape \
                    or data["target_" + name].shape != getattr(net, "t" + name).shape:
                raise ValueError("checkpoint parameter shape differs: %s" % name)
            setattr(net, name, data[name].astype(np.float32))
            setattr(net, "t" + name, data["target_" + name].astype(np.float32))
        return net


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
