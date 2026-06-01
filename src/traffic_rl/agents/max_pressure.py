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
