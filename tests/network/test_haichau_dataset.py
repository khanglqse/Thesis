import json

import pytest


def _write_roadnet(tmp_path, data, name="roadnet.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def _mini_data():
    return {
        "intersections": [
            {"id": "west", "virtual": True, "roads": ["in"]},
            {
                "id": "signal",
                "virtual": False,
                "roads": ["in", "out"],
                "roadLinks": [
                    {
                        "startRoad": "in",
                        "endRoad": "out",
                        "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
                    },
                    {
                        "startRoad": "in",
                        "endRoad": "out",
                        "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
                    },
                ],
                "trafficLight": {
                    "lightphases": [
                        {"time": 30, "availableRoadLinks": [0]},
                        {"time": 5, "availableRoadLinks": [0]},
                        {"time": 30, "availableRoadLinks": [1]},
                        {"time": 5, "availableRoadLinks": []},
                    ]
                },
            },
            {"id": "east", "virtual": True, "roads": ["out"]},
        ],
        "roads": [
            {
                "id": "in",
                "startIntersection": "west",
                "endIntersection": "signal",
                "lanes": [{}],
            },
            {
                "id": "out",
                "startIntersection": "signal",
                "endIntersection": "east",
                "lanes": [{}],
            },
        ],
    }


def test_audit_network_counts_only_multi_phase_signals(tmp_path):
    from traffic_rl.network.haichau_dataset import audit_network

    data = _mini_data()
    data["intersections"].insert(
        2,
        {
            "id": "decorative",
            "virtual": False,
            "roads": [],
            "roadLinks": [],
            "trafficLight": {"lightphases": [{"availableRoadLinks": []}]},
        },
    )
    report = audit_network(_write_roadnet(tmp_path, data))
    assert report == {
        "roads": 2,
        "lanes": 2,
        "intersections": 4,
        "controlled_signals": 1,
        "selectable_green_phases": 2,
        "transition_phases": 2,
        "agent_selectable_phase_counts": {"signal": 2},
        "agent_ids": ["signal"],
        "directed_signal_edges": [],
        "weak_components": 1,
        "phase_errors": [],
    }


def test_audit_network_builds_sorted_signal_adjacency(tmp_path):
    from traffic_rl.network.haichau_dataset import audit_network

    data = {
        "intersections": [
            {
                "id": signal,
                "virtual": False,
                "roads": [],
                "roadLinks": [],
                "trafficLight": {
                    "lightphases": [
                        {"availableRoadLinks": []},
                        {"availableRoadLinks": []},
                    ]
                },
            }
            for signal in ("B", "A", "C")
        ],
        "roads": [
            {"id": "ab", "startIntersection": "A", "endIntersection": "B", "lanes": [{}]},
        ],
    }
    report = audit_network(_write_roadnet(tmp_path, data))
    assert report["agent_ids"] == ["A", "B", "C"]
    assert report["directed_signal_edges"] == [["A", "B"]]
    assert report["weak_components"] == 2


def test_audit_network_reports_missing_roads_and_invalid_lane_indices(tmp_path):
    from traffic_rl.network.haichau_dataset import audit_network

    data = _mini_data()
    road_link = data["intersections"][1]["roadLinks"][0]
    road_link["startRoad"] = "missing"
    road_link["laneLinks"][0]["endLaneIndex"] = 9
    report = audit_network(_write_roadnet(tmp_path, data))
    assert any("missing road" in error for error in report["phase_errors"])
    assert any("lane index" in error for error in report["phase_errors"])


def test_audit_network_reports_invalid_phase_road_link_index(tmp_path):
    from traffic_rl.network.haichau_dataset import audit_network

    data = _mini_data()
    data["intersections"][1]["trafficLight"]["lightphases"][0][
        "availableRoadLinks"
    ] = [7]
    report = audit_network(_write_roadnet(tmp_path, data))
    assert any("roadLink index" in error for error in report["phase_errors"])


def test_audit_network_rejects_agent_with_fewer_than_two_movement_phases(tmp_path):
    from traffic_rl.network.haichau_dataset import audit_network

    data = _mini_data()
    data["intersections"][1]["trafficLight"]["lightphases"][2][
        "availableRoadLinks"
    ] = []
    report = audit_network(_write_roadnet(tmp_path, data))
    assert report["agent_selectable_phase_counts"] == {"signal": 1}
    assert any("fewer than two selectable green phases" in error
               for error in report["phase_errors"])


def test_phase_contract_excludes_short_movement_phase_and_maps_every_switch(tmp_path):
    from traffic_rl.network.haichau_dataset import build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    roadnet = RoadNet.load(str(_write_roadnet(tmp_path, _mini_data())))
    contract = build_phase_contract(roadnet, "mini", "a" * 64, 20)
    signal = contract["agents"]["signal"]
    assert signal["selectable_phases"] == [0, 2]
    assert signal["transition_phases"] == [1, 3]
    assert signal["transitions"] == {
        "0": {"2": [[1, 5]]},
        "2": {"0": [[3, 5]]},
    }


def test_phase_contract_rejects_adjacent_selectable_phases_without_transition(tmp_path):
    from traffic_rl.network.haichau_dataset import build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    data = _mini_data()
    phases = data["intersections"][1]["trafficLight"]["lightphases"]
    data["intersections"][1]["trafficLight"]["lightphases"] = [phases[0], phases[2]]
    roadnet = RoadNet.load(str(_write_roadnet(tmp_path, data)))
    with pytest.raises(ValueError, match="transition"):
        build_phase_contract(roadnet, "mini", "a" * 64, 20)


def test_canonical_network_has_53_agents_with_two_movement_phases():
    from pathlib import Path

    from traffic_rl.network.haichau_dataset import audit_network, build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    root = Path(__file__).resolve().parents[2]
    network_path = root / "datasets/haichau_network_v2/roadnet.json"
    contract_path = root / "datasets/haichau_network_v2/phase-contract.json"
    contract = json.loads(contract_path.read_text())
    roadnet = RoadNet.load(str(network_path))
    assert contract == build_phase_contract(
        roadnet,
        "haichau_network_v2",
        "a65a6edea00a44ea9e51da75db47aa88c08025a725e1dd07cf2f908093607ca1",
        20,
    )
    report = audit_network(network_path, contract)
    assert report["controlled_signals"] == 53
    assert report["selectable_green_phases"] == 107
    assert report["transition_phases"] == 127
    assert min(report["agent_selectable_phase_counts"].values()) >= 2
    for agent in contract["agents"].values():
        assert set(agent["selectable_phases"]).isdisjoint(agent["transition_phases"])
        for source in agent["selectable_phases"]:
            assert set(agent["transitions"][str(source)]) == {
                str(target) for target in agent["selectable_phases"] if target != source
            }
            assert all(agent["transitions"][str(source)].values())
    assert report["phase_errors"] == []
