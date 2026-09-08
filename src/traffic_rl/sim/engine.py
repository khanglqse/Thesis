"""Thin wrapper around the CityFlow C++ Engine (only importable inside Docker).

Keep this layer minimal: it just forwards to cityflow and returns plain dicts,
so all higher-level logic stays pure-Python and testable without cityflow.
"""


class CityFlowEngine(object):
    def __init__(self, config_path, thread_num=1):
        # type: (str, int) -> None
        import cityflow  # imported lazily; only available in the Docker image
        self._config_path = config_path
        self._thread_num = thread_num
        self._eng = cityflow.Engine(config_path, thread_num=thread_num)

    def reset(self):
        # type: () -> None
        self._eng.reset()

    def step(self):
        # type: () -> None
        self._eng.next_step()

    def set_tl_phase(self, inter_id, phase):
        # type: (str, int) -> None
        self._eng.set_tl_phase(inter_id, phase)

    def lane_vehicle_counts(self):
        # type: () -> dict
        return dict(self._eng.get_lane_vehicle_count())

    def lane_waiting_counts(self):
        # type: () -> dict
        return dict(self._eng.get_lane_waiting_vehicle_count())

    def true_lane_waiting_counts(self):
        # type: () -> dict
        # Ground-truth queue for METRIC computation. Identical to lane_waiting_counts()
        # for a real engine; PerturbedEngine overrides it to return UNPERTURBED counts so
        # that sensor-noise robustness measures true performance, not the noisy sensor.
        return self.lane_waiting_counts()

    def vehicle_count(self):
        # type: () -> int
        return int(self._eng.get_vehicle_count())

    def average_travel_time(self):
        # type: () -> float
        return float(self._eng.get_average_travel_time())

    def finished_vehicle_count(self):
        # type: () -> int
        getter = getattr(self._eng, "get_finished_vehicle_count", None)
        return int(getter()) if getter is not None else None

    def vehicle_ids(self):
        # type: () -> list
        return list(self._eng.get_vehicles(True))
