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


class NetworkMetricsObserver(object):
    """Build the complete metric contract from one snapshot per simulator step.

    Vehicle IDs are sampled after each engine step.  A newly visible ID is an
    inserted vehicle; an ID that disappears is completed.  ``scheduled_vehicles``
    remains the denominator, so demand that has not entered the network is kept
    separate from traffic still running at the horizon.
    """

    def __init__(self, scheduled_vehicles, step_seconds=1.0,
                 lane_to_node=None, spillback_thresholds=None):
        scheduled = float(scheduled_vehicles)
        if not math.isfinite(scheduled) or scheduled < 0 \
                or scheduled != int(scheduled):
            raise ValueError("scheduled_vehicles must be a non-negative integer")
        self.scheduled_vehicles = int(scheduled)
        self.step_seconds = float(step_seconds)
        if not math.isfinite(self.step_seconds) or self.step_seconds <= 0:
            raise ValueError("step_seconds must be finite and positive")
        self.lane_to_node = dict(lane_to_node or {})
        self.spillback_thresholds = {}
        for lane_id, raw_threshold in (spillback_thresholds or {}).items():
            threshold = float(raw_threshold)
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError("spillback thresholds must be finite and positive")
            self.spillback_thresholds[lane_id] = threshold
        self.reset()

    @staticmethod
    def _vehicle_id_set(vehicle_ids):
        if vehicle_ids is None:
            raise ValueError("active_vehicle_ids are required for vehicle accounting")
        values = list(vehicle_ids)
        if len(set(values)) != len(values):
            raise ValueError("active_vehicle_ids must be unique")
        return set(values)

    def reset(self, active_vehicle_ids=None):
        active = self._vehicle_id_set(active_vehicle_ids or [])
        if len(active) > self.scheduled_vehicles:
            raise ValueError("inserted vehicles exceed scheduled vehicles")
        self._metrics = NetworkMetricAccumulator(self.step_seconds)
        self._elapsed_seconds = 0.0
        self._active_ids = active
        self._seen_ids = set(active)
        self._completed_ids = set()
        self._entry_seconds = dict((vehicle_id, 0.0) for vehicle_id in active)
        self._completed_travel_times = []

    def observe(self, waiting_counts, active_vehicle_ids,
                phase_switches=0, intergreen_seconds=0,
                max_red_seconds=0):
        active = self._vehicle_id_set(active_vehicle_ids)
        reappeared = active.intersection(self._completed_ids)
        if reappeared:
            raise ValueError("completed vehicle IDs reappeared: %s" %
                             ", ".join(sorted(reappeared)))

        elapsed = self._elapsed_seconds + self.step_seconds
        seen = self._seen_ids.union(active)
        if len(seen) > self.scheduled_vehicles:
            raise ValueError("inserted vehicles exceed scheduled vehicles")
        entry_seconds = dict(self._entry_seconds)
        for vehicle_id in active.difference(self._seen_ids):
            entry_seconds[vehicle_id] = elapsed
        newly_completed = self._active_ids.difference(active)
        completed = self._completed_ids.union(newly_completed)
        travel_times = list(self._completed_travel_times)
        for vehicle_id in sorted(newly_completed):
            travel_times.append(elapsed - entry_seconds[vehicle_id])

        queues = {}
        for lane_id, raw_queue in waiting_counts.items():
            queue = float(raw_queue)
            if not math.isfinite(queue) or queue < 0:
                raise ValueError("lane queues must be finite and non-negative")
            queues[lane_id] = queue
        per_node = {}
        for lane_id, node_id in self.lane_to_node.items():
            per_node[node_id] = per_node.get(node_id, 0.0) + queues.get(
                lane_id, 0.0)
        spillback = [lane_id for lane_id, threshold in
                     self.spillback_thresholds.items()
                     if queues.get(lane_id, 0.0) >= threshold]
        inserted = len(seen)
        snapshot = {
            "queued": sum(queues.values()),
            "scheduled": self.scheduled_vehicles,
            "inserted": inserted,
            "departed": inserted,
            "arrived": len(completed),
            "running": len(active),
            "pending": self.scheduled_vehicles - inserted,
            "removed": 0,
            "travel_times": travel_times,
            "per_node_queue": per_node,
            "spillback_lanes": sorted(spillback),
            "phase_switches": phase_switches,
            "intergreen_seconds": intergreen_seconds,
            "max_red_seconds": max_red_seconds,
        }
        self._metrics.observe(snapshot)
        self._elapsed_seconds = elapsed
        self._active_ids = active
        self._seen_ids = seen
        self._completed_ids = completed
        self._entry_seconds = entry_seconds
        self._completed_travel_times = travel_times

    def finalize(self):
        return self._metrics.finalize()
