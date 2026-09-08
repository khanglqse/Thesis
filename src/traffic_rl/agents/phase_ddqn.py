"""Shared scalar phase-scoring Double DQN implemented in NumPy.

The model scores each movement-aligned phase row with the same MLP. Runtime
syntax remains compatible with Python 3.6 for the CityFlow image.
"""
import json
import os

import numpy as np


NEG = -1e9


def _relu(value):
    return np.maximum(value, 0.0)


class PhaseScoringDDQN(object):
    def __init__(self, feature_dim, hidden, lr, seed, grad_clip=None,
                 huber_delta=1.0):
        self.feature_dim = int(feature_dim)
        self.hidden = int(hidden)
        self.lr = float(lr)
        self.grad_clip = grad_clip
        self.huber_delta = float(huber_delta)
        rng = np.random.RandomState(seed)

        def he(fan_in, fan_out):
            return (rng.randn(fan_in, fan_out)
                    * np.sqrt(2.0 / fan_in)).astype(np.float32)

        self.W1 = he(self.feature_dim, self.hidden)
        self.b1 = np.zeros(self.hidden, np.float32)
        self.W2 = he(self.hidden, self.hidden)
        self.b2 = np.zeros(self.hidden, np.float32)
        self.W3 = he(self.hidden, 1)
        self.b3 = np.zeros(1, np.float32)
        self.params = ("W1", "b1", "W2", "b2", "W3", "b3")
        self._adam = {name: [np.zeros_like(getattr(self, name)),
                             np.zeros_like(getattr(self, name))]
                      for name in self.params}
        self._t = 0
        self.sync_target()

    def _online(self):
        return {name: getattr(self, name) for name in self.params}

    def _target(self):
        return {name: getattr(self, "t" + name) for name in self.params}

    def _forward_rows(self, rows, params):
        z1 = rows.dot(params["W1"]) + params["b1"]
        a1 = _relu(z1)
        z2 = a1.dot(params["W2"]) + params["b2"]
        a2 = _relu(z2)
        scores = a2.dot(params["W3"]) + params["b3"]
        return scores[:, 0], (rows, z1, a1, z2, a2)

    def _scores(self, features, params):
        values = np.asarray(features, dtype=np.float32)
        if values.ndim == 2:
            values = values[None, :, :]
        if values.ndim != 3 or values.shape[2] != self.feature_dim:
            raise ValueError("features must have shape (batch, phases, feature_dim)")
        batch, phases, _ = values.shape
        scores, cache = self._forward_rows(
            values.reshape(batch * phases, self.feature_dim), params)
        return scores.reshape(batch, phases), cache

    def q_values(self, features, mask):
        scores, _ = self._scores(features, self._online())
        valid = np.asarray(mask, dtype=np.bool_)
        if valid.ndim == 1:
            valid = valid[None, :]
        if valid.shape != scores.shape:
            raise ValueError("mask shape does not match phase scores")
        return np.where(valid, scores, NEG)

    def greedy_action(self, features, mask):
        valid = np.asarray(mask, dtype=np.bool_)
        if valid.ndim != 1 or not valid.any():
            raise ValueError("greedy_action requires at least one valid phase")
        return int(np.argmax(self.q_values(features, valid)[0]))

    def sync_target(self):
        for name in self.params:
            setattr(self, "t" + name, getattr(self, name).copy())

    def train_step(self, features, actions, rewards, next_features, dones,
                   next_masks, gamma):
        features = np.asarray(features, dtype=np.float32)
        if features.ndim != 3:
            raise ValueError("training features must include a batch dimension")
        batch, phases, _ = features.shape
        actions = np.asarray(actions, dtype=np.int64)
        rewards = np.asarray(rewards, dtype=np.float32)
        dones = np.asarray(dones, dtype=np.float32)
        next_masks = np.asarray(next_masks, dtype=np.bool_)
        if next_masks.shape != (batch, phases):
            raise ValueError("next_masks shape does not match phase scores")

        q, cache = self._scores(features, self._online())
        online_next, _ = self._scores(next_features, self._online())
        online_next = np.where(next_masks, online_next, NEG)
        next_actions = np.argmax(online_next, axis=1)
        target_next, _ = self._scores(next_features, self._target())
        next_values = target_next[np.arange(batch), next_actions]
        targets = rewards + (1.0 - dones) * float(gamma) * next_values

        chosen = q[np.arange(batch), actions]
        difference = (chosen - targets).astype(np.float32)
        delta = self.huber_delta
        absolute = np.abs(difference)
        quadratic = np.minimum(absolute, delta)
        loss = float(np.mean(0.5 * quadratic ** 2
                             + delta * (absolute - quadratic)))

        score_gradient = np.zeros((batch, phases), dtype=np.float32)
        score_gradient[np.arange(batch), actions] = (
            np.clip(difference, -delta, delta) / batch)
        self._adam_step(self._backprop(score_gradient.reshape(-1, 1), cache))
        return loss

    def _backprop(self, score_gradient, cache):
        rows, z1, a1, z2, a2 = cache
        gradients = {}
        gradients["W3"] = a2.T.dot(score_gradient)
        gradients["b3"] = score_gradient.sum(axis=0)
        da2 = score_gradient.dot(self.W3.T)
        dz2 = da2 * (z2 > 0)
        gradients["W2"] = a1.T.dot(dz2)
        gradients["b2"] = dz2.sum(axis=0)
        da1 = dz2.dot(self.W2.T)
        dz1 = da1 * (z1 > 0)
        gradients["W1"] = rows.T.dot(dz1)
        gradients["b1"] = dz1.sum(axis=0)
        return gradients

    def _adam_step(self, gradients, beta1=0.9, beta2=0.999, eps=1e-8):
        self._t += 1
        if self.grad_clip is not None:
            norm = np.sqrt(sum(float(np.sum(gradients[name] ** 2))
                               for name in self.params))
            if norm > float(self.grad_clip) and norm > 0:
                scale = float(self.grad_clip) / norm
                for name in self.params:
                    gradients[name] *= scale
        for name in self.params:
            gradient = gradients[name]
            mean, variance = self._adam[name]
            mean[:] = beta1 * mean + (1.0 - beta1) * gradient
            variance[:] = beta2 * variance + (1.0 - beta2) * gradient * gradient
            corrected_mean = mean / (1.0 - beta1 ** self._t)
            corrected_variance = variance / (1.0 - beta2 ** self._t)
            updated = (getattr(self, name) - self.lr * corrected_mean
                       / (np.sqrt(corrected_variance) + eps))
            setattr(self, name, updated.astype(np.float32))

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
            "meta_feature_dim": np.asarray(self.feature_dim, np.int64),
            "meta_hidden": np.asarray(self.hidden, np.int64),
            "meta_lr": np.asarray(self.lr, np.float64),
            "meta_grad_clip": np.asarray(
                np.nan if self.grad_clip is None else self.grad_clip, np.float64),
            "meta_huber_delta": np.asarray(self.huber_delta, np.float64),
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
        feature_dim = int(data["meta_feature_dim"])
        hidden = int(data["meta_hidden"])
        family = expected_contract.get("controller_family")
        if family is not None and family != "neighbor_phase_ddqn":
            raise ValueError("checkpoint controller_family is not neighbor_phase_ddqn")
        if ("feature_dim" in expected_contract
                and int(expected_contract["feature_dim"]) != feature_dim):
            raise ValueError("checkpoint feature_dim differs from weights")
        if ("feature_order" in expected_contract
                and len(expected_contract["feature_order"]) != feature_dim):
            raise ValueError("checkpoint feature_order differs from weights")
        if ("hidden_size" in expected_contract
                and int(expected_contract["hidden_size"]) != hidden):
            raise ValueError("checkpoint hidden_size differs from weights")
        if ("hidden" in expected_contract
                and int(expected_contract["hidden"]) != hidden):
            raise ValueError("checkpoint hidden alias differs from weights")
        if ("hidden_size" in expected_contract and "hidden" in expected_contract
                and int(expected_contract["hidden_size"])
                != int(expected_contract["hidden"])):
            raise ValueError("checkpoint hidden alias differs from hidden_size")
        normalization = expected_contract.get("normalization")
        if normalization is not None:
            for name in ("count_norm", "capacity_norm"):
                if (name in expected_contract
                        and float(expected_contract[name])
                        != float(normalization.get(name))):
                    raise ValueError("checkpoint %s alias differs from normalization" % name)
        grad_clip = float(data["meta_grad_clip"])
        if np.isnan(grad_clip):
            grad_clip = None
        net = cls(feature_dim, hidden,
                  float(data["meta_lr"]), seed=0, grad_clip=grad_clip,
                  huber_delta=float(data["meta_huber_delta"]))
        for name in net.params:
            setattr(net, name, data[name].astype(np.float32))
            setattr(net, "t" + name, data["target_" + name].astype(np.float32))
        return net
