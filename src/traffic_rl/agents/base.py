"""Shared controller helpers. A controller implements:
    act(context) -> {agent_id: green_choice}
where context = {"observations": {...}, "waiting_counts": {lane: int},
                 "action_masks": {agent_id: np.bool_ array}}.
3.6-safe.
"""


class Controller(object):
    name = "base"

    def act(self, context):
        raise NotImplementedError

    def reset(self):
        pass
