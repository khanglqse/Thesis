"""Fixed-size replay storage with auditable demand-regime coverage."""
import numpy as np


class NetworkReplayBuffer(object):
    def __init__(self, capacity, max_green, feature_dim, seed):
        self.capacity = int(capacity)
        self.features = np.zeros(
            (self.capacity, max_green, feature_dim), dtype=np.float32)
        self.next_features = np.zeros_like(self.features)
        self.actions = np.zeros(self.capacity, dtype=np.int64)
        self.rewards = np.zeros(self.capacity, dtype=np.float32)
        self.dones = np.zeros(self.capacity, dtype=np.float32)
        self.next_masks = np.zeros(
            (self.capacity, max_green), dtype=np.bool_)
        self.case_regimes = np.full(self.capacity, -1, dtype=np.int16)
        self._regime_to_id = {}
        self._id_to_regime = {}
        self._rng = np.random.RandomState(seed)
        self._size = 0
        self._index = 0

    def _regime_id(self, regime):
        if regime not in self._regime_to_id:
            regime_id = len(self._regime_to_id)
            self._regime_to_id[regime] = regime_id
            self._id_to_regime[regime_id] = regime
        return self._regime_to_id[regime]

    def add(self, features, action, reward, next_features, done, next_mask,
            case_regime):
        index = self._index
        self.features[index] = features
        self.actions[index] = action
        self.rewards[index] = reward
        self.next_features[index] = next_features
        self.dones[index] = done
        self.next_masks[index] = next_mask
        self.case_regimes[index] = self._regime_id(case_regime)
        self._index = (index + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size):
        if self._size == 0:
            raise ValueError("cannot sample an empty replay buffer")
        indices = self._rng.randint(0, self._size, size=int(batch_size))
        return {
            "features": self.features[indices],
            "actions": self.actions[indices],
            "rewards": self.rewards[indices],
            "next_features": self.next_features[indices],
            "dones": self.dones[indices],
            "next_masks": self.next_masks[indices],
            "case_regimes": self.case_regimes[indices],
        }

    def coverage(self):
        coverage = {}
        for regime_id in self.case_regimes[:self._size]:
            regime = self._id_to_regime[int(regime_id)]
            coverage[regime] = coverage.get(regime, 0) + 1
        return coverage

    def __len__(self):
        return self._size
