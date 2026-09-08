import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest
import yaml

from traffic_rl.research.artifacts import sha256_file


BASE_DIGEST = "sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32"


def _network():
    intersections, roads = [], []
    signal_index = 0
    for branch in range(26):
        signal_count = 3 if branch == 25 else 2
        nodes = ["west-%d" % branch]
        for _ in range(signal_count):
            nodes.append("signal-%02d" % signal_index)
            signal_index += 1
        nodes.append("east-%d" % branch)
        route = ["road-%d-%d" % (branch, index) for index in range(len(nodes) - 1)]
        intersections.append({"id": nodes[0], "virtual": True, "roads": [route[0]]})
        for index, node in enumerate(nodes[1:-1]):
            intersections.append({
                "id": node, "virtual": False, "roads": [route[index], route[index + 1]],
                "roadLinks": [{"startRoad": route[index], "endRoad": route[index + 1],
                               "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]}],
                "trafficLight": {"lightphases": [
                    {"time": 40, "availableRoadLinks": [0]},
                    {"time": 5, "availableRoadLinks": [0]},
                    {"time": 40, "availableRoadLinks": [0]},
                    {"time": 5, "availableRoadLinks": []},
                ]},
            })
        intersections.append({"id": nodes[-1], "virtual": True, "roads": [route[-1]]})
        roads.extend({"id": road_id, "startIntersection": nodes[index],
                      "endIntersection": nodes[index + 1], "lanes": [{}]}
                     for index, road_id in enumerate(route))
    return {"intersections": intersections, "roads": roads}


def _write_profile_source(root):
    path = root / "profiles.csv"
    fields = ["hour_start", "camera", "movement", "car_veh_per_h",
              "motorcycle_veh_per_h", "truck_veh_per_h", "bus_veh_per_h"]
    counts = {"07:00": 70, "08:00": 140, "09:00": 100,
              "12:00": 100, "13:00": 80, "14:00": 90,
              "16:00": 80, "17:00": 120, "18:00": 150}
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for hour, count in sorted(counts.items()):
            writer.writerow({"hour_start": hour, "camera": "one", "movement": "through",
                             "car_veh_per_h": count, "motorcycle_veh_per_h": 0,
                             "truck_veh_per_h": 0, "bus_veh_per_h": 0})
    return path, counts


@pytest.fixture
def valid_foundation(tmp_path):
    from scripts.prepare_haichau_network_v2 import prepare
    from traffic_rl.network.haichau_dataset import build_phase_contract
    from traffic_rl.network.roadnet import RoadNet

    dataset = tmp_path / "datasets" / "fixture"
    docker_dir = tmp_path / "docker" / "cityflow-research"
    dataset.mkdir(parents=True)
    docker_dir.mkdir(parents=True)
    roadnet_path = dataset / "roadnet.json"
    roadnet_path.write_text(json.dumps(_network()))
    source_dir = dataset / "source"
    source_dir.mkdir()
    source_records = []
    for role, name, payload in (
        ("clipped_osm_pbf", "clipped.osm.pbf", b"fixture-pbf"),
        ("clipped_osm_xml", "clipped.osm", b"fixture-osm"),
        ("sumo_network", "network.net.xml", b"fixture-sumo"),
        ("source_cityflow_roadnet", "source-roadnet.json", roadnet_path.read_bytes()),
    ):
        source_path = source_dir / name
        source_path.write_bytes(payload)
        source_records.append({
            "role": role,
            "path": "datasets/fixture/source/%s" % name,
            "path_at_conversion": "historical/%s" % name,
            "sha256": sha256_file(source_path),
            "availability": "tracked",
        })
    phase_contract_path = dataset / "phase-contract.json"
    phase_contract_path.write_text(json.dumps(build_phase_contract(
        RoadNet.load(str(roadnet_path)), "fixture", sha256_file(roadnet_path), 20
    ), sort_keys=True, separators=(",", ":")) + "\n")
    profile_path, counts = _write_profile_source(tmp_path)
    dockerfile = docker_dir / "Dockerfile"
    dockerfile.write_text("FROM cityflowproject/cityflow@%s\n" % BASE_DIGEST)
    provenance = {
        "schema_version": 2, "dataset_id": "fixture",
        "data_source_label": "osm_topology_synthetic_demand",
        "bbox_wgs84": [1, 2, 3, 4], "license": "fixture ODbL",
        "osm_source": {"extract_provider": "fixture", "url": "https://example.test/input.osm.pbf",
                       "retrieval_date": "unknown_not_recorded"},
        "source_artifacts": source_records,
        "conversion": {"commands": ["fixture"], "osmium_version": "unknown_not_recorded",
                       "netconvert_version": "unknown_not_recorded",
                       "converter_image_digest": "unknown_not_recorded",
                       "configuration_definition_commit": "unknown_not_recorded"},
        "repairs": [], "source_roadnet_sha256": sha256_file(roadnet_path),
        "roadnet_expected_sha256": sha256_file(roadnet_path),
        "expected_controlled_signals": 53, "expected_min_green_phases_per_agent": 2,
        "demand_provenance": {"temporal_profile_path": "profiles.csv",
                              "temporal_profile_sha256": sha256_file(profile_path),
                              "temporal_aggregation": "fixture sum",
                              "vehicle_mix_basis": "fixture", "applied_motorcycle_ratio": 0.75,
                              "vehicle_mix_scope": "synthetic fixture"},
        "limitations": {
            "historical_conversion_reproducibility": "unknown_not_recorded",
            "phase_plan_observation": "unknown_not_recorded",
            "study_scope": "synthetic fixture",
        },
    }
    provenance_path = dataset / "provenance.json"
    provenance_path.write_text(json.dumps(provenance))
    scenario_hours = {
        "normal": ["12:00", "13:00", "14:00"],
        "am_peak": ["07:00", "08:00", "09:00"],
        "pm_peak": ["16:00", "17:00", "18:00"],
    }
    config = {
        "schema_version": 2, "dataset_id": "fixture",
        "roadnet": "datasets/fixture/roadnet.json",
        "phase_contract": {"path": "datasets/fixture/phase-contract.json",
                           "sha256": sha256_file(phase_contract_path)},
        "provenance": {"path": "datasets/fixture/provenance.json",
                       "sha256": sha256_file(provenance_path)},
        "demand_label": "synthetic_osm_haichau_constrained_by_danang_profiles",
        "route_count": 2, "min_controlled_signals_per_route": 2,
        "horizon_seconds": 60, "motorcycle_ratio": 0.75,
        "reference_interval_seconds": 10.0,
        "route_family_split": {"train": 0.5, "validation": 0.25, "test": 0.25},
        "temporal_profile_source": {"path": "profiles.csv", "sha256": sha256_file(profile_path),
                                    "aggregation_fields": ["car_veh_per_h", "motorcycle_veh_per_h",
                                                           "truck_veh_per_h", "bus_veh_per_h"],
                                    "derivation": "fixture sum"},
        "regimes": {scenario: {"profile_bins": [
            {"start": index * 20, "end": (index + 1) * 20, "source_hour": hour,
             "source_vehicle_count": counts[hour]}
            for index, hour in enumerate(hours)]}
            for scenario, hours in scenario_hours.items()},
        "splits": {
            "train": {"demand_seeds": [11, 12, 13], "sim_seeds": [111, 112, 113]},
            "validation": {"demand_seeds": [31, 32], "sim_seeds": [131, 132]},
            "test": {"demand_seeds": [101, 102, 103, 104, 105],
                     "sim_seeds": [201, 202, 203, 204, 205]},
        },
        "simulation": {"action_interval": 10, "yellow_time": 3, "min_green": 20,
                       "maximum_red": 180},
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
    }
    config_path = tmp_path / "fixture.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    manifest = prepare(config_path, tmp_path)
    # Preserve old keys only so every new semantic test demonstrably fails against
    # the pre-review verifier instead of failing setup on the evolved runtime shape.
    manifest["runtime"]["image"] = "cityflowproject/cityflow"
    manifest["runtime"]["image_digest"] = BASE_DIGEST
    return tmp_path, manifest


def _verify(root, manifest):
    from scripts.verify_haichau_foundation import verify_foundation
    return verify_foundation(root, manifest)


def _rebind_config_artifact(root, manifest, config_key, manifest_record):
    config_path = root / manifest["generator_config_path"]
    config = yaml.safe_load(config_path.read_text())
    config[config_key] = dict(manifest_record)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    manifest["generator_config_sha256"] = sha256_file(config_path)


def test_foundation_verifier_accepts_semantically_bound_family(valid_foundation):
    root, manifest = valid_foundation
    report = _verify(root, manifest)
    assert report["controlled_signals"] == 53
    assert report["cases"] == 30
    assert report["selectable_green_phases"] == 106


def test_foundation_verifier_rejects_short_phase_promoted_to_action(valid_foundation):
    root, manifest = valid_foundation
    record = manifest["phase_contract"]
    path = root / record["path"]
    contract = json.loads(path.read_text())
    agent = contract["agents"][sorted(contract["agents"])[0]]
    agent["selectable_phases"].append(agent["transition_phases"][0])
    path.write_text(json.dumps(contract, sort_keys=True, separators=(",", ":")) + "\n")
    record["sha256"] = sha256_file(path)
    _rebind_config_artifact(root, manifest, "phase_contract", record)
    with pytest.raises(ValueError, match="phase contract"):
        _verify(root, manifest)


def test_foundation_verifier_rejects_missing_directed_transition(valid_foundation):
    root, manifest = valid_foundation
    record = manifest["phase_contract"]
    path = root / record["path"]
    contract = json.loads(path.read_text())
    agent = contract["agents"][sorted(contract["agents"])[0]]
    source = str(agent["selectable_phases"][0])
    target = str(agent["selectable_phases"][1])
    del agent["transitions"][source][target]
    path.write_text(json.dumps(contract, sort_keys=True, separators=(",", ":")) + "\n")
    record["sha256"] = sha256_file(path)
    _rebind_config_artifact(root, manifest, "phase_contract", record)
    with pytest.raises(ValueError, match="phase contract"):
        _verify(root, manifest)


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda m: m["preprocessing"].update(count_norm=999), "preprocessing"),
        (lambda m: m["simulation"].update(min_green=999), "simulation"),
        (lambda m: m.update(data_source_label="observed"), "data source label"),
        (lambda m: m["cases"][0].update(scale=999), "case semantic"),
        (lambda m: m["cases"][0].update(route_signal_histogram={"3": 2}), "case semantic"),
        (lambda m: m["cases"][0].update(demand_seed=999), "case semantic"),
        (lambda m: m["cases"][0]["temporal_profile"][0].update(interval_seconds=999), "case semantic"),
        (lambda m: m["cases"][0]["scheduled_departures_by_bin"][0].update(scheduled=999), "case semantic"),
        (lambda m: m["cases"][0].update(case_id="wrong"), "case registry"),
        (lambda m: m["runtime"].update(base_image="attacker/image:latest"), "runtime identity"),
        (lambda m: m["network"].update(controlled_signals=52), "controlled signal count"),
    ],
)
def test_foundation_verifier_rejects_manifest_semantic_drift(valid_foundation, mutation, message):
    root, manifest = valid_foundation
    mutation(manifest)
    with pytest.raises(ValueError, match=message):
        _verify(root, manifest)


