#!/usr/bin/env python3
"""Fail-closed verification and CityFlow smoke for the Hai Chau v2 foundation."""

import argparse
from collections import Counter, defaultdict
import copy
import csv
import json
import os
from pathlib import Path
import re
import tempfile

import yaml

from traffic_rl.network.haichau_dataset import (
    VEHICLE_TEMPLATES,
    audit_network,
    build_flow_cases,
    count_controlled_signals,
    route_is_valid,
    validate_phase_contract,
)
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import (
    canonical_sha256,
    validate_disjoint_splits,
    verify_artifact,
)


EXPECTED_CONTROLLED_SIGNALS = 53
EXPECTED_CASES = 30
EXPECTED_SCENARIOS = {"normal", "am_peak", "pm_peak"}
EXPECTED_BASE_IMAGE = "cityflowproject/cityflow"
EXPECTED_IMAGE_DIGEST = "sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32"
EXPECTED_DERIVED_TAG = "traffic-rl-cityflow-research:v2"
EXPECTED_PLATFORM = "linux/amd64"
EXPECTED_DEMAND_LABEL = "synthetic_osm_haichau_constrained_by_danang_profiles"
EXPECTED_CONFIGURATION_DEFINITION_COMMIT = "9f4deae7d0b2390593c52a18d78f7894f7579251"
UNKNOWN = "unknown_not_recorded"
EXPECTED_HAICHAU_OSM_SOURCE = {
    "extract_provider": "Geofabrik",
    "retrieval_date": UNKNOWN,
    "url": "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf",
}
EXPECTED_HAICHAU_COMMANDS = [
    "osmium extract --overwrite -b 108.1888,16.0213,108.236,16.1037 data/osm/vietnam-latest.osm.pbf -o data/osm/danang_haichau.osm.pbf",
    "osmium cat --overwrite data/osm/danang_haichau.osm.pbf -o data/osm/danang_haichau.osm",
    "netconvert --osm-files data/osm/danang_haichau.osm --output-file data/osm/danang_haichau.net.xml --keep-edges.by-vclass passenger --remove-edges.isolated true --geometry.remove true --roundabouts.guess true --ramps.guess true --junctions.join true --tls.guess-signals true --tls.join true --tls.discard-simple true --tls.default-type actuated --no-turnarounds true --remove-edges.by-type highway.residential --keep-edges.components 1",
    "python3 /home/cityflow/tools/converter/converter.py --sumonet data/osm/danang_haichau.net.xml --cityflownet data/danang/roadnet_haichau.json",
]
EXPECTED_HAICHAU_SOURCE_HASHES = {
    "clipped_osm_pbf": "cc091baf523d0fa7a8be0b32a62d5e4bccc4d6452e51b38c1b1a88ffc518a331",
    "clipped_osm_xml": "0e71b672e12fb9c6601750be554abd560737a62e8557df3c5cf7f116403d26f1",
    "sumo_network": "0b4e0750134697de1a9d5c7d19fb71bc6cbade58506a7fd816410a487ee3faba",
    "source_cityflow_roadnet": "cddce1090b214fd8250303a28b51e4a460f4af04dde87cafad9dabd58f2ac040",
}
EXPECTED_HAICHAU_PROVENANCE_SEMANTIC_SHA256 = (
    "de9cc6003a4b39ca478cdae13c8ebb68937e27adcd4172df515cc724311b28d1"
)


def _require_exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("provenance %s schema mismatch" % label)


def _is_sha256(value):
    return isinstance(value, str) and re.match(r"^[0-9a-f]{64}$", value) is not None


def _verify_canonical_provenance_anchor(provenance, dataset_id):
    """Pin every canonical provenance assertion outside its mutable hash graph."""
    if (dataset_id == "haichau_network_v2"
            and canonical_sha256(provenance)
            != EXPECTED_HAICHAU_PROVENANCE_SEMANTIC_SHA256):
        raise ValueError("canonical provenance semantic hash mismatch")


