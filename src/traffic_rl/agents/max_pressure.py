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

    def act(self, context):
        w = context["waiting_counts"]
        actions = {}
        for a in self.ids:
            best_idx, best_p = 0, None
            for idx, (inc, out) in enumerate(self._mov[a]):
                p = sum(w.get(l, 0) for l in inc) - sum(w.get(l, 0) for l in out)
                if best_p is None or p > best_p:
                    best_p, best_idx = p, idx
            actions[a] = best_idx
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

    def _phase_pressures(self, agent_id, waiting):
        return [sum(waiting.get(lane, 0) for lane in incoming) -
                sum(waiting.get(lane, 0) for lane in outgoing)
                for incoming, outgoing in self._mov[agent_id]]

    def act(self, context):
        waiting = context["waiting_counts"]
        actions = {}
        for agent_id in self.ids:
            pressures = self._phase_pressures(agent_id, waiting)
            best = max(range(len(pressures)), key=lambda index: pressures[index])
            current = self._current[agent_id]
            if (self._ticks[agent_id] >= self.min_hold_decisions and
                    pressures[best] > pressures[current] + self.switch_threshold):
                current = best
                self._current[agent_id] = current
                self._ticks[agent_id] = 0
            actions[agent_id] = current
            self._ticks[agent_id] += 1
        return actions

    def reset(self):
        self._current = dict((agent_id, 0) for agent_id in self.ids)
        self._ticks = dict((agent_id, 0) for agent_id in self.ids)
