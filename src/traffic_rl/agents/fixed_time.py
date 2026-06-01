"""Fixed-time baseline: each intersection cycles its green phases round-robin.
3.6-safe."""
from traffic_rl.agents.base import Controller


class FixedTimeController(Controller):
    name = "FixedTime"

    def __init__(self, num_actions):
        self.num_actions = num_actions          # {agent_id: #green phases}
        self._counter = {a: 0 for a in num_actions}

    def act(self, context):
        actions = {a: self._counter[a] % n for a, n in self.num_actions.items()}
        for a in self.num_actions:
            self._counter[a] += 1
        return actions

    def reset(self):
        self._counter = {a: 0 for a in self.num_actions}
