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

    def network_metric_snapshot(self, lane_to_node=None, spillback_lanes=None,
                                phase_switches=0, intergreen_seconds=0,
                                max_red_seconds=0, travel_times=None,
                                scheduled=None, inserted=None, departed=None,
                                arrived=None, pending=None, removed=None):
        """Return plain metric inputs without advancing or mutating CityFlow.

        CityFlow itself exposes current and finished vehicle counts but not the
        environment's full scheduled/inserted accounting.  The default therefore
        reports only vehicles observed in the network.  A campaign environment
        must pass authoritative ``scheduled``, ``inserted``/``departed``,
        ``pending`` and ``removed`` counters when demand is unreleased or a
        vehicle leaves without arriving.
        """
        waiting = self.lane_waiting_counts()
        per_node = {}
        for lane_id, node_id in (lane_to_node or {}).items():
            per_node[node_id] = per_node.get(node_id, 0.0) + float(
                waiting.get(lane_id, 0))
        running = self.vehicle_count()
        get_finished = getattr(self._eng, "get_finished_vehicle_count", None)
        native_arrived = int(get_finished()) if get_finished is not None else 0
        arrived = native_arrived if arrived is None else int(arrived)
        if inserted is not None and departed is not None \
                and int(inserted) != int(departed):
            raise ValueError("inserted must equal departed")
        inserted = inserted if inserted is not None else departed
        if removed is None:
            removed = max(int(inserted) - arrived - running, 0) \
                if inserted is not None else 0
        inserted = (running + arrived + int(removed)
                    if inserted is None else int(inserted))
        departed = inserted
        scheduled = inserted if scheduled is None else int(scheduled)
        pending = scheduled - inserted if pending is None else int(pending)
        return {
            "queued": float(sum(waiting.values())),
            "scheduled": scheduled,
            "inserted": inserted,
            "running": running,
            "departed": departed,
            "arrived": arrived,
            "pending": pending,
            "removed": int(removed),
            "travel_times": list(travel_times or []),
            "per_node_queue": per_node,
            "spillback_lanes": sorted(spillback_lanes or []),
            "phase_switches": int(phase_switches),
            "intergreen_seconds": float(intergreen_seconds),
            "max_red_seconds": float(max_red_seconds),
        }