def test_foundation_verifier_rejects_normal_case_rewired_to_peak(valid_foundation):
    root, manifest = valid_foundation
    normal = next(case for case in manifest["cases"] if case["scenario"] == "normal")
    peak = next(case for case in manifest["cases"] if case["split"] == normal["split"]
                and case["demand_seed"] == normal["demand_seed"] and case["scenario"] == "am_peak")
    normal["flow_path"], normal["flow_sha256"] = peak["flow_path"], peak["flow_sha256"]
    with pytest.raises(ValueError, match="flow semantics"):
        _verify(root, manifest)


def test_foundation_verifier_parses_flow_and_rejects_cross_split_route(valid_foundation):
    root, manifest = valid_foundation
    train = next(case for case in manifest["cases"] if case["split"] == "train")
    test = next(case for case in manifest["cases"] if case["split"] == "test")
    train_flow = json.loads((root / train["flow_path"]).read_text())
    test_path = root / test["flow_path"]
    test_flow = json.loads(test_path.read_text())
    test_flow[0]["route"] = train_flow[0]["route"]
    test_path.write_text(json.dumps(test_flow, sort_keys=True, separators=(",", ":")) + "\n")
    test["flow_sha256"] = sha256_file(test_path)
    with pytest.raises(ValueError, match="route family overlap|flow semantics"):
        _verify(root, manifest)


