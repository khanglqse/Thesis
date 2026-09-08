import json
import hashlib

import pytest

from traffic_rl.network.roadnet import RoadNet


def _roadnet(tmp_path, phases):
    road_links = [
        {"startRoad": "rin", "endRoad": "rout",
         "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0},
                       {"startLaneIndex": 0, "endLaneIndex": 1}]},
        {"startRoad": "rin", "endRoad": "rout",
         "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]},
    ]
    value = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": road_links,
            "trafficLight": {"lightphases": phases},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "in", "endIntersection": "A",
             "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "out",
             "lanes": [{}, {}]},
        ],
    }
    path = tmp_path / "roadnet.json"
    path.write_text(json.dumps(value))
    return RoadNet.load(str(path))


def test_short_subset_phases_are_transitions_between_selectable_greens(tmp_path):
    roadnet = _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 5, "availableRoadLinks": [0]},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 5, "availableRoadLinks": [1]},
    ])

    contract = roadnet.phase_contract("A")

    assert contract["selectable_phases"] == [0, 2]
    assert contract["transition_phases"] == [1, 3]
    assert roadnet.transition_sequence("A", 0, 2) == [(1, 5)]
    assert roadnet.transition_sequence("A", 2, 0) == [(3, 5)]
    assert contract["errors"] == []


def test_phase_movement_pairs_counts_lane_links_without_deduping_incoming(tmp_path):
    roadnet = _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 5, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 5, "availableRoadLinks": []},
    ])

    assert roadnet.phase_movement_pairs("A", 0) == [
        ("rin_0", "rout_0"), ("rin_0", "rout_1")]


def test_contract_fails_when_selectable_green_has_no_transition_path(tmp_path):
    roadnet = _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 40, "availableRoadLinks": [1]},
    ])

    contract = roadnet.phase_contract("A")

    assert any("transition path" in error for error in contract["errors"])
    with pytest.raises(ValueError, match="transition path"):
        roadnet.transition_sequence("A", 0, 1)


def test_audit_exposes_selectable_phases_transitions_and_errors(tmp_path):
    roadnet = _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 5, "availableRoadLinks": [0]},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 5, "availableRoadLinks": [1]},
    ])

    audit = roadnet.phase_contract_audit()

    assert audit["schema_version"] == 1
    assert audit["selectable_phases"] == {"A": [0, 2]}
    assert audit["transition_phases"] == {"A": [1, 3]}
    assert audit["transitions"] == {"A": {
        "0": {"2": [(1, 5)]}, "2": {"0": [(3, 5)]}}}
    assert audit["errors"] == {}


def test_explicit_contract_is_hash_bound_and_controls_roles(tmp_path):
    _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 10, "availableRoadLinks": [0]},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 5, "availableRoadLinks": []},
    ])
    roadnet_path = tmp_path / "roadnet.json"
    contract = {
        "schema_version": 1,
        "dataset_id": "fixture",
        "roadnet_sha256": hashlib.sha256(roadnet_path.read_bytes()).hexdigest(),
        "derivation": {"min_green_seconds": 20},
        "agents": {"A": {
            "selectable_phases": [0, 2],
            "transition_phases": [1, 3],
            "compound_phases": [1],
            "phase_semantics": [
                {"phase_index": 0, "duration_seconds": 40,
                 "source_state": "G", "role": "selectable_green"},
                {"phase_index": 1, "duration_seconds": 10,
                 "source_state": "g", "role": "compound_service"},
                {"phase_index": 2, "duration_seconds": 40,
                 "source_state": "G", "role": "selectable_green"},
                {"phase_index": 3, "duration_seconds": 5,
                 "source_state": "r", "role": "all_red"},
            ],
            "transitions": {
                "0": {"2": [[1, 10]]},
                "2": {"0": [[3, 5]]},
            },
        }},
    }
    contract_path = tmp_path / "phase-contract.json"
    contract_path.write_text(json.dumps(contract))

    roadnet = RoadNet.load(str(roadnet_path), str(contract_path),
                           require_phase_contract=True)

    assert roadnet.green_phases("A") == [0, 2]
    assert roadnet.transition_sequence("A", 0, 2) == [(1, 10)]
    assert roadnet.phase_role("A", 1) == "compound_service"


def test_explicit_contract_rejects_roadnet_hash_mismatch(tmp_path):
    _roadnet(tmp_path, [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 5, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 5, "availableRoadLinks": []},
    ])
    contract_path = tmp_path / "phase-contract.json"
    contract_path.write_text(json.dumps({"roadnet_sha256": "wrong"}))

    with pytest.raises(ValueError, match="roadnet_sha256"):
        RoadNet.load(str(tmp_path / "roadnet.json"), str(contract_path),
                     require_phase_contract=True)
