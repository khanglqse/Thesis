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


def queue_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Direct queue-minimisation reward = -(incoming queue).

    Unlike max-pressure (which rewards draining downstream relative to upstream),
    this rewards an agent purely for keeping its own incoming queues short — i.e.
    it optimises the SAME quantity the thesis reports (total waiting vehicles).
    """
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    return -float(inflow)


def queue_norm_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Per-lane average incoming queue, negated.

    Normalising by lane count stops large intersections from dominating the
    pooled (parameter-shared) gradient, so the shared policy weights every
    junction comparably regardless of how many incoming lanes it has.
    """
    n = max(1, len(state.incoming_lanes))
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    return -float(inflow) / n


def pressure_norm_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Max-pressure reward normalised by the intersection's lane count.

    Same sign/intent as pressure_reward but scale-invariant across junctions of
    different sizes (helps the shared net and keeps TD targets O(1)).
    """
    n = max(1, len(state.incoming_lanes) + len(state.outgoing_lanes))
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    outflow = sum(waiting_counts.get(l, 0) for l in state.outgoing_lanes)
    return -float(inflow - outflow) / n


def efficient_pressure_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Efficient pressure (arXiv 2112.02336): mean incoming queue minus mean
    outgoing queue, i.e. pressure computed on PER-LANE AVERAGES instead of raw
    sums. This is scale-invariant to how many lanes a movement has and is the
    reward that lets Efficient-/Advanced-MPLight edge past Max-Pressure.
    """
    nin = max(1, len(state.incoming_lanes))
    nout = max(1, len(state.outgoing_lanes))
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    outflow = sum(waiting_counts.get(l, 0) for l in state.outgoing_lanes)
    return -float(inflow / nin - outflow / nout)


_REWARDS = {
    "pressure": pressure_reward,
    "queue": queue_reward,
    "queue_norm": queue_norm_reward,
    "pressure_norm": pressure_norm_reward,
    "efficient_pressure": efficient_pressure_reward,
}


def make_reward(reward_type="pressure"):
    """Return the reward function for `reward_type` (see _REWARDS keys)."""
    try:
        return _REWARDS[reward_type]
    except KeyError:
        raise ValueError("unknown reward_type %r; choose from %s"
                         % (reward_type, sorted(_REWARDS)))