def test_foundation_verifier_parses_flow_and_rejects_vehicle_mix(valid_foundation):
    root, manifest = valid_foundation
    case = manifest["cases"][0]
    flow_path = root / case["flow_path"]
    flow = json.loads(flow_path.read_text())
    flow[0]["vehicle"]["length"] = 99
    flow_path.write_text(json.dumps(flow, sort_keys=True, separators=(",", ":")) + "\n")
    case["flow_sha256"] = sha256_file(flow_path)
    with pytest.raises(ValueError, match="vehicle|flow semantics"):
        _verify(root, manifest)


def test_foundation_verifier_rejects_missing_provenance_field(valid_foundation):
    root, manifest = valid_foundation
    provenance_record = manifest["network"]["provenance"]
    provenance_path = root / provenance_record["path"]
    provenance = json.loads(provenance_path.read_text())
    del provenance["conversion"]
    provenance_path.write_text(json.dumps(provenance))
    provenance_record["sha256"] = sha256_file(provenance_path)
    with pytest.raises(ValueError, match="provenance"):
        _verify(root, manifest)


def _empty_osm_source(provenance):
    provenance["osm_source"] = {}


def _empty_conversion_commands(provenance):
    provenance["conversion"]["commands"] = []


def _fabricate_converter_digest(provenance):
    provenance["conversion"]["converter_image_digest"] = "fabricated"


