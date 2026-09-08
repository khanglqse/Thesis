import json


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
                    }
                ],
                "trafficLight": {
                    "lightphases": [
                        {"time": 30, "availableRoadLinks": [0]},
                        {"time": 3, "availableRoadLinks": []},
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
        "intersections": 4,
        "controlled_signals": 1,
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
