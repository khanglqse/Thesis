import hashlib
import json

import pytest

from scripts.prepare_haichau_viewer_network import build_viewer
from traffic_rl.eval.network_replay import validate_network
from traffic_rl.network.roadnet import RoadNet


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def test_builds_valid_geometry_in_manifest_agent_order(tmp_path):
    ids = ["N%02d" % index for index in range(53)]
    roadnet = tmp_path / "roadnet.json"
    roads = []
    intersections = [
        {"id": "entry", "virtual": True, "roads": ["entry_N00"],
         "roadLinks": [], "trafficLight": {"lightphases": []}},
        {"id": "exit", "virtual": True, "roads": ["N52_exit"],
         "roadLinks": [], "trafficLight": {"lightphases": []}},
    ]
    road_ids = ["entry_N00"] + ["N%02d_N%02d" % (i, i + 1)
                                  for i in range(52)] + ["N52_exit"]
    endpoints = [("entry", ids[0])] + list(zip(ids, ids[1:])) + [(ids[-1], "exit")]
    for index, (road_id, endpoints_pair) in enumerate(zip(road_ids, endpoints)):
        source, target = endpoints_pair
        roads.append({
            "id": road_id, "startIntersection": source, "endIntersection": target,
            "points": [{"x": index, "y": 0}, {"x": index + 1, "y": 0}],
            "lanes": [{}],
        })
    for index, node in enumerate(ids):
        intersections.append({
            "id": node, "virtual": False, "point": {"x": index, "y": index % 4},
            "roads": [road_ids[index], road_ids[index + 1]],
            "roadLinks": [{
                "startRoad": road_ids[index], "endRoad": road_ids[index + 1],
                "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
            }],
            "trafficLight": {"lightphases": [
                {"time": 40, "availableRoadLinks": [0]},
                {"time": 5, "availableRoadLinks": []},
            ]},
        })
    _write(roadnet, {
        "intersections": intersections,
        "roads": roads,
    })
    digest = hashlib.sha256(roadnet.read_bytes()).hexdigest()
    adjacency = RoadNet.load(str(roadnet)).signal_adjacency()
    manifest = tmp_path / "manifest.json"
    _write(manifest, {"network": {
        "path": "roadnet.json", "sha256": digest, "agent_ids": ids,
        "signal_adjacency": adjacency,
        "signal_adjacency_sha256": hashlib.sha256(json.dumps(
            adjacency, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }})

    result = build_viewer(tmp_path, "manifest.json", "release/viewer.json")
    document = json.loads((tmp_path / result["path"]).read_text())

    assert [node["id"] for node in document["nodes"]] == ids
    assert document["nodes"][0]["neighbors"] == [ids[1]]
    assert document["links"] == [
        {"source": ids[index], "target": ids[index + 1]}
        for index in range(52)]
    assert document["signal_adjacency_sha256"] == result["signal_adjacency_sha256"]
    assert validate_network(document) == set(ids)


def test_refuses_network_hash_drift(tmp_path):
    _write(tmp_path / "roadnet.json", {"intersections": [], "roads": []})
    _write(tmp_path / "manifest.json", {"network": {
        "path": "roadnet.json", "sha256": "0" * 64,
        "agent_ids": ["N%02d" % index for index in range(53)],
        "signal_adjacency": {},
        "signal_adjacency_sha256": "0" * 64,
    }})

    with pytest.raises(ValueError, match="network hash drift"):
        build_viewer(tmp_path, "manifest.json", "viewer.json")


def test_refuses_manifest_adjacency_that_differs_from_shared_derivation(tmp_path):
    ids = ["N%02d" % index for index in range(53)]
    intersections = [{
        "id": node, "virtual": False, "point": {"x": index, "y": 0},
        "roads": [], "roadLinks": [],
        "trafficLight": {"lightphases": [{}, {}]},
    } for index, node in enumerate(ids)]
    roadnet = tmp_path / "roadnet.json"
    _write(roadnet, {"intersections": intersections, "roads": []})
    digest = hashlib.sha256(roadnet.read_bytes()).hexdigest()
    adjacency = RoadNet.load(str(roadnet)).signal_adjacency()
    adjacency["directed_edges"] = [[ids[0], ids[1]]]
    _write(tmp_path / "manifest.json", {"network": {
        "path": "roadnet.json", "sha256": digest, "agent_ids": ids,
        "signal_adjacency": adjacency,
        "signal_adjacency_sha256": hashlib.sha256(json.dumps(
            adjacency, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }})

    with pytest.raises(ValueError, match="signal adjacency drift"):
        build_viewer(tmp_path, "manifest.json", "viewer.json")


def test_refuses_manifest_signal_adjacency_hash_drift(tmp_path):
    ids = ["N%02d" % index for index in range(53)]
    roadnet = tmp_path / "roadnet.json"
    _write(roadnet, {"intersections": [{
        "id": node, "virtual": False, "point": {"x": index, "y": 0},
        "roads": [], "roadLinks": [],
        "trafficLight": {"lightphases": [{}, {}]},
    } for index, node in enumerate(ids)], "roads": []})
    adjacency = RoadNet.load(str(roadnet)).signal_adjacency()
    _write(tmp_path / "manifest.json", {"network": {
        "path": "roadnet.json",
        "sha256": hashlib.sha256(roadnet.read_bytes()).hexdigest(),
        "agent_ids": ids, "signal_adjacency": adjacency,
        "signal_adjacency_sha256": "0" * 64,
    }})

    with pytest.raises(ValueError, match="signal adjacency hash drift"):
        build_viewer(tmp_path, "manifest.json", "viewer.json")
