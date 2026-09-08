"""Semantic identity of the final network learner's reward (Python 3.6)."""

import math


REWARD_FIELDS = {"queue_weight", "downstream_block_weight", "switch_penalty"}
TEMPORAL_AGGREGATION = "mean_over_simulator_steps_in_action_interval"


def training_objective(reward):
    if not isinstance(reward, dict) or set(reward) != REWARD_FIELDS:
        raise ValueError("training objective reward fields are incomplete")
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) or value < 0
           for value in reward.values()):
        raise ValueError("training objective reward values are invalid")
    return {"reward": dict(reward), "temporal_aggregation": TEMPORAL_AGGREGATION}
