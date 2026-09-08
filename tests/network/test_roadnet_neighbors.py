import json
import os

from traffic_rl.network.roadnet import RoadNet

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _signal(node_id, roads, road_links):
    return {
        "id": node_id, "virtual": False, "roads": roads,
        "roadLinks": road_links,
        "trafficLight": {"lightphases": [
            {"time": 40, "availableRoadLinks": [0]},
            {"time": 5, "availableRoadLinks": []},
            {"time": 40, "availableRoadLinks": [0]},
        ]},
    }


def _road(road_id, start, end, x0, x1):
    return {
        "id": road_id, "startIntersection": start, "endIntersection": end,
        "points": [{"x": x0, "y": 0}, {"x": x1, "y": 0}],
        "lanes": [{}],
    }


def _corridor_roadnet(tmp_path, allow_middle=True, continue_after_b=False):
    lane_links = ([{"startLaneIndex": 0, "endLaneIndex": 0}]
                  if allow_middle else [])
    data = {
        "intersections": [
            {"id": "entry", "virtual": True, "roads": ["entry_A"]},
            _signal("A", ["entry_A", "A_U"], [{
                "startRoad": "entry_A", "endRoad": "A_U",
                "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
            }]),
            {
                "id": "U", "virtual": False, "roads": ["A_U", "U_B"],
                "roadLinks": [{"startRoad": "A_U", "endRoad": "U_B",
                                "laneLinks": lane_links}],
                "trafficLight": {"lightphases": [
                    {"time": 30, "availableRoadLinks": [0]}]},
            },
            _signal("B", ["U_B", "B_next"], [{
                "startRoad": "U_B", "endRoad": "B_next",
                "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
            }]),
            ({
                "id": "U2", "virtual": False, "roads": ["B_next", "U2_C"],
                "roadLinks": [{
                    "startRoad": "B_next", "endRoad": "U2_C",
                    "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
                }],
                "trafficLight": {"lightphases": [
                    {"time": 30, "availableRoadLinks": [0]}]},
            } if continue_after_b else
             {"id": "exit", "virtual": True, "roads": ["B_next"]}),
        ],
        "roads": [
            _road("entry_A", "entry", "A", 0, 10),
            _road("A_U", "A", "U", 10, 30),
            _road("U_B", "U", "B", 30, 55),
            _road("B_next", "B", "U2" if continue_after_b else "exit", 55, 65),
        ],
    }
    if continue_after_b:
        data["intersections"].extend([
            _signal("C", ["U2_C", "C_exit"], [{
                "startRoad": "U2_C", "endRoad": "C_exit",
                "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
            }]),
            {"id": "exit", "virtual": True, "roads": ["C_exit"]},
        ])
        data["roads"].extend([
            _road("U2_C", "U2", "C", 65, 80),
            _road("C_exit", "C", "exit", 80, 90),
        ])
    path = tmp_path / "roadnet.json"
    path.write_text(json.dumps(data))
    return RoadNet.load(str(path))


def test_neighbors_follow_permitted_corridor_through_unsignalized_junction(tmp_path):
    roadnet = _corridor_roadnet(tmp_path)

    adjacency = roadnet.signal_adjacency()

    assert roadnet.downstream_neighbors("A") == ["B"]
    assert roadnet.upstream_neighbors("B") == ["A"]
    assert adjacency["directed_edges"] == [["A", "B"]]
    assert adjacency["edges"][0] == {
        "source": "A", "target": "B", "outgoing_road": "A_U",
        "road_path": ["A_U", "U_B"],
        "intermediate_intersections": ["U"],
        "road_hops": 2, "distance_coordinate_units": 45.0,
    }


def test_corridor_does_not_cross_controlled_or_unpermitted_boundary(tmp_path):
    roadnet = _corridor_roadnet(tmp_path, continue_after_b=True)
    # Even though B permits movement toward C, A must stop at the first signal B.
    assert roadnet.downstream_neighbors("A") == ["B"]
    assert roadnet.downstream_neighbors("B") == ["C"]
    assert ["A", "C"] not in roadnet.signal_adjacency()["directed_edges"]

    blocked = _corridor_roadnet(tmp_path, allow_middle=False)
    assert blocked.downstream_neighbors("A") == []


def test_signal_adjacency_is_cached_for_per_step_encoder_reads(tmp_path):
    roadnet = _corridor_roadnet(tmp_path)
    first = roadnet.signal_adjacency()

    assert roadnet.signal_adjacency() is first
    assert roadnet.upstream_neighbors("B") == ["A"]
    assert roadnet.downstream_neighbors("A") == ["B"]


def test_upstream_neighbors_on_haichau():
    rn = RoadNet.load(
        os.path.join(ROOT, "datasets/haichau_network_v2/roadnet.json")
    )
    sig = set(rn.signalized_ids())
    assert len(sig) == 53                       # sanity: the evaluated network
    adjacency = rn.signal_adjacency()
    with_nbr = 0
    for i in sig:
        nbrs = rn.upstream_neighbors(i)
        for n in nbrs:
            assert n in sig and n != i          # neighbours are signalized, not self
        assert len(nbrs) == len(set(nbrs))      # deduped
        if nbrs:
            with_nbr += 1
    assert adjacency["policy"]["selection"] == (
        "shortest_permitted_path_to_first_controlled_signal_per_outgoing_road")
    assert adjacency["policy"]["maximum_distance_coordinate_units"] is None
    assert adjacency["policy"]["maximum_road_hops"] is None
    assert adjacency["stats"]["covered_signals"] == 53
    assert adjacency["stats"]["isolated_signals"] == 0
    assert adjacency["stats"]["directed_edges"] == 154
    assert adjacency["stats"]["weak_components"] == 2
    assert adjacency["stats"]["distance_coordinate_units"]["p95"] < 1400
    assert adjacency["stats"]["distance_coordinate_units"]["max"] < 2700
