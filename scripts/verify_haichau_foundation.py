#!/usr/bin/env python3
"""Fail-closed verification and CityFlow smoke for the Hai Chau v2 foundation."""

import argparse
from collections import Counter, defaultdict
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


def _verify_provenance(root, record, network, config):
    path = verify_artifact(root, record)
    provenance = json.loads(path.read_text())
    required = {
        "schema_version", "dataset_id", "data_source_label", "bbox_wgs84",
        "license", "osm_source", "source_artifacts", "conversion", "repairs",
        "source_roadnet_sha256", "roadnet_expected_sha256",
        "expected_controlled_signals", "expected_min_green_phases_per_agent",
        "demand_provenance",
    }
    missing = sorted(required - set(provenance))
    if missing:
        raise ValueError("provenance missing required fields: %s" % missing)
    if provenance["dataset_id"] != config["dataset_id"]:
        raise ValueError("provenance dataset_id mismatch")
    if provenance["roadnet_expected_sha256"] != network["sha256"]:
        raise ValueError("provenance roadnet hash mismatch")
    if provenance["expected_controlled_signals"] != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("provenance controlled signal count mismatch")
    if provenance["expected_min_green_phases_per_agent"] != 2:
        raise ValueError("provenance green phase minimum mismatch")
    for field in ("commands", "osmium_version", "netconvert_version", "converter_image_digest"):
        if field not in provenance["conversion"]:
            raise ValueError("provenance conversion field missing: %s" % field)
    if not isinstance(provenance["conversion"]["commands"], list):
        raise ValueError("provenance conversion commands must be a list")
    demand = provenance["demand_provenance"]
    source = config.get("temporal_profile_source", {})
    if (demand.get("temporal_profile_path") != source.get("path")
            or demand.get("temporal_profile_sha256") != source.get("sha256")
            or demand.get("applied_motorcycle_ratio") != config.get("motorcycle_ratio")):
        raise ValueError("provenance demand inputs differ from generator config")
    return provenance


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
    provenance = _verify_provenance(root, network["provenance"], network, config)

    actual = audit_network(network_path)
    if actual["controlled_signals"] != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("controlled signal count audit mismatch")
    for field in (
        "roads",
        "lanes",
        "intersections",
        "controlled_signals",
        "green_phases",
        "agent_green_phase_counts",
        "agent_ids",
        "directed_signal_edges",
        "weak_components",
        "phase_errors",
    ):
        if network.get(field) != actual[field]:
            raise ValueError("network audit field mismatch: %s" % field)
    if actual["phase_errors"]:
        raise ValueError("network phase audit failed")
    if min(actual["agent_green_phase_counts"].values()) < 2:
        raise ValueError("controlled signal has fewer than two green phases")
    repairs = provenance["repairs"]
    if provenance["source_roadnet_sha256"] != network["sha256"] and not repairs:
        raise ValueError("provenance must document roadnet repairs")
    roadnet_data = RoadNet.load(str(network_path))
    for repair in repairs:
        required = {"type", "intersection_id", "before", "after", "rationale"}
        if not required.issubset(repair):
            raise ValueError("provenance repair record is incomplete")
        intersection = roadnet_data._by_id.get(repair["intersection_id"])
        if intersection is None or intersection["trafficLight"]["lightphases"] != repair["after"]:
            raise ValueError("provenance repair does not match canonical network")
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
