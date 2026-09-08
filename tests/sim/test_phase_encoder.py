import json

import numpy as np

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder


def _write_roadnet(tmp_path, name, intersections, roads):
    path = tmp_path / (name + ".json")
    path.write_text(json.dumps({"intersections": intersections, "roads": roads}))
    return RoadNet.load(str(path))


def _single_signal_roadnet(tmp_path, name, served_lane):
    other_lane = 1 - served_lane
    intersections = [{
        "id": name,
        "virtual": False,
        "roads": ["%s_in" % name, "%s_out" % name],
        "roadLinks": [
            {"startRoad": "%s_in" % name, "endRoad": "%s_out" % name,
             "laneLinks": [{"startLaneIndex": served_lane, "endLaneIndex": 0}]},
            {"startRoad": "%s_in" % name, "endRoad": "%s_out" % name,
             "laneLinks": [{"startLaneIndex": other_lane, "endLaneIndex": 1}]},
        ],
        "trafficLight": {"lightphases": [
            {"availableRoadLinks": [0]},
            {"availableRoadLinks": []},
        ]},
    }]
    roads = [
        {"id": "%s_in" % name, "startIntersection": "%s_boundary_in" % name,
         "endIntersection": name, "lanes": [{}, {}]},
        {"id": "%s_out" % name, "startIntersection": name,
         "endIntersection": "%s_boundary_out" % name, "lanes": [{}, {}]},
    ]
    return _write_roadnet(tmp_path, name, intersections, roads)


def test_phase_features_follow_served_movements_not_lane_position(tmp_path):
    roadnet_a = _single_signal_roadnet(tmp_path, "A", served_lane=0)
    roadnet_b = _single_signal_roadnet(tmp_path, "B", served_lane=1)
    encoder_a = PhaseFeatureEncoder(roadnet_a, 20.0, 40.0)
    encoder_b = PhaseFeatureEncoder(roadnet_b, 20.0, 40.0)

    features_a, mask_a = encoder_a.encode_all(
        "A", {"A_in_0": 8, "A_out_0": 5},
        {"A_in_0": 6, "A_out_0": 2}, 0, 20, [30])
    features_b, mask_b = encoder_b.encode_all(
        "B", {"B_in_1": 8, "B_out_0": 5},
        {"B_in_1": 6, "B_out_0": 2}, 0, 20, [30])

    np.testing.assert_allclose(features_a[0, :6], features_b[0, :6])
    assert mask_a.tolist() == mask_b.tolist() == [True]


def test_neighbor_features_include_upstream_and_downstream(tmp_path):
    intersections = []
    roads = []
    names = ["upstream", "middle", "downstream"]
    connections = [("boundary", "upstream"), ("upstream", "middle"),
                   ("middle", "downstream"), ("downstream", "exit")]
    for start, end in connections:
        roads.append({"id": "%s_to_%s" % (start, end),
                      "startIntersection": start, "endIntersection": end,
                      "lanes": [{}]})
    for idx, name in enumerate(names):
        incoming = roads[idx]["id"]
        outgoing = roads[idx + 1]["id"]
        intersections.append({
            "id": name, "virtual": False, "roads": [incoming, outgoing],
            "roadLinks": [{
                "startRoad": incoming, "endRoad": outgoing,
                "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
            }],
            "trafficLight": {"lightphases": [
                {"availableRoadLinks": [0]}, {"availableRoadLinks": []},
            ]},
        })
    roadnet = _write_roadnet(tmp_path, "chain", intersections, roads)
    encoder = PhaseFeatureEncoder(roadnet, 20.0, 40.0)
    waits = {"boundary_to_upstream_0": 6, "upstream_to_middle_0": 4,
             "middle_to_downstream_0": 3}
    features, _ = encoder.encode_all(
        "middle", dict(waits), waits, 0, 30, [10])

    assert roadnet.downstream_neighbors("middle") == ["downstream"]
    assert features[0, 8] > 0
    assert features[0, 9] > 0


def test_padded_phase_rows_are_zero_and_masked(tmp_path):
    roadnet = _single_signal_roadnet(tmp_path, "A", served_lane=0)
    encoder = PhaseFeatureEncoder(roadnet, 20.0, 40.0, max_green=3)
    features, mask = encoder.encode_all("A", {}, {}, 0, 0, [0])

    assert features.shape == (3, 12)
    assert mask.tolist() == [True, False, False]
    np.testing.assert_array_equal(features[1:], np.zeros((2, 12), np.float32))

