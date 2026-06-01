import json
from traffic_rl.network.roadnet import RoadNet

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False,
            "roads": ["rin", "rout"],
            "roadLinks": [
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]},
            ],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},   # green 0
                {"time": 6,  "availableRoadLinks": []},     # all-red
                {"time": 39, "availableRoadLinks": [1]},   # green 1
            ]},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "X", "endIntersection": "A",
             "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "Y",
             "lanes": [{}]},
        ],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data))
    return RoadNet.load(str(p))

def test_green_phases_excludes_all_red(tmp_path):
    rn = _net(tmp_path)
    assert rn.green_phases("A") == [0, 2]

def test_all_red_phase_is_first_empty(tmp_path):
    rn = _net(tmp_path)
    assert rn.all_red_phase("A") == 1

def test_phase_movements_maps_lane_ids(tmp_path):
    rn = _net(tmp_path)
    inc, out = rn.phase_movements("A", 0)   # roadLink 0: rin_0 -> rout_0
    assert inc == ["rin_0"] and out == ["rout_0"]
    inc2, out2 = rn.phase_movements("A", 2)  # roadLink 1: rin_1 -> rout_0
    assert inc2 == ["rin_1"] and out2 == ["rout_0"]