def _fabricate_definition_commit(provenance):
    provenance["conversion"]["configuration_definition_commit"] = "0" * 40


def _fabricate_source_artifact_hash(provenance):
    provenance["source_artifacts"][0]["sha256"] = "0" * 64


def _remove_source_roadnet_role(provenance):
    provenance["source_artifacts"] = [
        record for record in provenance["source_artifacts"]
        if record["role"] != "source_cityflow_roadnet"
    ]


@pytest.mark.parametrize("mutation", [
    _empty_osm_source,
    _empty_conversion_commands,
    _fabricate_converter_digest,
    _fabricate_definition_commit,
    _fabricate_source_artifact_hash,
    _remove_source_roadnet_role,
])
def test_foundation_verifier_rejects_fabricated_provenance_even_when_rebound(
        valid_foundation, mutation):
    root, manifest = valid_foundation
    record = manifest["network"]["provenance"]
    path = root / record["path"]
    provenance = json.loads(path.read_text())
    mutation(provenance)
    path.write_text(json.dumps(provenance, sort_keys=True))
    record["sha256"] = sha256_file(path)
    _rebind_config_artifact(root, manifest, "provenance", record)
    with pytest.raises(ValueError, match="provenance|artifact|hash mismatch"):
        _verify(root, manifest)


def test_canonical_provenance_labels_signal_repair_as_synthetic_assumption():
    root = Path(__file__).resolve().parents[2]
    provenance = json.loads(
        (root / "datasets/haichau_network_v2/provenance.json").read_text()
    )
    repair = provenance["repairs"][0]
    assert repair["intersection_id"] == "5896811072"
    assert repair["modeling_status"] == "synthetic_engineering_normalization"
    assert repair["source_evidence"] == "unknown_not_recorded"
    assert provenance["limitations"]["phase_plan_observation"] == "unknown_not_recorded"


def test_foundation_verifier_rejects_profile_count_not_supported_by_source(valid_foundation):
    root, manifest = valid_foundation
    config_path = root / manifest["generator_config_path"]
    config = yaml.safe_load(config_path.read_text())
    config["regimes"]["normal"]["profile_bins"][0]["source_vehicle_count"] += 1
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    manifest["generator_config_sha256"] = sha256_file(config_path)
    with pytest.raises(ValueError, match="temporal profile source count"):
        _verify(root, manifest)


def test_foundation_verifier_rejects_dockerfile_base_even_when_rehashed(valid_foundation):
    root, manifest = valid_foundation
    dockerfile = root / manifest["runtime"]["dockerfile"]["path"]
    dockerfile.write_text("FROM attacker/image:latest\n")
    manifest["runtime"]["dockerfile"]["sha256"] = sha256_file(dockerfile)
    with pytest.raises(ValueError, match="runtime identity Dockerfile"):
        _verify(root, manifest)


