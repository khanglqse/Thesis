"""Max-Pressure baseline (Varaiya): pick the green phase maximizing pressure
= sum(incoming queue) - sum(outgoing queue) over the movements it serves.
Greedy, no learning. 3.6-safe."""
from traffic_rl.agents.base import Controller


class MaxPressureController(Controller):
    name = "MaxPressure"

    def __init__(self, roadnet):
        self.ids = roadnet.signalized_ids()
        # precompute per-agent list of (incoming_lanes, outgoing_lanes) per green
        self._mov = {}
        for a in self.ids:
            greens = roadnet.green_phases(a)
            self._mov[a] = [roadnet.phase_movements(a, p) for p in greens]

    def _valid_actions(self, agent_id, context):
        mask = context.get("action_masks", {}).get(agent_id)
        valid = [index for index in range(len(self._mov[agent_id]))
                 if mask is None or (index < len(mask) and mask[index])]
        if not valid:
            raise ValueError("no valid pressure action for %s" % agent_id)
        return valid

    def _phase_pressures(self, agent_id, waiting):
        return [sum(waiting.get(lane, 0) for lane in incoming) -
                sum(waiting.get(lane, 0) for lane in outgoing)
                for incoming, outgoing in self._mov[agent_id]]

    def act(self, context):
        actions = {}
        for agent_id in self.ids:
            pressures = self._phase_pressures(agent_id, context["waiting_counts"])
            valid = self._valid_actions(agent_id, context)
            # Ascending valid indices make pressure ties deterministic.
            actions[agent_id] = max(valid, key=lambda index: pressures[index])
        return actions


class HystereticMaxPressureController(MaxPressureController):
    """Max-Pressure with a minimum hold and switching improvement margin."""
    name = "HystereticMaxPressure"

    def __init__(self, roadnet, min_hold_decisions=3, switch_threshold=0.0):
        super(HystereticMaxPressureController, self).__init__(roadnet)
        self.min_hold_decisions = int(min_hold_decisions)
        self.switch_threshold = float(switch_threshold)
        self._current = dict((agent_id, 0) for agent_id in self.ids)
        self._ticks = dict((agent_id, 0) for agent_id in self.ids)

    def act(self, context):
        waiting = context["waiting_counts"]
        actions = {}
        for agent_id in self.ids:
            pressures = self._phase_pressures(agent_id, waiting)
            valid = self._valid_actions(agent_id, context)
            best = max(valid, key=lambda index: pressures[index])
            current = self._current[agent_id]
            if (current not in valid or
                    (self._ticks[agent_id] >= self.min_hold_decisions and
                     pressures[best] > pressures[current] + self.switch_threshold)):
                current = best
                self._current[agent_id] = current
                self._ticks[agent_id] = 0
            actions[agent_id] = current
            self._ticks[agent_id] += 1
        return actions

    def reset(self):
        self._current = dict((agent_id, 0) for agent_id in self.ids)
        self._ticks = dict((agent_id, 0) for agent_id in self.ids)
