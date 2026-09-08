"""Network-level metrics sampled at every simulator step.

Travel-time statistics describe completed vehicles only and are deliberately
reported beside departed/arrived/running counts and completion rate.
"""

import statistics

import numpy as np


_FIELDS = (
    "queued", "running", "departed", "arrived", "travel_times",
    "per_node_queue", "spillback_lanes", "phase_switches",
    "intergreen_seconds", "max_red_seconds",
)


class NetworkMetricAccumulator(object):
    def __init__(self, step_seconds=1.0):
        self.step_seconds = float(step_seconds)
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        self._steps = 0
        self._queue_integral = 0.0
        self._per_node_integral = {}
        self._per_node_max = {}
        self._spillback_seconds = {}
        self._terminal = None

    def observe(self, snapshot):
        missing = [field for field in _FIELDS if field not in snapshot]
        if missing:
            raise ValueError("missing snapshot fields: %s" % ", ".join(missing))
        for field in ("queued", "running", "departed", "arrived",
                      "phase_switches", "intergreen_seconds", "max_red_seconds"):
            if float(snapshot[field]) < 0:
                raise ValueError("snapshot values must be non-negative")

        queued = float(snapshot["queued"])
        self._queue_integral += queued * self.step_seconds
        for node_id, queue in snapshot["per_node_queue"].items():
            queue = float(queue)
            if queue < 0:
                raise ValueError("per-node queue must be non-negative")
            self._per_node_integral[node_id] = (
                self._per_node_integral.get(node_id, 0.0)
                + queue * self.step_seconds)
            self._per_node_max[node_id] = max(
                queue, self._per_node_max.get(node_id, 0.0))
        for lane_id in snapshot["spillback_lanes"]:
            self._spillback_seconds[lane_id] = (
                self._spillback_seconds.get(lane_id, 0.0) + self.step_seconds)
        self._steps += 1
        self._terminal = dict(snapshot)

    def finalize(self):
        terminal = self._terminal or dict((field, 0) for field in _FIELDS)
        terminal["travel_times"] = terminal.get("travel_times") or []
        travel_times = [float(value) for value in terminal["travel_times"]]
        arrived = int(terminal.get("arrived", 0))
        departed = int(terminal.get("departed", 0))
        running = int(terminal.get("running", 0))
        if arrived > departed:
            raise ValueError("arrived cannot exceed departed")
        if travel_times and len(travel_times) != arrived:
            raise ValueError("travel_times count must equal arrived")

        result = {
            "observed_steps": self._steps,
            "observed_seconds": self._steps * self.step_seconds,
            "queue_integral_vehicle_seconds": self._queue_integral,
            "queue_integral_vehicle_hours": self._queue_integral / 3600.0,
            "per_node_queue_integral_vehicle_seconds": dict(
                sorted(self._per_node_integral.items())),
            "per_node_max_queue": dict(sorted(self._per_node_max.items())),
            "spillback_lane_seconds": dict(sorted(self._spillback_seconds.items())),
            "departed": departed,
            "arrived": arrived,
            "running": running,
            "pending": departed - arrived,
            "completion_rate": (float(arrived) / departed if departed else None),
            "phase_switches": int(terminal.get("phase_switches", 0)),
            "intergreen_seconds": float(terminal.get("intergreen_seconds", 0)),
            "max_red_seconds": float(terminal.get("max_red_seconds", 0)),
            "travel_time_completed_mean": None,
            "travel_time_completed_median": None,
            "travel_time_completed_p95": None,
        }
        if travel_times:
            result.update({
                "travel_time_completed_mean": statistics.mean(travel_times),
                "travel_time_completed_median": statistics.median(travel_times),
                "travel_time_completed_p95": float(np.percentile(travel_times, 95)),
            })
        return result
