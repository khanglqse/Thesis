from collections import OrderedDict

from traffic_rl.sim.robustness_perturbations import (
    KeyedSensorEngine,
    LaneCapacityIncidentEngine,
    select_topology_incident,
)


class Engine:
    def __init__(self, reverse=False):
        pairs = [("lane_b", 20), ("lane_a", 10), ("lane_c", 30)]
        self.counts = OrderedDict(reversed(pairs) if reverse else pairs)
        self.waiting = OrderedDict((key, value // 2) for key, value in self.counts.items())
        self.speeds = []
        self.calls = []

    def reset(self):
        self.calls.append("reset")

    def step(self):
        self.calls.append("step")

    def set_tl_phase(self, node, phase):
        self.calls.append((node, phase))

    def lane_vehicle_counts(self):
        return dict(self.counts)

    def lane_waiting_counts(self):
        return dict(self.waiting)

    def true_lane_waiting_counts(self):
        return dict(self.waiting)

    def vehicle_ids(self):
        return ["v1", "v2"]

    def due_vehicle_ids(self):
        return ["v1", "v2", "v3"]

    def vehicle_count(self):
        return 2

    def average_travel_time(self):
        return 4.0

    def finished_vehicle_count(self):
        return 1

    def lane_vehicle_ids(self):
        return {"lane_a": ["v1"], "lane_b": ["v2"], "lane_c": []}

    def set_vehicle_speed(self, vehicle_id, speed):
        self.speeds.append((vehicle_id, speed))


def test_sensor_trace_is_keyed_by_step_channel_lane_not_dict_or_call_order():
    a = KeyedSensorEngine(Engine(False), kind="gaussian", amount=0.15, seed=17)
    b = KeyedSensorEngine(Engine(True), kind="gaussian", amount=0.15, seed=17)

    a_vehicle = a.lane_vehicle_counts()
    a_waiting = a.lane_waiting_counts()
    b_waiting = b.lane_waiting_counts()
    b_vehicle = b.lane_vehicle_counts()

    assert a_vehicle == b_vehicle
    assert a_waiting == b_waiting
    assert a.lane_vehicle_counts() == a_vehicle
    a.step(); b.step()
    assert a.lane_waiting_counts() == b.lane_waiting_counts()


def test_sensor_dropout_is_keyed_and_true_metrics_are_never_corrupted():
    inner = Engine()
    wrapped = KeyedSensorEngine(inner, kind="dropout", amount=1.0, seed=9)

    assert wrapped.lane_waiting_counts() == {
        "lane_a": 0, "lane_b": 0, "lane_c": 0}
    assert wrapped.true_lane_waiting_counts() == dict(inner.waiting)
    assert wrapped.vehicle_ids() == ["v1", "v2"]
    assert wrapped.due_vehicle_ids() == ["v1", "v2", "v3"]


def test_lane_incident_closes_half_lanes_only_during_fixed_window():
    inner = Engine()
    wrapped = LaneCapacityIncidentEngine(
        inner, closed_lanes=["lane_a"], start_step=2, end_step=4,
        closed_speed=0.0, recovery_speed=11.0)

    wrapped.step()
    assert inner.speeds == []
    wrapped.step()
    assert inner.speeds[-1] == ("v1", 0.0)
    wrapped.step()
    assert inner.speeds[-1] == ("v1", 0.0)
    wrapped.step()
    assert inner.speeds[-1] == ("v1", 11.0)
    assert wrapped.true_lane_waiting_counts() == dict(inner.waiting)


def test_topology_only_incident_target_is_stable_and_reduces_exactly_half():
    roadnet = {
        "roads": [
            {"id": "r_b", "endIntersection": "N1", "lanes": [{}, {}, {}, {}]},
            {"id": "r_a", "endIntersection": "N2", "lanes": [{}, {}, {}, {}]},
            {"id": "r_c", "endIntersection": "N3", "lanes": [{}, {}, {}]},
        ],
        "intersections": [
            {"id": "N2", "virtual": False}, {"id": "N1", "virtual": False},
            {"id": "N3", "virtual": False}],
    }

    target = select_topology_incident(roadnet)

    assert target == {
        "road_id": "r_a", "intersection_id": "N2", "original_lane_count": 4,
        "closed_lane_ids": ["r_a_2", "r_a_3"], "open_lane_ids": ["r_a_0", "r_a_1"],
        "capacity_reduction_fraction": 0.5,
    }


def test_topology_incident_can_be_restricted_to_the_53_controlled_signals():
    roadnet = {
        "roads": [
            {"id": "r_uncontrolled", "endIntersection": "X", "lanes": [{}, {}, {}, {}, {}, {}]},
            {"id": "r_controlled", "endIntersection": "N", "lanes": [{}, {}, {}, {}]},
        ],
        "intersections": [
            {"id": "X", "virtual": False}, {"id": "N", "virtual": False}],
    }

    target = select_topology_incident(roadnet, controlled_signal_ids=["N"])

    assert target["road_id"] == "r_controlled"
    assert target["intersection_id"] == "N"
