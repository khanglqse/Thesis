"""Random baseline: pick a uniformly-random valid green phase each decision.
Lower-bound reference. 3.6-safe."""
import random
from traffic_rl.agents.base import Controller


class RandomController(Controller):
    name = "Random"

    def __init__(self, num_actions, seed=0):
        self.num_actions = num_actions
        self._rng = random.Random(seed)

    def act(self, context):
        return {a: self._rng.randrange(n) for a, n in self.num_actions.items()}

    def reset(self):
        pass
