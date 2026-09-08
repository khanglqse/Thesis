import json
from pathlib import Path

import pytest

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import validate_disjoint_splits


def _parallel_roadnet(tmp_path):
    intersections = []
    roads = []
    for branch in range(3):
        west, first, second, east = (
            "west%d" % branch, "S%dA" % branch, "S%dB" % branch, "east%d" % branch
        )
        route = ["r%d0" % branch, "r%d1" % branch, "r%d2" % branch]
        intersections.extend([
            {"id": west, "virtual": True, "roads": [route[0]]},
            {"id": first, "virtual": False, "roads": route[:2],
             "roadLinks": [{"startRoad": route[0], "endRoad": route[1], "laneLinks": []}],
             "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": []}]}},
            {"id": second, "virtual": False, "roads": route[1:],
             "roadLinks": [{"startRoad": route[1], "endRoad": route[2], "laneLinks": []}],
             "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": []}]}},
            {"id": east, "virtual": True, "roads": [route[2]]},
        ])
        roads.extend([
            {"id": route[0], "startIntersection": west, "endIntersection": first, "lanes": [{}]},
            {"id": route[1], "startIntersection": first, "endIntersection": second, "lanes": [{}]},
            {"id": route[2], "startIntersection": second, "endIntersection": east, "lanes": [{}]},
        ])
    path = tmp_path / "parallel.json"
    path.write_text(json.dumps({"intersections": intersections, "roads": roads}))
    return RoadNet.load(str(path))


def _config():
    bins = {
        "normal": [("12:00", 100), ("13:00", 80), ("14:00", 90)],
        "am_peak": [("07:00", 70), ("08:00", 140), ("09:00", 100)],
        "pm_peak": [("16:00", 80), ("17:00", 120), ("18:00", 150)],
    }
    return {
        "demand_label": "synthetic_osm_haichau_constrained_by_danang_profiles",
        "route_count": 4,
        "min_controlled_signals_per_route": 2,
        "horizon_seconds": 120,
        "motorcycle_ratio": 0.75,
        "reference_interval_seconds": 8.0,
        "route_family_split": {"train": 0.5, "validation": 0.25, "test": 0.25},
        "regimes": {
            scenario: {
                "profile_bins": [
                    {"start": index * 40, "end": (index + 1) * 40,
                     "source_hour": hour, "source_vehicle_count": count}
                    for index, (hour, count) in enumerate(values)
                ]
            }
            for scenario, values in bins.items()
        },
        "splits": {
            "train": {"demand_seeds": [11], "sim_seeds": [111]},
            "validation": {"demand_seeds": [31], "sim_seeds": [131]},
            "test": {"demand_seeds": [101], "sim_seeds": [201]},
        },
    }


def test_route_catalog_is_stable_and_partitioned_without_overlap(tmp_path):
    from traffic_rl.network.haichau_dataset import build_route_catalog, partition_route_families

    roadnet = _parallel_roadnet(tmp_path)
    catalog = build_route_catalog(roadnet, min_signals=2)
    assert catalog == build_route_catalog(roadnet, min_signals=2)
    assert len(catalog) == 3
    partitions = partition_route_families(catalog, _config()["route_family_split"])
    identities = {split: {f["route_sha256"] for f in families}
                  for split, families in partitions.items()}
    assert all(identities.values())
    assert identities["train"].isdisjoint(identities["validation"])
    assert identities["train"].isdisjoint(identities["test"])
    assert identities["validation"].isdisjoint(identities["test"])


def test_route_catalog_fails_closed_when_coverage_is_impossible(tmp_path):
    from traffic_rl.network.haichau_dataset import build_route_catalog

    with pytest.raises(ValueError, match="insufficient multi-signal route families"):
        build_route_catalog(_parallel_roadnet(tmp_path), min_signals=3)


def test_cases_sample_only_their_disjoint_route_partition(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    cases, catalog = build_flow_cases(_parallel_roadnet(tmp_path), _config(), include_catalog=True)
    validate_disjoint_splits(cases)
    by_split = {split: {h for case in cases if case["split"] == split
                        for h in case["route_family_hashes"]}
                for split in ("train", "validation", "test")}
    assert by_split["train"].isdisjoint(by_split["validation"])
    assert by_split["train"].isdisjoint(by_split["test"])
    assert by_split["validation"].isdisjoint(by_split["test"])
    assert {family["split"] for family in catalog} == {"train", "validation", "test"}


def test_temporal_profiles_stagger_streams_and_change_within_hour_shape(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    cases = build_flow_cases(_parallel_roadnet(tmp_path), _config())
    train = {case["scenario"]: case for case in cases if case["split"] == "train"}
    assert len(train["normal"]["flow"]) == 12
    for case in train.values():
        assert len({row["startTime"] for row in case["flow"]}) > 3
        assert sum(item["scheduled"] for item in case["scheduled_departures_by_bin"]) == case["scheduled_vehicles"]
    normal = [item["interval_seconds"] for item in train["normal"]["temporal_profile"]]
    am_peak = [item["interval_seconds"] for item in train["am_peak"]["temporal_profile"]]
    pm_peak = [item["interval_seconds"] for item in train["pm_peak"]["temporal_profile"]]
    assert len(set(normal)) == 3
    assert am_peak != normal
    assert pm_peak != normal


def test_same_seed_regimes_keep_route_and_vehicle_stream_family(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    cases = [case for case in build_flow_cases(_parallel_roadnet(tmp_path), _config())
             if case["split"] == "train"]
    by_scenario = {case["scenario"]: case for case in cases}
    assert by_scenario["normal"]["route_family_hashes"] == by_scenario["am_peak"]["route_family_hashes"]
    assert [row["route"] for row in by_scenario["normal"]["flow"][:4]] == [row["route"] for row in by_scenario["am_peak"]["flow"][:4]]
    assert [row["vehicle"] for row in by_scenario["normal"]["flow"][:4]] == [row["vehicle"] for row in by_scenario["am_peak"]["flow"][:4]]


def test_flow_case_builder_rejects_unpaired_simulation_seeds(tmp_path):
    from traffic_rl.network.haichau_dataset import build_flow_cases

    config = _config()
    config["splits"]["train"]["sim_seeds"] = []
    with pytest.raises(ValueError, match="paired"):
        build_flow_cases(_parallel_roadnet(tmp_path), config)


def test_real_dataset_route_family_splits_are_pairwise_disjoint():
    import yaml
    from traffic_rl.network.haichau_dataset import build_flow_cases

    root = Path(__file__).resolve().parents[2]
    roadnet = RoadNet.load(str(root / "datasets/haichau_network_v2/roadnet.json"))
    config = yaml.safe_load((root / "configs/haichau_network_v2.yaml").read_text())
    cases = build_flow_cases(roadnet, config)
    by_split = {split: {h for case in cases if case["split"] == split
                        for h in case["route_family_hashes"]}
                for split in ("train", "validation", "test")}
    assert all(by_split.values())
    assert by_split["train"].isdisjoint(by_split["validation"])
    assert by_split["train"].isdisjoint(by_split["test"])
    assert by_split["validation"].isdisjoint(by_split["test"])