def _load_verified_config(root, manifest):
    config_path = verify_artifact(
        root,
        {
            "path": manifest["generator_config_path"],
            "sha256": manifest["generator_config_sha256"],
        },
    )
    config = yaml.safe_load(config_path.read_text())
    if config.get("schema_version") != 2:
        raise ValueError("generator config schema_version must be 2")
    if config.get("dataset_id") != manifest.get("dataset_id"):
        raise ValueError("generator config dataset_id mismatch")
    if manifest.get("data_source_label") != config.get("demand_label"):
        raise ValueError("data source label differs from generator config")
    if config.get("demand_label") != EXPECTED_DEMAND_LABEL:
        raise ValueError("data source label must remain explicitly synthetic")
    if manifest.get("simulation") != config.get("simulation"):
        raise ValueError("simulation settings differ from generator config")
    if manifest.get("preprocessing") != config.get("preprocessing"):
        raise ValueError("preprocessing settings differ from generator config")
    return config


def _verify_provenance(root, record, network, config, network_path):
    if record != config.get("provenance"):
        raise ValueError("provenance record differs from generator config")
    path = verify_artifact(root, record)
    provenance = json.loads(path.read_text())
    _verify_canonical_provenance_anchor(provenance, config["dataset_id"])
    required = {
        "schema_version", "dataset_id", "data_source_label", "bbox_wgs84",
        "license", "osm_source", "source_artifacts", "conversion", "repairs",
        "source_roadnet_sha256", "roadnet_expected_sha256",
        "expected_controlled_signals", "expected_min_green_phases_per_agent",
        "demand_provenance", "limitations",
    }
    _require_exact_keys(provenance, required, "root")
    if provenance["schema_version"] != 2:
        raise ValueError("provenance schema_version must be 2")
    if (provenance["dataset_id"] != config["dataset_id"]
            or provenance["data_source_label"] != "osm_topology_synthetic_demand"):
        raise ValueError("provenance dataset_id mismatch")
    bbox = provenance["bbox_wgs84"]
    if (not isinstance(bbox, list) or len(bbox) != 4
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in bbox)
            or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]):
        raise ValueError("provenance bounding box is invalid")
    if not isinstance(provenance["license"], str) or not provenance["license"].strip():
        raise ValueError("provenance license is invalid")

    osm = provenance["osm_source"]
    _require_exact_keys(osm, {"extract_provider", "url", "retrieval_date"}, "osm_source")
    if (not isinstance(osm["extract_provider"], str) or not osm["extract_provider"].strip()
            or not isinstance(osm["url"], str) or not osm["url"].startswith("https://")
            or osm["retrieval_date"] != UNKNOWN):
        raise ValueError("provenance OSM source is invalid")

    conversion = provenance["conversion"]
    conversion_keys = {
        "commands", "configuration_definition_commit", "converter_image_digest",
        "netconvert_version", "osmium_version",
    }
    _require_exact_keys(conversion, conversion_keys, "conversion")
    commands = conversion["commands"]
    if (not isinstance(commands, list) or not commands
            or any(not isinstance(command, str) or not command.strip() for command in commands)
            or len(commands) != len(set(commands))):
        raise ValueError("provenance conversion commands must be non-empty and unique")
    definition_commit = conversion["configuration_definition_commit"]
    expected_commit = (EXPECTED_CONFIGURATION_DEFINITION_COMMIT
                       if config["dataset_id"] == "haichau_network_v2" else UNKNOWN)
    if definition_commit != expected_commit:
        raise ValueError("provenance configuration commit is invalid")
    for field in ("osmium_version", "netconvert_version", "converter_image_digest"):
        if conversion[field] != UNKNOWN:
            raise ValueError("provenance unknown conversion identity must use %s" % UNKNOWN)

    artifact_keys = {"role", "path", "path_at_conversion", "sha256", "availability"}
    required_roles = {
        "clipped_osm_pbf", "clipped_osm_xml", "sumo_network",
        "source_cityflow_roadnet",
    }
    artifacts = provenance["source_artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(required_roles):
        raise ValueError("provenance source artifact registry is incomplete")
    by_role = {}
    for artifact in artifacts:
        _require_exact_keys(artifact, artifact_keys, "source artifact")
        if (artifact["role"] in by_role or artifact["role"] not in required_roles
                or artifact["availability"] != "tracked"
                or not artifact["path_at_conversion"]):
            raise ValueError("provenance source artifact role is invalid")
        if not _is_sha256(artifact["sha256"]):
            raise ValueError("provenance source artifact hash is invalid")
        verify_artifact(root, artifact)
        by_role[artifact["role"]] = artifact
    if set(by_role) != required_roles:
        raise ValueError("provenance source artifact roles are incomplete")
    if provenance["source_roadnet_sha256"] != by_role["source_cityflow_roadnet"]["sha256"]:
        raise ValueError("provenance source roadnet hash mismatch")
    if config["dataset_id"] == "haichau_network_v2":
        if osm != EXPECTED_HAICHAU_OSM_SOURCE:
            raise ValueError("provenance canonical OSM source mismatch")
        if commands != EXPECTED_HAICHAU_COMMANDS:
            raise ValueError("provenance canonical conversion commands mismatch")
        if {role: record["sha256"] for role, record in by_role.items()} != EXPECTED_HAICHAU_SOURCE_HASHES:
            raise ValueError("provenance canonical source hashes mismatch")

    if provenance["roadnet_expected_sha256"] != network["sha256"]:
        raise ValueError("provenance roadnet hash mismatch")
    if provenance["expected_controlled_signals"] != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("provenance controlled signal count mismatch")
    if provenance["expected_min_green_phases_per_agent"] != 2:
        raise ValueError("provenance green phase minimum mismatch")
    demand = provenance["demand_provenance"]
    _require_exact_keys(demand, {
        "temporal_profile_path", "temporal_profile_sha256", "temporal_aggregation",
        "vehicle_mix_basis", "applied_motorcycle_ratio", "vehicle_mix_scope",
    }, "demand")
    source = config.get("temporal_profile_source", {})
    if (demand.get("temporal_profile_path") != source.get("path")
            or demand.get("temporal_profile_sha256") != source.get("sha256")
            or demand.get("applied_motorcycle_ratio") != config.get("motorcycle_ratio")
            or any(not demand[field] for field in (
                "temporal_aggregation", "vehicle_mix_basis", "vehicle_mix_scope"
            ))):
        raise ValueError("provenance demand inputs differ from generator config")

    limitations = provenance["limitations"]
    _require_exact_keys(limitations, {
        "historical_conversion_reproducibility", "phase_plan_source", "study_scope",
    }, "limitations")
    if (limitations["historical_conversion_reproducibility"] != UNKNOWN
            or not isinstance(limitations["phase_plan_source"], str)
            or not limitations["phase_plan_source"].strip()
            or not limitations["study_scope"]):
        raise ValueError("provenance limitations are invalid")

    source_path = verify_artifact(root, by_role["source_cityflow_roadnet"])
    source_roadnet = json.loads(source_path.read_text())
    canonical_roadnet = json.loads(Path(network_path).read_text())
    transformed = copy.deepcopy(source_roadnet)
    source_by_id = {item["id"]: item for item in transformed["intersections"]}
    repairs = provenance["repairs"]
    if provenance["source_roadnet_sha256"] == network["sha256"] and repairs:
        raise ValueError("provenance repairs must be empty when source equals canonical")
    if provenance["source_roadnet_sha256"] != network["sha256"] and not repairs:
        raise ValueError("provenance must document roadnet repairs")
    for repair in repairs:
        repair_keys = {
            "type", "intersection_id", "before", "after", "rationale",
            "modeling_status", "source_evidence",
        }
        _require_exact_keys(repair, repair_keys, "repair")
        if (repair["type"] != "split_single_action_by_road_link"
                or repair["modeling_status"] != "synthetic_engineering_normalization"
                or repair["source_evidence"] != UNKNOWN
                or not repair["rationale"]):
            raise ValueError("provenance repair semantics are invalid")
        intersection = source_by_id.get(repair["intersection_id"])
        if (intersection is None
                or intersection["trafficLight"]["lightphases"] != repair["before"]):
            raise ValueError("provenance repair source does not match tracked artifact")
        intersection["trafficLight"]["lightphases"] = repair["after"]
    if transformed != canonical_roadnet:
        raise ValueError("provenance repairs do not exactly produce canonical roadnet")
    return provenance


def _verify_phase_contract(root, manifest, config, network_path, provenance):
    record = manifest.get("phase_contract", {})
    if record != config.get("phase_contract"):
        raise ValueError("phase contract record differs from generator config")
    path = verify_artifact(root, record)
    contract = json.loads(path.read_text())
    roadnet = RoadNet.load(str(network_path))
    sumo_records = [
        item for item in provenance["source_artifacts"]
        if item["role"] == "sumo_network"
    ]
    if len(sumo_records) != 1:
        raise ValueError("phase contract requires exactly one SUMO source")
    sumo_artifact = sumo_records[0]
    sumo_path = verify_artifact(root, sumo_artifact)
    sumo_record = {
        "path": sumo_artifact["path"],
        "sha256": sumo_artifact["sha256"],
    }
    return validate_phase_contract(
        roadnet,
        contract,
        config["dataset_id"],
        manifest["network"]["sha256"],
        int(config["simulation"]["min_green"]),
        sumo_path,
        sumo_record,
        provenance["repairs"],
    )


def _verify_temporal_source(root, config):
    source = config.get("temporal_profile_source", {})
    path = verify_artifact(root, source)
    fields = source.get("aggregation_fields")
    if not fields or not source.get("derivation"):
        raise ValueError("temporal profile source contract is incomplete")
    by_hour = Counter()
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                by_hour[row["hour_start"]] += sum(int(row[field]) for field in fields)
            except (KeyError, TypeError, ValueError):
                raise ValueError("temporal profile source schema mismatch")
    for scenario in EXPECTED_SCENARIOS:
        for profile_bin in config["regimes"][scenario]["profile_bins"]:
            if by_hour[profile_bin["source_hour"]] != profile_bin["source_vehicle_count"]:
                raise ValueError("temporal profile source count mismatch")


def _verify_network(root, manifest, config):
    network = manifest.get("network", {})
    if network.get("controlled_signals") != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("controlled signal count must be exactly 53")
    network_path = verify_artifact(root, network)
    if network.get("path") != config.get("roadnet"):
        raise ValueError("network path differs from generator config")

    if not network.get("provenance"):
        raise ValueError("network provenance record is required")
    provenance = _verify_provenance(
        root, network["provenance"], network, config, network_path
    )
    phase_contract = _verify_phase_contract(
        root, manifest, config, network_path, provenance
    )

    actual = audit_network(
        network_path,
        phase_contract,
        int(config["simulation"]["min_green"]),
        root / phase_contract["source_sumo_network"]["path"],
        phase_contract["source_sumo_network"],
        provenance["repairs"],
    )
    if actual["controlled_signals"] != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("controlled signal count audit mismatch")
    for field in (
        "roads",
        "lanes",
        "intersections",
        "controlled_signals",
        "selectable_green_phases",
        "transition_phases",
        "agent_selectable_phase_counts",
        "agent_ids",
        "directed_signal_edges",
        "weak_components",
        "phase_errors",
    ):
        if network.get(field) != actual[field]:
            raise ValueError("network audit field mismatch: %s" % field)
    if actual["phase_errors"]:
        raise ValueError("network phase audit failed")
    if min(actual["agent_selectable_phase_counts"].values()) < 2:
        raise ValueError("controlled signal has fewer than two selectable green phases")
    return network_path, actual


def _verify_runtime(root, manifest):
    runtime = manifest.get("runtime", {})
    expected = {
        "base_image": EXPECTED_BASE_IMAGE,
        "base_image_digest": EXPECTED_IMAGE_DIGEST,
        "derived_image_tag": EXPECTED_DERIVED_TAG,
        "platform": EXPECTED_PLATFORM,
    }
    if any(runtime.get(field) != value for field, value in expected.items()):
        raise ValueError("runtime identity mismatch")
    dockerfile = verify_artifact(root, runtime.get("dockerfile", {}))
    first_line = dockerfile.read_text().splitlines()[0]
    if first_line != "FROM %s@%s" % (EXPECTED_BASE_IMAGE, EXPECTED_IMAGE_DIGEST):
        raise ValueError("runtime identity Dockerfile base mismatch")


def verify_runtime_attestation(manifest, environment):
    """Validate host-inspected identity passed into the running smoke container."""
    runtime = manifest["runtime"]
    image_id = environment.get("HAICHAU_DERIVED_IMAGE_ID", "")
    if not re.match(r"^sha256:[0-9a-f]{64}$", image_id):
        raise ValueError("derived image identity is missing or malformed")
    if environment.get("HAICHAU_BASE_IMAGE_DIGEST") != runtime["base_image_digest"]:
        raise ValueError("derived image identity has wrong base digest label")
    if environment.get("HAICHAU_DOCKERFILE_SHA256") != runtime["dockerfile"]["sha256"]:
        raise ValueError("derived image identity has wrong Dockerfile hash label")
    if environment.get("HAICHAU_IMAGE_PLATFORM", runtime["platform"]) != runtime["platform"]:
        raise ValueError("derived image identity has wrong platform")
    return {
        "derived_image_id": image_id,
        "base_image_digest": runtime["base_image_digest"],
        "dockerfile_sha256": runtime["dockerfile"]["sha256"],
        "platform": runtime["platform"],
    }


def _scheduled_departures(row):
    return 1 + int((row["endTime"] - row["startTime"]) // row["interval"])


def _verify_parsed_flow(roadnet, case, flow, config, catalog_by_hash):
    if not isinstance(flow, list) or not flow:
        raise ValueError("flow semantics require a non-empty list")
    split_hashes = {route_hash for route_hash, family in catalog_by_hash.items()
                    if family["split"] == case["split"]}
    parsed_hashes = set()
    for row in flow:
        if set(row) != {"vehicle", "route", "interval", "startTime", "endTime"}:
            raise ValueError("flow semantics contain an invalid CityFlow row")
        if not route_is_valid(roadnet, row["route"], config["min_controlled_signals_per_route"]):
            raise ValueError("flow semantics contain an invalid route")
        route_hash = canonical_sha256(row["route"])
        parsed_hashes.add(route_hash)
        if route_hash not in split_hashes:
            raise ValueError("route family overlap or unregistered family in flow")
        if row["vehicle"] not in VEHICLE_TEMPLATES.values():
            raise ValueError("vehicle mix contains an unknown template")
    if parsed_hashes != set(case["route_family_hashes"]):
        raise ValueError("case semantic route family hashes mismatch")


def _verify_route_catalog(root, manifest, roadnet, expected_catalog):
    record = manifest.get("route_families", {})
    path = verify_artifact(root, record)
    catalog = json.loads(path.read_text())
    if catalog != expected_catalog or record.get("count") != len(catalog):
        raise ValueError("route family catalog semantics mismatch")
    counts = Counter(family["split"] for family in catalog)
    if record.get("partition_counts") != {split: counts[split] for split in sorted(counts)}:
        raise ValueError("route family partition counts mismatch")
    seen = {}
    for family in catalog:
        route_hash = canonical_sha256(family["route"])
        if route_hash != family["route_sha256"] or family["route_family_id"] != "rf_" + route_hash:
            raise ValueError("route family identity mismatch")
        if not route_is_valid(roadnet, family["route"], 2):
            raise ValueError("route family contains invalid route")
        if route_hash in seen and seen[route_hash] != family["split"]:
            raise ValueError("route family overlap across splits")
        seen[route_hash] = family["split"]
    return {family["route_sha256"]: family for family in catalog}


def _verify_cases(root, manifest, config, roadnet, expected_cases, catalog_by_hash):
    cases = manifest.get("cases", [])
    if len(cases) != EXPECTED_CASES:
        raise ValueError("expected exactly 30 primary cases")
    expected_by_id = {case["case_id"]: case for case in expected_cases}
    actual_ids = [case.get("case_id") for case in cases]
    if len(set(actual_ids)) != len(actual_ids) or set(actual_ids) != set(expected_by_id):
        raise ValueError("case registry differs from generator config")
    parsed_by_split = defaultdict(set)
    for case in cases:
        expected = expected_by_id[case["case_id"]]
        for field, value in expected.items():
            if field != "flow" and case.get(field) != value:
                raise ValueError("case semantic mismatch: %s" % field)
        flow_path = verify_artifact(
            root, {"path": case["flow_path"], "sha256": case["flow_sha256"]}
        )
        flow = json.loads(flow_path.read_text())
        _verify_parsed_flow(roadnet, case, flow, config, catalog_by_hash)
        parsed_by_split[case["split"]].update(canonical_sha256(row["route"]) for row in flow)
        if flow != expected["flow"]:
            raise ValueError("flow semantics differ from hash-bound generator config")

    split_counts = validate_disjoint_splits(cases)
    if split_counts != {"test": 15, "train": 9, "validation": 6}:
        raise ValueError("split case counts mismatch")
    splits = sorted(parsed_by_split)
    for index, split in enumerate(splits):
        for other in splits[index + 1:]:
            if not parsed_by_split[split].isdisjoint(parsed_by_split[other]):
                raise ValueError("route family overlap across parsed flows")
    return split_counts


def verify_foundation(root, manifest):
    """Verify the complete host-side foundation and return one summary record."""
    root = Path(root).resolve()
    if manifest.get("protocol_version") != 2:
        raise ValueError("protocol_version must be 2")
    _verify_runtime(root, manifest)
    config = _load_verified_config(root, manifest)
    _verify_temporal_source(root, config)
    network_path, network_audit = _verify_network(root, manifest, config)
    roadnet = RoadNet.load(str(network_path))
    expected_cases, expected_catalog = build_flow_cases(
        roadnet, config, include_catalog=True
    )
    catalog_by_hash = _verify_route_catalog(
        root, manifest, roadnet, expected_catalog
    )
    split_counts = _verify_cases(
        root, manifest, config, roadnet, expected_cases, catalog_by_hash
    )
    return {
        "status": "verified",
        "protocol_version": 2,
        "controlled_signals": network_audit["controlled_signals"],
        "selectable_green_phases": network_audit["selectable_green_phases"],
        "transition_phases": network_audit["transition_phases"],
        "cases": len(manifest["cases"]),
        "split_counts": split_counts,
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime_digest": manifest["runtime"]["base_image_digest"],
        "route_families": len(expected_catalog),
    }


def run_engine_smoke(root, manifest, max_steps=60):
    """Run a real 60-second Fixed-Time episode in the pinned CityFlow image."""
    from traffic_rl.agents.fixed_time import FixedTimeController
    from traffic_rl.sim.engine import CityFlowEngine
    from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

    verify_foundation(root, manifest)
    runtime_identity = verify_runtime_attestation(manifest, os.environ)
    root = Path(root).resolve()
    case = next(
        case
        for case in manifest["cases"]
        if case["split"] == "train" and case["scenario"] == "normal"
    )
    runtime_config = {
        "interval": 1.0,
        "seed": int(case["sim_seed"]),
        "dir": str(root) + "/",
        "roadnetFile": manifest["network"]["path"],
        "flowFile": case["flow_path"],
        "rlTrafficLight": True,
        "laneChange": False,
        "saveReplay": False,
    }
    config_handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="haichau-smoke-", delete=False
    )
    try:
        json.dump(runtime_config, config_handle, sort_keys=True)
        config_handle.close()
        roadnet = RoadNet.load(str(root / manifest["network"]["path"]))
        simulation = manifest["simulation"]
        env = MultiAgentTrafficEnv(
            roadnet,
            CityFlowEngine(config_handle.name),
            action_interval=int(simulation["action_interval"]),
            max_steps=int(max_steps),
            yellow_time=int(simulation["yellow_time"]),
            min_green=int(simulation["min_green"]),
            count_norm=float(manifest["preprocessing"]["count_norm"]),
        )
        controller = FixedTimeController(
            num_actions=env.num_actions,
            green_duration=30,
            action_interval=int(simulation["action_interval"]),
        )
        observations = env.reset()
        controller.reset()
        done = False
        info = {}
        while not done:
            actions = controller.act(
                {
                    "observations": observations,
                    "waiting_counts": env.current_waiting_counts(),
                    "action_masks": env.action_masks(),
                }
            )
            observations, _, done, info = env.step(actions)
        result = {
            "status": "engine-smoke-passed",
            "controller": "FixedTime",
            "case_id": case["case_id"],
            "controlled_signals": len(env.agent_ids),
            "steps": info["step"],
            "vehicle_count": info["vehicle_count"],
            "average_travel_time": info["average_travel_time"],
            "queue_integral_vehicle_seconds": info[
                "queue_integral_vehicle_seconds"
            ],
        }
        result.update(runtime_identity)
        return result
    finally:
        path = Path(config_handle.name)
        if path.exists():
            path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="results/haichau_network_v2/experiment-manifest.json",
    )
    parser.add_argument("--engine-smoke", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / args.manifest).read_text())
    report = (
        run_engine_smoke(root, manifest)
        if args.engine_smoke
        else verify_foundation(root, manifest)
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
