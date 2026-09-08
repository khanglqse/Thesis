import json
from collections import Counter
from xml.etree import ElementTree

import pytest

from traffic_rl.research.artifacts import canonical_sha256, sha256_file


def _write_roadnet(tmp_path, data, name="roadnet.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def _write_sumo(tmp_path, phases=None):
    phases = phases or [(30, "G"), (5, "y"), (30, "G"), (5, "r")]
    root = ElementTree.Element("net")
    logic = ElementTree.SubElement(root, "tlLogic", id="signal")
    for duration, state in phases:
        ElementTree.SubElement(
            logic, "phase", duration=str(duration), state=state
        )
    path = tmp_path / "source.net.xml"
    ElementTree.ElementTree(root).write(str(path))
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
    adjacency = report.pop("signal_adjacency")
    adjacency_sha256 = report.pop("signal_adjacency_sha256")
    assert adjacency_sha256 == canonical_sha256(adjacency)
    assert adjacency["stats"]["controlled_signals"] == 1
    assert adjacency["stats"]["isolated_signals"] == 1
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
            {"id": "V", "virtual": True, "roads": ["va"],
             "roadLinks": [], "trafficLight": {"lightphases": []}},
        ] + [{
                "id": signal,
                "virtual": False,
                "roads": (["va", "ab"] if signal == "A" else ["ab"]
                          if signal == "B" else []),
                "roadLinks": ([{
                    "startRoad": "va", "endRoad": "ab",
                    "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}],
                }] if signal == "A" else []),
                "trafficLight": {
                    "lightphases": [
                        {"time": 40, "availableRoadLinks": ([0] if signal == "A" else [])},
                        {"time": 40, "availableRoadLinks": ([0] if signal == "A" else [])},
                    ]
                },
            } for signal in ("B", "A", "C")],
        "roads": [
            {"id": "va", "startIntersection": "V", "endIntersection": "A",
             "points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}], "lanes": [{}]},
            {"id": "ab", "startIntersection": "A", "endIntersection": "B",
             "points": [{"x": 1, "y": 0}, {"x": 2, "y": 0}], "lanes": [{}]},
        ],
    }
    report = audit_network(_write_roadnet(tmp_path, data))
    assert report["agent_ids"] == ["A", "B", "C"]
    assert report["directed_signal_edges"] == [["A", "B"]]
    assert report["weak_components"] == 2
    assert report["signal_adjacency"]["directed_edges"] == [["A", "B"]]


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
    sumo_path = _write_sumo(tmp_path)
    contract = build_phase_contract(
        roadnet, "mini", "a" * 64, 20, sumo_path,
        {"path": "source.net.xml", "sha256": sha256_file(sumo_path)}, []
    )
    signal = contract["agents"]["signal"]
    assert signal["selectable_phases"] == [0, 2]
    assert signal["transition_phases"] == [1, 3]
    assert signal["transitions"] == {
        "0": {"2": [[1, 5]]},
        "2": {"0": [[3, 5]]},
    }
    assert signal["compound_phases"] == []
    assert [item["role"] for item in signal["phase_semantics"]] == [
        "selectable_green", "clearance_yellow", "selectable_green", "all_red"
    ]
    assert signal["source_tl_logic_id"] == "signal"


def test_phase_contract_rejects_adjacent_selectable_phases_without_transition(tmp_path):
    from traffic_rl.network.haichau_dataset import build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    data = _mini_data()
    phases = data["intersections"][1]["trafficLight"]["lightphases"]
    data["intersections"][1]["trafficLight"]["lightphases"] = [phases[0], phases[2]]
    roadnet = RoadNet.load(str(_write_roadnet(tmp_path, data)))
    sumo_path = _write_sumo(tmp_path, [(30, "G"), (30, "G")])
    with pytest.raises(ValueError, match="transition"):
        build_phase_contract(
            roadnet, "mini", "a" * 64, 20, sumo_path,
            {"path": "source.net.xml", "sha256": sha256_file(sumo_path)}, []
        )


def test_canonical_network_has_53_agents_with_two_movement_phases():
    from pathlib import Path

    from traffic_rl.network.haichau_dataset import audit_network, build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    root = Path(__file__).resolve().parents[2]
    network_path = root / "datasets/haichau_network_v2/roadnet.json"
    contract_path = root / "datasets/haichau_network_v2/phase-contract.json"
    contract = json.loads(contract_path.read_text())
    provenance = json.loads(
        (root / "datasets/haichau_network_v2/provenance.json").read_text()
    )
    sumo_record = next(
        record for record in provenance["source_artifacts"]
        if record["role"] == "sumo_network"
    )
    sumo_path = root / sumo_record["path"]
    roadnet = RoadNet.load(str(network_path))
    assert contract == build_phase_contract(
        roadnet,
        "haichau_network_v2",
        "a65a6edea00a44ea9e51da75db47aa88c08025a725e1dd07cf2f908093607ca1",
        20,
        sumo_path,
        {"path": sumo_record["path"], "sha256": sumo_record["sha256"]},
        provenance["repairs"],
    )
    report = audit_network(
        network_path,
        contract,
        20,
        sumo_path,
        {"path": sumo_record["path"], "sha256": sumo_record["sha256"]},
        provenance["repairs"],
    )
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


def test_canonical_phase_contract_aligns_all_53_sumo_tllogics():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "datasets/haichau_network_v2/phase-contract.json").read_text()
    )
    sumo_root = ElementTree.parse(
        str(root / contract["source_sumo_network"]["path"])
    ).getroot()
    tl_logics = {item.attrib["id"]: item for item in sumo_root.findall("tlLogic")}

    assert len(contract["agents"]) == 53
    compound_count = 0
    for agent_id, agent in contract["agents"].items():
        source = tl_logics[agent["source_tl_logic_id"]]
        source_phases = source.findall("phase")
        if agent_id == "5896811072":
            assert agent["source_alignment"] == "synthetic_engineering_normalization"
            assert [item["source_phase_index"] for item in agent["phase_semantics"]] == [0, 1, 0, 2]
        else:
            assert agent["source_alignment"] == "exact_phase_order_duration_and_state"
            assert len(source_phases) == len(agent["phase_semantics"])
            for index, semantic in enumerate(agent["phase_semantics"]):
                assert semantic["source_phase_index"] == index
                assert semantic["source_state"] == source_phases[index].attrib["state"]
                assert semantic["duration_seconds"] == int(float(source_phases[index].attrib["duration"]))
        for phase_index in agent["compound_phases"]:
            semantic = agent["phase_semantics"][phase_index]
            assert semantic["role"] == "compound_service"
            assert "g" in semantic["source_state"].lower()
            assert "y" not in semantic["source_state"].lower()
            assert semantic["duration_seconds"] < 20
            assert semantic["movements"]
            compound_count += 1
    assert compound_count == 10
    assert Counter(
        item["role"]
        for agent in contract["agents"].values()
        for item in agent["phase_semantics"]
    ) == {
        "selectable_green": 107,
        "compound_service": 10,
        "clearance_yellow": 116,
        "all_red": 1,
    }
