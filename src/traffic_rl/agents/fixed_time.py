"""Fixed-time baseline: each intersection cycles its phases round-robin.

Must stay importable under Python 3.6 (CityFlow Docker image).
"""
from typing import Dict


class FixedTimeController:
    def __init__(self, num_phases):
        self.num_phases = num_phases  # type: Dict[str, int]
        self._counter = {aid: 0 for aid in num_phases}  # type: Dict[str, int]

    def act(self, observations=None):
        actions = {aid: self._counter[aid] % n for aid, n in self.num_phases.items()}
        for aid in self.num_phases:
            self._counter[aid] += 1
        return actions

    def reset(self):
        self._counter = {aid: 0 for aid in self.num_phases}
