import json
from pathlib import Path

import pytest
import yaml

from traffic_rl.research.artifacts import sha256_file


def _write_inputs(root):
    dataset = root / "datasets" / "mini"
    dataset.mkdir(parents=True)
    docker_dir = root / "docker" / "cityflow-research"
    docker_dir.mkdir(parents=True)
    (docker_dir / "Dockerfile").write_text(
        "FROM cityflowproject/cityflow@sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32\n"
    )
    intersections, roads = [], []
    for branch in range(3):
        route = ["r%d0" % branch, "r%d1" % branch, "r%d2" % branch]
        west, first, second, east = "w%d" % branch, "a%d" % branch, "b%d" % branch, "e%d" % branch
        intersections.extend([
            {"id": west, "virtual": True, "roads": [route[0]]},
            {"id": first, "virtual": False, "roads": route[:2],
             "roadLinks": [{"startRoad": route[0], "endRoad": route[1], "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]}],
             "trafficLight": {"lightphases": [
                 {"time": 40, "availableRoadLinks": [0]},
                 {"time": 5, "availableRoadLinks": []},
                 {"time": 40, "availableRoadLinks": [0]},
                 {"time": 5, "availableRoadLinks": []},
             ]}},
            {"id": second, "virtual": False, "roads": route[1:],
             "roadLinks": [{"startRoad": route[1], "endRoad": route[2], "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]}],
             "trafficLight": {"lightphases": [
                 {"time": 40, "availableRoadLinks": [0]},
                 {"time": 5, "availableRoadLinks": []},
                 {"time": 40, "availableRoadLinks": [0]},
                 {"time": 5, "availableRoadLinks": []},
             ]}},
            {"id": east, "virtual": True, "roads": [route[2]]},
        ])
        roads.extend([
            {"id": route[0], "startIntersection": west, "endIntersection": first, "lanes": [{}]},
            {"id": route[1], "startIntersection": first, "endIntersection": second, "lanes": [{}]},
            {"id": route[2], "startIntersection": second, "endIntersection": east, "lanes": [{}]},
        ])
    roadnet = {"intersections": intersections, "roads": roads}
    roadnet_path = dataset / "roadnet.json"
    roadnet_path.write_text(json.dumps(roadnet))
    from traffic_rl.network.haichau_dataset import build_phase_contract
    from traffic_rl.network.roadnet import RoadNet
    phase_contract_path = dataset / "phase-contract.json"
    phase_contract_path.write_text(json.dumps(build_phase_contract(
        RoadNet.load(str(roadnet_path)), "mini", sha256_file(roadnet_path), 20
    ), sort_keys=True, separators=(",", ":")) + "\n")
    provenance_path = dataset / "provenance.json"
    provenance_path.write_text(
        json.dumps({"dataset_id": "mini", "expected_controlled_signals": 6})
    )
    config = {
        "schema_version": 2,
        "dataset_id": "mini",
        "roadnet": "datasets/mini/roadnet.json",
        "phase_contract": {"path": "datasets/mini/phase-contract.json",
                           "sha256": sha256_file(phase_contract_path)},
        "provenance": {"path": "datasets/mini/provenance.json",
                       "sha256": sha256_file(provenance_path)},
        "demand_label": "synthetic_test_demand",
        "route_count": 2,
        "min_controlled_signals_per_route": 2,
        "horizon_seconds": 60,
        "motorcycle_ratio": 1.0,
        "reference_interval_seconds": 10.0,
        "route_family_split": {"train": 0.5, "validation": 0.25, "test": 0.25},
        "regimes": {
            scenario: {"profile_bins": [
                {"start": 0, "end": 20, "source_hour": hours[0], "source_vehicle_count": counts[0]},
                {"start": 20, "end": 40, "source_hour": hours[1], "source_vehicle_count": counts[1]},
                {"start": 40, "end": 60, "source_hour": hours[2], "source_vehicle_count": counts[2]},
            ]}
            for scenario, hours, counts in (
                ("normal", ["12:00", "13:00", "14:00"], [100, 80, 90]),
                ("am_peak", ["07:00", "08:00", "09:00"], [70, 140, 100]),
                ("pm_peak", ["16:00", "17:00", "18:00"], [80, 120, 150]),
            )
        },
        "splits": {
            "train": {"demand_seeds": [11], "sim_seeds": [111]},
            "validation": {"demand_seeds": [31], "sim_seeds": [131]},
            "test": {"demand_seeds": [101], "sim_seeds": [201]},
        },
        "simulation": {"action_interval": 10, "min_green": 20},
        "preprocessing": {"count_norm": 20.0},
    }
    config_path = root / "mini.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    return config_path


def test_prepare_writes_hash_bound_cases(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare

    config_path = _write_inputs(tmp_path)
    manifest = prepare(config_path, tmp_path)
    assert manifest["protocol_version"] == 2
    assert len(manifest["cases"]) == 9
    assert all(len(case["flow_sha256"]) == 64 for case in manifest["cases"])
    assert manifest["network"]["controlled_signals"] == 6
    assert manifest["network"]["selectable_green_phases"] == 12
    assert manifest["network"]["path"] == "datasets/mini/roadnet.json"
    assert manifest["phase_contract"] == {
        "path": "datasets/mini/phase-contract.json",
        "sha256": sha256_file(tmp_path / "datasets/mini/phase-contract.json"),
    }
    assert manifest["runtime"]["base_image_digest"].startswith("sha256:")
    assert len(manifest["runtime"]["dockerfile"]["sha256"]) == 64

    for case in manifest["cases"]:
        flow_path = tmp_path / case["flow_path"]
        assert flow_path.is_file()
        assert len(json.loads(flow_path.read_text())) == 6
        assert flow_path.read_text().endswith("\n")

    route_catalog = manifest["route_families"]
    assert len(route_catalog["sha256"]) == 64
    families = json.loads((tmp_path / route_catalog["path"]).read_text())
    assert len(families) == 3
    assert {family["split"] for family in families} == {"train", "validation", "test"}

    manifest_path = tmp_path / "results" / "mini" / "experiment-manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest
    assert manifest_path.read_text().endswith("\n")


def test_prepare_refuses_generator_drift_without_new_version(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare

    config_path = _write_inputs(tmp_path)
    prepare(config_path, tmp_path)
    config = yaml.safe_load(config_path.read_text())
    config["reference_interval_seconds"] = 12.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(ValueError, match="existing manifest.*differs"):
        prepare(config_path, tmp_path)


def test_prepare_new_version_flag_allows_deliberate_rebuild(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare

    config_path = _write_inputs(tmp_path)
    old = prepare(config_path, tmp_path)
    config = yaml.safe_load(config_path.read_text())
    config["reference_interval_seconds"] = 12.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    new = prepare(config_path, tmp_path, new_version=True)
    assert old["generator_config_sha256"] != new["generator_config_sha256"]
