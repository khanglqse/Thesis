"""Deterministic V3 robustness perturbations (Python 3.6 compatible)."""

import hashlib
import math


def _uniform(seed, step, channel, lane_id, draw):
    payload = "%s|%s|%s|%s|%s" % (seed, step, channel, lane_id, draw)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return (integer + 0.5) / float(2 ** 64)


def _normal(seed, step, channel, lane_id):
    first = max(_uniform(seed, step, channel, lane_id, 0), 1e-15)
    second = _uniform(seed, step, channel, lane_id, 1)
    return math.sqrt(-2.0 * math.log(first)) * math.cos(2.0 * math.pi * second)


class _DelegatingEngine(object):
    def __init__(self, inner):
        self._inner = inner

    def reset(self):
        return self._inner.reset()

    def step(self):
        return self._inner.step()

    def set_tl_phase(self, inter_id, phase):
        return self._inner.set_tl_phase(inter_id, phase)

    def lane_vehicle_counts(self):
        return self._inner.lane_vehicle_counts()

    def lane_waiting_counts(self):
        return self._inner.lane_waiting_counts()

    def true_lane_waiting_counts(self):
        getter = getattr(self._inner, "true_lane_waiting_counts", None)
        return getter() if getter is not None else self._inner.lane_waiting_counts()

    def vehicle_count(self):
        return self._inner.vehicle_count()

    def average_travel_time(self):
        return self._inner.average_travel_time()

    def finished_vehicle_count(self):
        return self._inner.finished_vehicle_count()

    def vehicle_ids(self):
        return self._inner.vehicle_ids()

    def due_vehicle_ids(self):
        return self._inner.due_vehicle_ids()


class KeyedSensorEngine(_DelegatingEngine):
    """Perturb observations with a trace keyed by step/channel/lane.

    Hash-derived draws make the trace independent of mapping iteration order,
    repeated reads, and whether a controller asks for vehicle or waiting counts
    first. Ground-truth metrics always delegate to the unperturbed engine.
    """

    def __init__(self, inner, kind, amount, seed):
        super(KeyedSensorEngine, self).__init__(inner)
        if kind not in ("gaussian", "dropout"):
            raise ValueError("sensor perturbation kind must be gaussian or dropout")
        self.kind = kind
        self.amount = float(amount)
        if not math.isfinite(self.amount) or not 0.0 <= self.amount <= 1.0:
            raise ValueError("sensor perturbation amount must be in [0, 1]")
        self.seed = int(seed)
        self._step = 0

    def reset(self):
        self._step = 0
        return self._inner.reset()

    def step(self):
        result = self._inner.step()
        self._step += 1
        return result

    def _perturb(self, counts, channel):
        result = {}
        for lane_id in sorted(counts):
            value = counts[lane_id]
            if self.kind == "dropout":
                draw = _uniform(self.seed, self._step, channel, lane_id, 0)
                result[lane_id] = 0 if draw < self.amount else value
            else:
                z = _normal(self.seed, self._step, channel, lane_id)
                noisy = float(value) + z * self.amount * max(1.0, abs(float(value)))
                result[lane_id] = max(0, int(round(noisy)))
        return result

    def lane_vehicle_counts(self):
        return self._perturb(self._inner.lane_vehicle_counts(), "vehicle")

    def lane_waiting_counts(self):
        return self._perturb(self._inner.lane_waiting_counts(), "waiting")


class LaneRestrictionIncidentEngine(_DelegatingEngine):
    """Restrict a frozen subset of lanes during the active time window."""

    def __init__(self, inner, closed_lanes, start_step, end_step,
                 closed_speed=0.0):
        super(LaneRestrictionIncidentEngine, self).__init__(inner)
        self.closed_lanes = tuple(sorted(closed_lanes))
        self.start_step = int(start_step)
        self.end_step = int(end_step)
        self.closed_speed = float(closed_speed)
        if not self.closed_lanes or not 0 <= self.start_step < self.end_step:
            raise ValueError("lane incident requires lanes and a valid time window")
        self._step = 0

    def reset(self):
        self._step = 0
        return self._inner.reset()

    def _vehicles_on_closed_lanes(self):
        lane_vehicles = self._inner.lane_vehicle_ids()
        return set(vehicle for lane in self.closed_lanes
                   for vehicle in lane_vehicles.get(lane, ()))

    def step(self):
        result = self._inner.step()
        self._step += 1
        if self.start_step <= self._step < self.end_step:
            current = self._vehicles_on_closed_lanes()
            for vehicle_id in sorted(current):
                self._inner.set_vehicle_speed(vehicle_id, self.closed_speed)
        return result


def select_topology_incident(roadnet_document, controlled_signal_ids=None):
    """Select an incoming road where exactly half the lanes can be restricted."""
    intersections = dict((item["id"], item)
                         for item in roadnet_document.get("intersections", ()))
    controlled = (set(controlled_signal_ids)
                  if controlled_signal_ids is not None else None)
    candidates = []
    for road in roadnet_document.get("roads", ()):
        lane_count = len(road.get("lanes", ()))
        end_id = road.get("endIntersection")
        end = intersections.get(end_id, {})
        if (lane_count >= 2 and lane_count % 2 == 0
                and not end.get("virtual", False)
                and (controlled is None or end_id in controlled)):
            candidates.append((-lane_count, str(road.get("id")), str(end_id), road))
    if not candidates:
        raise ValueError("roadnet has no incoming road with an even multi-lane count")
    unused_count, road_id, intersection_id, road = sorted(candidates)[0]
    lane_count = len(road["lanes"])
    open_count = lane_count // 2
    return {
        "road_id": road_id,
        "intersection_id": intersection_id,
        "original_lane_count": lane_count,
        "closed_lane_ids": ["%s_%d" % (road_id, index)
                            for index in range(open_count, lane_count)],
        "open_lane_ids": ["%s_%d" % (road_id, index)
                          for index in range(open_count)],
        "restricted_lane_fraction": 0.5,
    }
