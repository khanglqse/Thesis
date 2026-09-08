"""Deterministic balanced sampling across demand regimes."""
import numpy as np


class BalancedCaseSampler(object):
    def __init__(self, cases, seed):
        self._rng = np.random.RandomState(seed)
        self._cases = {}
        for case in cases:
            regime = case.get("scenario", case.get("regime"))
            if not regime:
                raise ValueError("every case must define scenario or regime")
            self._cases.setdefault(regime, []).append(case)
        if not self._cases:
            raise ValueError("at least one case is required")
        self._remaining = {regime: [] for regime in self._cases}
        self._regime_block = []

    def _refill_regimes(self):
        self._regime_block = sorted(self._cases)
        self._rng.shuffle(self._regime_block)

    def _next_for_regime(self, regime):
        if not self._remaining[regime]:
            shuffled = list(self._cases[regime])
            self._rng.shuffle(shuffled)
            self._remaining[regime] = shuffled
        return self._remaining[regime].pop()

    def next_case(self):
        if not self._regime_block:
            self._refill_regimes()
        regime = self._regime_block.pop()
        return self._next_for_regime(regime)
