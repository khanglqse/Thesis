"""Fixed-time baseline: each intersection cycles its green phases round-robin,
holding every phase for a fixed green duration before advancing.

A realistic fixed-time plan keeps a phase green for ~25-50s, not just one
decision interval. Holding longer cuts the per-switch lost time (the yellow /
all-red transition the env inserts on every phase change) and lets each green
discharge more of its queue -- making this a stronger, fairer baseline than a
plan that switches every action_interval.

3.6-safe.
"""
from traffic_rl.agents.base import Controller


class FixedTimeController(Controller):
    name = "FixedTime"

    def __init__(self, num_actions, green_duration=30, action_interval=10):
        # num_actions: {agent_id: #green phases}. green_duration: seconds of green
        # per phase. hold = how many decisions to keep a phase before advancing
        # (>=1); green_duration=action_interval reproduces the old switch-every-
        # interval behaviour.
        self.num_actions = num_actions
        self.green_duration = green_duration
        self.action_interval = action_interval
        self._hold = max(1, int(round(float(green_duration) / max(1, action_interval))))
        self._phase = {a: 0 for a in num_actions}
        self._ticks = {a: 0 for a in num_actions}

    def act(self, context):
        actions = {a: self._phase[a] for a in self.num_actions}
        for a, n in self.num_actions.items():
            self._ticks[a] += 1
            if self._ticks[a] >= self._hold:
                self._phase[a] = (self._phase[a] + 1) % n
                self._ticks[a] = 0
        return actions

    def reset(self):
        self._phase = {a: 0 for a in self.num_actions}
        self._ticks = {a: 0 for a in self.num_actions}
