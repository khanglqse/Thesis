# Shared fixtures live here; intentionally minimal for now.


class FakeEngine:
    """Duck-typed stand-in for CityFlowEngine.

    Records set_tl_phase + step calls so tests can assert phase scheduling.
    lane counts are programmable via .vehicle_counts / .waiting_counts dicts.
    """
    def __init__(self, vehicle_counts=None, waiting_counts=None):
        self.vehicle_counts = dict(vehicle_counts or {})
        self.waiting_counts = dict(waiting_counts or {})
        self.calls = []          # ("set", inter_id, phase) / ("step",) / ("reset",)
        self.phase = {}          # inter_id -> last phase set
        self._tt = 0.0
        self._t = 0

    def reset(self):
        self.calls.append(("reset",))
        self._t = 0

    def step(self):
        self.calls.append(("step",))
        self._t += 1
        self._tt += 1.0

    def set_tl_phase(self, inter_id, phase):
        self.calls.append(("set", inter_id, phase))
        self.phase[inter_id] = phase

    def lane_vehicle_counts(self):
        return dict(self.vehicle_counts)

    def lane_waiting_counts(self):
        return dict(self.waiting_counts)

    def vehicle_count(self):
        return sum(self.vehicle_counts.values())

    def average_travel_time(self):
        return self._tt

    def steps_of(self, kind):
        return [c for c in self.calls if c[0] == kind]
