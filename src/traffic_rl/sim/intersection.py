"""Pure-Python per-intersection observation and pressure reward.

Operates on plain dicts (lane_id -> count) so it is testable without CityFlow.
Must stay importable under Python 3.6 (CityFlow Docker image): no
`from __future__ import annotations`; `dataclasses` backport pip-installed there.
"""
from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class IntersectionState:
    inter_id: str
    incoming_lanes: List[str]
    outgoing_lanes: List[str]
    num_phases: int

    def observation(self, lane_counts: Dict[str, int], current_phase: int) -> np.ndarray:
        """Vehicle count per incoming lane, then a one-hot of the current phase."""
        counts = [float(lane_counts.get(l, 0)) for l in self.incoming_lanes]
        phase = [0.0] * self.num_phases
        if 0 <= current_phase < self.num_phases:
            phase[current_phase] = 1.0
        return np.array(counts + phase, dtype=np.float32)

    def obs_dim(self) -> int:
        return len(self.incoming_lanes) + self.num_phases


def pressure_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Signed max-pressure reward = -(incoming queue - outgoing queue).

    Negative pressure (queues draining downstream) yields positive reward.
    """
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    outflow = sum(waiting_counts.get(l, 0) for l in state.outgoing_lanes)
    return -float(inflow - outflow)