def test_runtime_attestation_binds_derived_image_and_build_inputs(valid_foundation):
    from scripts.verify_haichau_foundation import verify_runtime_attestation

    _, manifest = valid_foundation
    environment = {
        "HAICHAU_DERIVED_IMAGE_ID": "sha256:" + "a" * 64,
        "HAICHAU_BASE_IMAGE_DIGEST": BASE_DIGEST,
        "HAICHAU_DOCKERFILE_SHA256": manifest["runtime"]["dockerfile"]["sha256"],
    }
    result = verify_runtime_attestation(manifest, environment)
    assert result["derived_image_id"] == environment["HAICHAU_DERIVED_IMAGE_ID"]


def test_runtime_attestation_rejects_unbound_derived_image(valid_foundation):
    from scripts.verify_haichau_foundation import verify_runtime_attestation

    _, manifest = valid_foundation
    environment = {
        "HAICHAU_DERIVED_IMAGE_ID": "mutable-tag",
        "HAICHAU_BASE_IMAGE_DIGEST": BASE_DIGEST,
        "HAICHAU_DOCKERFILE_SHA256": manifest["runtime"]["dockerfile"]["sha256"],
    }
    with pytest.raises(ValueError, match="derived image identity"):
        verify_runtime_attestation(manifest, environment)


def test_committed_clean_checkout_foundation_evidence():
    root = Path(__file__).resolve().parents[2]
    evidence_path = root / "results/haichau_network_v2/verification/foundation.json"
    evidence = json.loads(evidence_path.read_text())

    assert evidence["schema_version"] == 1
    assert evidence["dataset_id"] == "haichau_network_v2"
    assert re.match(r"^[0-9a-f]{40}$", evidence["verified_commit"])
    subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", evidence["verified_commit"] + "^{commit}"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor",
         evidence["verified_commit"], "HEAD"],
        check=True,
    )
    assert evidence["checkout"]["status_before"] == "clean"
    assert evidence["checkout"]["ignored_source_present"] is False
    assert evidence["wall_time_seconds"] > 0

    commands = {record["command"]: record for record in evidence["commands"]}
    assert set(commands) == {
        "make test",
        "PYTHONPATH=src python3 scripts/verify_haichau_foundation.py",
        "make haichau-smoke",
    }
    assert all(record["exit_code"] == 0 for record in commands.values())
    assert "165 passed, 1 deselected" in commands["make test"]["output_summary"]
    assert commands[
        "PYTHONPATH=src python3 scripts/verify_haichau_foundation.py"
    ]["output"]["status"] == "verified"
    assert commands["make haichau-smoke"]["output"]["status"] == "engine-smoke-passed"

    runtime = evidence["runtime_identity"]
    assert re.match(r"^sha256:[0-9a-f]{64}$", runtime["derived_image_id"])
    assert runtime["base_image_digest"] == BASE_DIGEST
    assert runtime["platform"] == "linux/amd64"
    smoke_output = commands["make haichau-smoke"]["output"]
    for field in ("derived_image_id", "base_image_digest", "dockerfile_sha256", "platform"):
        assert runtime[field] == smoke_output[field]

    expected_paths = {
        "configs/haichau_network_v2.yaml",
        "datasets/haichau_network_v2/phase-contract.json",
        "datasets/haichau_network_v2/provenance.json",
        "datasets/haichau_network_v2/roadnet.json",
        "datasets/haichau_network_v2/source/danang_haichau.net.xml",
        "datasets/haichau_network_v2/source/danang_haichau.osm",
        "datasets/haichau_network_v2/source/danang_haichau.osm.pbf",
        "datasets/haichau_network_v2/source/roadnet_haichau_rush.json",
        "docker/cityflow-research/Dockerfile",
        "results/haichau_network_v2/experiment-manifest.json",
    }
    artifacts = evidence["verified_artifacts"]
    assert set(artifacts) == expected_paths
    for path, expected_hash in artifacts.items():
        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", "%s:%s" % (evidence["verified_commit"], path)]
        )
        assert hashlib.sha256(blob).hexdigest() == expected_hash
