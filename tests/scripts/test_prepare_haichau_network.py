import json
from pathlib import Path

import pytest
import yaml


def _write_inputs(root):
    dataset = root / "datasets" / "mini"
    dataset.mkdir(parents=True)
    roadnet = {
        "intersections": [
            {"id": "west", "virtual": True, "roads": ["in"]},
            {
                "id": "signal",
                "virtual": False,
                "roads": ["in", "out"],
                "roadLinks": [
                    {"startRoad": "in", "endRoad": "out", "laneLinks": []}
                ],
                "trafficLight": {
                    "lightphases": [
                        {"availableRoadLinks": [0]},
                        {"availableRoadLinks": []},
                    ]
                },
            },
            {"id": "east", "virtual": True, "roads": ["out"]},
        ],
        "roads": [
            {"id": "in", "startIntersection": "west", "endIntersection": "signal", "lanes": [{}]},
            {"id": "out", "startIntersection": "signal", "endIntersection": "east", "lanes": [{}]},
        ],
    }
    (dataset / "roadnet.json").write_text(json.dumps(roadnet))
    (dataset / "provenance.json").write_text(
        json.dumps({"dataset_id": "mini", "expected_controlled_signals": 1})
    )
    config = {
        "schema_version": 2,
        "dataset_id": "mini",
        "roadnet": "datasets/mini/roadnet.json",
        "demand_label": "synthetic_test_demand",
        "route_count": 2,
        "min_controlled_signals_per_route": 1,
        "horizon_seconds": 60,
        "motorcycle_ratio": 1.0,
        "regimes": {"normal": {"interval_seconds": 10.0}},
        "splits": {
            "train": {"demand_seeds": [11], "sim_seeds": [111]},
            "validation": {"demand_seeds": [31], "sim_seeds": [131]},
            "test": {"demand_seeds": [101], "sim_seeds": [201]},
        },
        "simulation": {"action_interval": 10},
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
    assert len(manifest["cases"]) == 3
    assert all(len(case["flow_sha256"]) == 64 for case in manifest["cases"])
    assert manifest["network"]["controlled_signals"] == 1
    assert manifest["network"]["path"] == "datasets/mini/roadnet.json"
    assert manifest["runtime"]["image_digest"].startswith("sha256:")

    for case in manifest["cases"]:
        flow_path = tmp_path / case["flow_path"]
        assert flow_path.is_file()
        assert json.loads(flow_path.read_text())[0]["route"] == ["in", "out"]
        assert flow_path.read_text().endswith("\n")

    manifest_path = tmp_path / "results" / "mini" / "experiment-manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest
    assert manifest_path.read_text().endswith("\n")


def test_prepare_refuses_generator_drift_without_new_version(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare

    config_path = _write_inputs(tmp_path)
    prepare(config_path, tmp_path)
    config = yaml.safe_load(config_path.read_text())
    config["horizon_seconds"] = 120
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(ValueError, match="existing manifest.*differs"):
        prepare(config_path, tmp_path)


def test_prepare_new_version_flag_allows_deliberate_rebuild(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare

    config_path = _write_inputs(tmp_path)
    old = prepare(config_path, tmp_path)
    config = yaml.safe_load(config_path.read_text())
    config["horizon_seconds"] = 120
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    new = prepare(config_path, tmp_path, new_version=True)
    assert old["generator_config_sha256"] != new["generator_config_sha256"]
