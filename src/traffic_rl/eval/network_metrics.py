"""Network-level metrics sampled at every simulator step.

Travel-time statistics describe completed vehicles only and are deliberately
reported beside scheduled/inserted/arrived/running/pending/removed counts.
"""

import math
import statistics

import numpy as np


_FIELDS = (
    "queued", "scheduled", "inserted", "departed", "arrived", "running",
    "pending", "removed", "travel_times",
    "per_node_queue", "spillback_lanes", "phase_switches",
    "intergreen_seconds", "max_red_seconds",
)

_SCALARS = (
    "queued", "scheduled", "inserted", "departed", "arrived", "running",
    "pending", "removed", "phase_switches", "intergreen_seconds",
    "max_red_seconds",
)


class NetworkMetricAccumulator(object):
    def __init__(self, step_seconds=1.0):
        self.step_seconds = float(step_seconds)
        if not math.isfinite(self.step_seconds) or self.step_seconds <= 0:
            raise ValueError("step_seconds must be finite and positive")
        self._steps = 0
        self._queue_integral = 0.0
        self._pending_integral = 0.0
        self._per_node_integral = {}
        self._per_node_max = {}
        self._spillback_seconds = {}
        self._terminal = None

    def observe(self, snapshot):
        missing = [field for field in _FIELDS if field not in snapshot]
        if missing:
            raise ValueError("missing snapshot fields: %s" % ", ".join(missing))
        for field in _SCALARS:
            value = float(snapshot[field])
            if not math.isfinite(value):
                raise ValueError("snapshot values must be finite")
            if value < 0:
                raise ValueError("snapshot values must be non-negative")
        for field in (
                "scheduled", "inserted", "departed", "arrived", "running",
                "pending", "removed", "phase_switches"):
            if float(snapshot[field]) != int(float(snapshot[field])):
                raise ValueError("vehicle and switch counters must be integers")
        if int(snapshot["inserted"]) != int(snapshot["departed"]):
            raise ValueError("inserted must equal departed")
        if int(snapshot["scheduled"]) != (
                int(snapshot["inserted"]) + int(snapshot["pending"])):
            raise ValueError("vehicle accounting requires scheduled = inserted + pending")
        if int(snapshot["inserted"]) != (
                int(snapshot["arrived"]) + int(snapshot["running"])
                + int(snapshot["removed"])):
            raise ValueError(
                "vehicle accounting requires inserted = arrived + running + removed")
        travel_times = [float(value) for value in snapshot["travel_times"]]
        if any(not math.isfinite(value) or value < 0 for value in travel_times):
            raise ValueError("travel_times must be finite and non-negative")

        queued = float(snapshot["queued"])
        self._queue_integral += queued * self.step_seconds
        self._pending_integral += float(snapshot["pending"]) * self.step_seconds
        for node_id, queue in snapshot["per_node_queue"].items():
            queue = float(queue)
            if not math.isfinite(queue) or queue < 0:
                raise ValueError("per-node queue must be finite and non-negative")
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
        scheduled = int(terminal.get("scheduled", 0))
        inserted = int(terminal.get("inserted", 0))
        arrived = int(terminal.get("arrived", 0))
        departed = int(terminal.get("departed", 0))
        running = int(terminal.get("running", 0))
        pending = int(terminal.get("pending", 0))
        removed = int(terminal.get("removed", 0))
        if len(travel_times) != arrived:
            raise ValueError("travel_times count must equal arrived")

        result = {
            "observed_steps": self._steps,
            "observed_seconds": self._steps * self.step_seconds,
            "queue_integral_vehicle_seconds": self._queue_integral,
            "queue_integral_vehicle_hours": self._queue_integral / 3600.0,
            "pending_integral_vehicle_seconds": self._pending_integral,
            "per_node_queue_integral_vehicle_seconds": dict(
                sorted(self._per_node_integral.items())),
            "per_node_max_queue": dict(sorted(self._per_node_max.items())),
            "spillback_lane_seconds": dict(sorted(self._spillback_seconds.items())),
            "scheduled": scheduled,
            "inserted": inserted,
            "departed": departed,
            "arrived": arrived,
            "running": running,
            "pending": pending,
            "removed": removed,
            "censored_or_unfinished": pending + running + removed,
            "completion_denominator": "scheduled",
            "completion_rate": (float(arrived) / scheduled if scheduled else None),
            "insertion_rate": (float(inserted) / scheduled if scheduled else None),
            "completed_travel_time_count": len(travel_times),
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
