import json

import pytest

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import validate_disjoint_splits


def _chain_roadnet(tmp_path):
    intersections = [
        {"id": "west", "virtual": True, "roads": ["r0"]},
        {
            "id": "S1",
            "virtual": False,
            "roads": ["r0", "r1"],
            "roadLinks": [{"startRoad": "r0", "endRoad": "r1", "laneLinks": []}],
            "trafficLight": {
                "lightphases": [
                    {"availableRoadLinks": [0]},
                    {"availableRoadLinks": []},
                ]
            },
        },
        {
            "id": "S2",
            "virtual": False,
            "roads": ["r1", "r2"],
            "roadLinks": [{"startRoad": "r1", "endRoad": "r2", "laneLinks": []}],
            "trafficLight": {
                "lightphases": [
                    {"availableRoadLinks": [0]},
                    {"availableRoadLinks": []},
                ]
            },
        },
        {"id": "east", "virtual": True, "roads": ["r2"]},
    ]
    roads = [
        {"id": "r0", "startIntersection": "west", "endIntersection": "S1", "lanes": [{}]},
        {"id": "r1", "startIntersection": "S1", "endIntersection": "S2", "lanes": [{}]},
        {"id": "r2", "startIntersection": "S2", "endIntersection": "east", "lanes": [{}]},
    ]
    path = tmp_path / "chain.json"
    path.write_text(json.dumps({"intersections": intersections, "roads": roads}))
    return RoadNet.load(str(path))


def _config():
    return {
        "demand_label": "synthetic_osm_haichau_constrained_by_danang_profiles",
        "route_count": 4,
        "min_controlled_signals_per_route": 2,
        "horizon_seconds": 120,
        "motorcycle_ratio": 0.75,
        "regimes": {
            "normal": {"interval_seconds": 8.0},
            "am_peak": {"interval_seconds": 5.0},
            "pm_peak": {"interval_seconds": 4.0},
        },
        "splits": {
            "train": {"demand_seeds": [11], "sim_seeds": [111]},
            "validation": {"demand_seeds": [31], "sim_seeds": [131]},
            "test": {"demand_seeds": [101], "sim_seeds": [201]},
        },
    }


def test_routes_are_seeded_and_cross_multiple_signals(tmp_path):
    from traffic_rl.network.haichau_dataset import (
        count_controlled_signals,
        generate_routes,
    )

    roadnet = _chain_roadnet(tmp_path)
    a = generate_routes(roadnet, seed=11, route_count=4, min_signals=2)
    b = generate_routes(roadnet, seed=11, route_count=4, min_signals=2)
    assert a == b == [["r0", "r1", "r2"]] * 4
    assert all(count_controlled_signals(roadnet, route) >= 2 for route in a)


def test_route_generation_fails_closed_when_coverage_is_impossible(tmp_path):
    from traffic_rl.network.haichau_dataset import generate_routes

    with pytest.raises(ValueError, match="insufficient multi-signal routes"):
        generate_routes(_chain_roadnet(tmp_path), seed=11, route_count=1, min_signals=3)


def test_normal_am_pm_cases_use_disjoint_split_seeds(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    cases = build_flow_cases(_chain_roadnet(tmp_path), _config())
    validate_disjoint_splits(cases)
    assert len(cases) == 9
    assert {case["scenario"] for case in cases if case["split"] == "train"} == {
        "normal",
        "am_peak",
        "pm_peak",
    }
    assert {case["scale"] for case in cases} == {1.0, 1.6, 2.0}
    assert all(case["route_signal_histogram"] == {"2": 4} for case in cases)
    assert all(case["data_source_label"] == _config()["demand_label"] for case in cases)


def test_regimes_keep_route_and_vehicle_family_but_change_interval(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    cases = [
        case
        for case in build_flow_cases(_chain_roadnet(tmp_path), _config())
        if case["split"] == "train"
    ]
    by_scenario = {case["scenario"]: case for case in cases}
    normal = by_scenario["normal"]["flow"]
    am_peak = by_scenario["am_peak"]["flow"]
    assert [row["route"] for row in normal] == [row["route"] for row in am_peak]
    assert [row["vehicle"] for row in normal] == [row["vehicle"] for row in am_peak]
    assert {row["interval"] for row in normal} == {8.0}
    assert {row["interval"] for row in am_peak} == {5.0}
    assert all(row["startTime"] == 0 and row["endTime"] == 120 for row in normal)


def test_flow_case_builder_rejects_unpaired_simulation_seeds(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    config = _config()
    config["splits"]["train"]["sim_seeds"] = []
    with pytest.raises(ValueError, match="paired"):
        build_flow_cases(_chain_roadnet(tmp_path), config)
