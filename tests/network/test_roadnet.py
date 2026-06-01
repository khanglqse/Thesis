import json

from traffic_rl.network.roadnet import RoadNet

SAMPLE = {
    "intersections": [
        {
            "id": "int_A", "virtual": False,
            "roads": ["road_in", "road_out"],
            "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": [1]}]},
            "roadLinks": [
                {"startRoad": "road_in", "endRoad": "road_out"},
            ],
        },
        {"id": "int_V", "virtual": True, "roads": ["road_out"]},
    ],
    "roads": [
        {"id": "road_in", "startIntersection": "int_V", "endIntersection": "int_A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "road_out", "startIntersection": "int_A", "endIntersection": "int_V",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


def test_signalized_intersections(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    assert rn.signalized_ids() == ["int_A"]
    assert rn.num_phases("int_A") == 2


def test_single_phase_junctions_are_not_agents(tmp_path):
    # The CityFlow converter emits a trivial 1-phase trafficLight for every
    # non-signalized junction. Those must NOT be treated as agents.
    sample = json.loads(json.dumps(SAMPLE))
    sample["intersections"].append({
        "id": "int_trivial", "virtual": False,
        "roads": ["road_in"],
        "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}]},
        "roadLinks": [],
    })
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(sample))
    rn = RoadNet.load(str(p))
    assert rn.signalized_ids() == ["int_A"]   # int_trivial (1 phase) excluded


def test_incoming_lane_ids(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    # CityFlow lane id convention: "<roadId>_<laneIndex>"
    assert rn.incoming_lanes("int_A") == ["road_in_0"]
    assert rn.outgoing_lanes("int_A") == ["road_out_0"]


def test_road_adjacency_for_routing(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    assert rn.next_roads("road_in") == ["road_out"]
    assert rn.next_roads("road_out") == []
