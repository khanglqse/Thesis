import json

from traffic_rl.network.flow_gen import VEHICLE_TEMPLATES, generate_flow
from traffic_rl.network.roadnet import RoadNet

SAMPLE = {
    "intersections": [
        {"id": "A", "virtual": False, "roads": ["r1", "r2"],
         "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": [1]}]},
         "roadLinks": [{"startRoad": "r1", "endRoad": "r2"}]},
        {"id": "V1", "virtual": True, "roads": ["r1"]},
        {"id": "V2", "virtual": True, "roads": ["r2"]},
    ],
    "roads": [
        {"id": "r1", "startIntersection": "V1", "endIntersection": "A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "r2", "startIntersection": "A", "endIntersection": "V2",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


def _roadnet(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    return RoadNet.load(str(p))


def test_generate_flow_is_deterministic(tmp_path):
    rn = _roadnet(tmp_path)
    a = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=0.75)
    b = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=0.75)
    assert a == b


def test_flow_entries_are_valid_cityflow(tmp_path):
    rn = _roadnet(tmp_path)
    flows = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=1.0)
    assert len(flows) == 10
    f = flows[0]
    assert set(f) >= {"vehicle", "route", "interval", "startTime", "endTime"}
    assert f["route"][0] == "r1"            # routes start at an entry road
    assert f["vehicle"] == VEHICLE_TEMPLATES["motorbike"]
    assert all(isinstance(r, str) for r in f["route"])


def test_motorbike_ratio_controls_mix(tmp_path):
    rn = _roadnet(tmp_path)
    flows = generate_flow(rn, num_flows=100, route_length=2, seed=3, motorbike_ratio=0.0)
    assert all(f["vehicle"] == VEHICLE_TEMPLATES["car"] for f in flows)
