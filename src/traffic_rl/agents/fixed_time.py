"""Deterministic nominal-duration fixed-time schedule, shared by all runners.

Phase requests follow elapsed decision time. A duration not divisible by the
policy interval is sampled on that interval without rounding the cycle length.
Signal constraints (minimum green, transitions, maximum red) may override a
request through the supplied action mask; the nominal clock keeps advancing.

3.6-safe.
"""
from traffic_rl.agents.base import Controller


class FixedTimeController(Controller):
    name = "FixedTime"

    def __init__(self, num_actions, green_duration=30, action_interval=10):
        self.num_actions = num_actions
        self.green_duration = green_duration
        self.action_interval = action_interval
        # Preserve at least one decision per phase for callers requesting a
        # shorter duration than the policy can express.
        self._duration = max(float(green_duration), float(action_interval), 1.0)
        self._decisions = 0

    def act(self, context):
        phase_slot = int(self._decisions * self.action_interval / self._duration)
        masks = context.get("action_masks", {})
        actions = {}
        for agent_id, phase_count in self.num_actions.items():
            requested = phase_slot % phase_count
            mask = masks.get(agent_id)
            if mask is not None and not mask[requested]:
                valid = [index for index in range(phase_count) if mask[index]]
                if not valid:
                    raise ValueError("fixed-time action mask has no valid phase")
                requested = valid[0]
            actions[agent_id] = requested
        self._decisions += 1
        return actions

    def reset(self):
        self._decisions = 0
