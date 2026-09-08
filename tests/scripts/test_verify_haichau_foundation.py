import copy
import json

import pytest
import yaml

from traffic_rl.research.artifacts import sha256_file


RUNTIME_DIGEST = "sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32"


@pytest.fixture
def valid_foundation(tmp_path):
    dataset = tmp_path / "datasets" / "fixture"
    demands = tmp_path / "results" / "fixture" / "demands"
    dataset.mkdir(parents=True)
    demands.mkdir(parents=True)

    intersections = []
    for index in range(53):
        intersections.append(
            {
                "id": "signal-%02d" % index,
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
        )
    roadnet_path = dataset / "roadnet.json"
    roadnet_path.write_text(json.dumps({"intersections": intersections, "roads": []}))
    provenance_path = dataset / "provenance.json"
    provenance_path.write_text(
        json.dumps(
            {
                "dataset_id": "fixture",
                "roadnet_expected_sha256": sha256_file(roadnet_path),
                "expected_controlled_signals": 53,
            }
        )
    )
    config = {
        "schema_version": 2,
        "dataset_id": "fixture",
        "roadnet": "datasets/fixture/roadnet.json",
        "demand_label": "synthetic_osm_haichau_constrained_by_danang_profiles",
        "route_count": 1,
        "min_controlled_signals_per_route": 2,
        "regimes": {
            "normal": {"interval_seconds": 72.0},
            "am_peak": {"interval_seconds": 45.0},
            "pm_peak": {"interval_seconds": 36.0},
        },
    }
    config_path = tmp_path / "fixture.yaml"
    config_path.write_text(yaml.safe_dump(config))

    split_seeds = {"train": [11, 12, 13], "validation": [31, 32], "test": [101, 102, 103, 104, 105]}
    cases = []
    for split, seeds in split_seeds.items():
        for seed in seeds:
            for scenario in ("normal", "am_peak", "pm_peak"):
                case_id = "%s_%s_demand%s" % (split, scenario, seed)
                flow_path = demands / (case_id + ".json")
                flow_path.write_text(json.dumps([{"case_id": case_id}]))
                cases.append(
                    {
                        "case_id": case_id,
                        "split": split,
                        "scenario": scenario,
                        "demand_seed": seed,
                        "sim_seed": seed + 100,
                        "flow_path": flow_path.relative_to(tmp_path).as_posix(),
                        "flow_sha256": sha256_file(flow_path),
                        "route_signal_histogram": {"2": 1},
                        "data_source_label": config["demand_label"],
                    }
                )
    agent_ids = sorted(intersection["id"] for intersection in intersections)
    manifest = {
        "protocol_version": 2,
        "dataset_id": "fixture",
        "data_source_label": config["demand_label"],
        "generator_config_path": config_path.relative_to(tmp_path).as_posix(),
        "generator_config_sha256": sha256_file(config_path),
        "network": {
            "path": roadnet_path.relative_to(tmp_path).as_posix(),
            "sha256": sha256_file(roadnet_path),
            "provenance": {
                "path": provenance_path.relative_to(tmp_path).as_posix(),
                "sha256": sha256_file(provenance_path),
            },
            "roads": 0,
            "intersections": 53,
            "controlled_signals": 53,
            "agent_ids": agent_ids,
            "directed_signal_edges": [],
            "weak_components": 53,
            "phase_errors": [],
        },
        "cases": cases,
        "runtime": {
            "image": "cityflowproject/cityflow",
            "image_digest": RUNTIME_DIGEST,
            "platform": "linux/amd64",
        },
    }
    return tmp_path, manifest


def test_foundation_verifier_accepts_hash_bound_complete_family(valid_foundation):
    from scripts.verify_haichau_foundation import verify_foundation

    root, manifest = valid_foundation
    report = verify_foundation(root, manifest)
    assert report["controlled_signals"] == 53
    assert report["cases"] == 30
    assert report["split_counts"] == {"test": 15, "train": 9, "validation": 6}


def test_foundation_verifier_rejects_wrong_agent_count(valid_foundation):
    from scripts.verify_haichau_foundation import verify_foundation

    root, manifest = valid_foundation
    manifest["network"]["controlled_signals"] = 52
    with pytest.raises(ValueError, match="controlled signal count"):
        verify_foundation(root, manifest)


def test_foundation_verifier_rejects_flow_hash_drift(valid_foundation):
    from scripts.verify_haichau_foundation import verify_foundation

    root, manifest = valid_foundation
    flow_path = root / manifest["cases"][0]["flow_path"]
    flow_path.write_text("[]")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_foundation(root, manifest)


def test_foundation_verifier_rejects_incomplete_seed_scenario_family(valid_foundation):
    from scripts.verify_haichau_foundation import verify_foundation

    root, manifest = valid_foundation
    manifest["cases"][0]["scenario"] = "surge"
    with pytest.raises(ValueError, match="scenario coverage"):
        verify_foundation(root, manifest)


def test_foundation_verifier_rejects_runtime_digest_drift(valid_foundation):
    from scripts.verify_haichau_foundation import verify_foundation

    root, manifest = valid_foundation
    manifest["runtime"]["image_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="runtime digest"):
        verify_foundation(root, manifest)
