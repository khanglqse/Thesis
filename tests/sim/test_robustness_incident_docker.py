import json

import pytest

from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.robustness_perturbations import LaneRestrictionIncidentEngine


def _write_cityflow_fixture(directory):
    roadnet = {
        "intersections": [
            {"id": "west", "point": {"x": 0, "y": 0}, "width": 0,
             "roads": ["in"], "virtual": True},
            {"id": "signal", "point": {"x": 100, "y": 0}, "width": 5,
             "roads": ["in", "out"], "virtual": False,
             "roadLinks": [{
                 "type": "go_straight", "startRoad": "in", "endRoad": "out",
                 "direction": 0,
                 "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0,
                                "points": [{"x": 100, "y": 0},
                                           {"x": 105, "y": 0}]}],
             }],
             "trafficLight": {"roadLinkIndices": [0], "lightphases": [
                 {"time": 30, "availableRoadLinks": [0]},
             ]}},
            {"id": "east", "point": {"x": 147, "y": 0}, "width": 0,
             "roads": ["out"], "virtual": True},
        ],
        "roads": [
            {"id": "in", "startIntersection": "west",
             "endIntersection": "signal",
             "points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}],
             "lanes": [{"width": 3.2, "maxSpeed": 16.67}]},
            {"id": "out", "startIntersection": "signal",
             "endIntersection": "east",
             "points": [{"x": 105, "y": 0}, {"x": 147, "y": 0}],
             "lanes": [{"width": 3.2, "maxSpeed": 16.67}]},
        ],
    }
    flow = [{
        "vehicle": {"length": 5.0, "width": 2.0, "maxPosAcc": 2.0,
                    "maxNegAcc": 4.5, "usualPosAcc": 2.0,
                    "usualNegAcc": 4.5, "minGap": 2.5,
                    "maxSpeed": 16.67, "headwayTime": 1.5},
        "route": ["in", "out"], "interval": 1.0,
        "startTime": 0, "endTime": 0,
    }]
    (directory / "roadnet.json").write_text(json.dumps(roadnet))
    (directory / "flow.json").write_text(json.dumps(flow))
    config = {
        "interval": 1.0, "seed": 7, "dir": str(directory) + "/",
        "roadnetFile": "roadnet.json", "flowFile": "flow.json",
        "rlTrafficLight": True, "laneChange": False, "saveReplay": False,
    }
    config_path = directory / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


@pytest.mark.docker_release
def test_pinned_cityflow_vehicle_can_exit_during_incident_deceleration(tmp_path):
    engine = CityFlowEngine(str(_write_cityflow_fixture(tmp_path)))
    engine.reset()
    for _ in range(30):
        if engine.lane_vehicle_ids().get("out_0"):
            break
        engine.step()
    assert engine.lane_vehicle_ids().get("out_0")

    speed_calls = []
    set_speed = engine.set_vehicle_speed

    def record_speed(vehicle_id, speed):
        speed_calls.append((vehicle_id, speed))
        return set_speed(vehicle_id, speed)

    engine.set_vehicle_speed = record_speed
    incident = LaneRestrictionIncidentEngine(
        engine, closed_lanes=["out_0"], start_step=1, end_step=2)
    incident.step()
    capped = set(engine.lane_vehicle_ids().get("out_0", ()))
    assert capped
    assert speed_calls == [(next(iter(capped)), 0.0)]

    incident.step()

    assert capped.isdisjoint(set(engine.vehicle_ids()))
    assert speed_calls == [(next(iter(capped)), 0.0)]
