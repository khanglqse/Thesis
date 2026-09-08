#!/usr/bin/env python3
"""Build deterministic Hai Chau demand files and their hash-bound manifest."""

import argparse
import json
from pathlib import Path

import yaml

from traffic_rl.network.haichau_dataset import (
    audit_network,
    build_flow_cases,
    build_route_coverage_provenance,
)
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import sha256_file, verify_artifact


BASE_IMAGE_DIGEST = "sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32"
BASE_IMAGE_NAME = "cityflowproject/cityflow"
DERIVED_IMAGE_TAG = "traffic-rl-cityflow-research:v2"


def _canonical_write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    else:
        payload = json.dumps(value, indent=2, sort_keys=True)
    path.write_text(payload + "\n")


def _under_root(root, path):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise ValueError("artifact path must be inside repository root: %s" % path)


def prepare(config_path, root=None, new_version=False):
    """Resolve a generator config into immutable flow files and a manifest."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    root = root.resolve()
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    config = yaml.safe_load(config_path.read_text())
    if config.get("schema_version") != 2:
        raise ValueError("Hai Chau generator config schema_version must be 2")

    roadnet_path = root / config["roadnet"]
    provenance_record = config.get("provenance", {})
    provenance_path = verify_artifact(root, provenance_record)
    provenance = json.loads(provenance_path.read_text())
    sumo_records = [
        record for record in provenance.get("source_artifacts", [])
        if record.get("role") == "sumo_network"
    ]
    if len(sumo_records) != 1:
        raise ValueError("provenance must identify exactly one SUMO network")
    sumo_artifact = sumo_records[0]
    sumo_path = verify_artifact(root, sumo_artifact)
    sumo_contract_record = {
        "path": sumo_artifact["path"],
        "sha256": sumo_artifact["sha256"],
    }
    phase_contract_record = config.get("phase_contract", {})
    phase_contract_path = verify_artifact(root, phase_contract_record)
    phase_contract = json.loads(phase_contract_path.read_text())
    network_audit = audit_network(
        roadnet_path,
        phase_contract,
        int(config["simulation"]["min_green"]),
        sumo_path,
        sumo_contract_record,
        provenance.get("repairs", []),
    )
    if network_audit["phase_errors"]:
        raise ValueError("network audit has phase errors")

    generator_hash = sha256_file(config_path)
    network_hash = sha256_file(roadnet_path)
    result_dir = root / "results" / config["dataset_id"]
    manifest_path = result_dir / "experiment-manifest.json"
    if manifest_path.exists() and not new_version:
        existing = json.loads(manifest_path.read_text())
        if (
            existing.get("generator_config_sha256") != generator_hash
            or existing.get("network", {}).get("sha256") != network_hash
        ):
            raise ValueError(
                "existing manifest network or generator hash differs; use --new-version"
            )

    roadnet = RoadNet.load(str(roadnet_path))
    generated_cases, route_catalog = build_flow_cases(
        roadnet, config, include_catalog=True
    )
    route_catalog_path = result_dir / "route-families.json"
    _canonical_write(route_catalog_path, route_catalog, compact=True)
    case_records = []
    for generated in generated_cases:
        case = dict(generated)
        flow = case.pop("flow")
        flow_path = result_dir / "demands" / (case["case_id"] + ".json")
        _canonical_write(flow_path, flow, compact=True)
        case["flow_path"] = _under_root(root, flow_path)
        case["flow_sha256"] = sha256_file(flow_path)
        case_records.append(case)

    network = dict(network_audit)
    network["path"] = _under_root(root, roadnet_path)
    network["sha256"] = network_hash
    network["provenance"] = dict(provenance_record)

    dockerfile_path = root / "docker" / "cityflow-research" / "Dockerfile"
    if not dockerfile_path.is_file():
        raise ValueError("CityFlow research Dockerfile is required")
    manifest = {
        "protocol_version": 2,
        "dataset_id": config["dataset_id"],
        "data_source_label": config["demand_label"],
        "generator_config_path": _under_root(root, config_path),
        "generator_config_sha256": generator_hash,
        "network": network,
        "phase_contract": dict(phase_contract_record),
        "route_families": {
            "path": _under_root(root, route_catalog_path),
            "sha256": sha256_file(route_catalog_path),
            "count": len(route_catalog),
            "partition_counts": {
                split: sum(1 for family in route_catalog if family["split"] == split)
                for split in ("train", "validation", "test")
            },
        },
        "route_coverage": build_route_coverage_provenance(
            roadnet, config, route_catalog, generated_cases
        ),
        "cases": case_records,
        "runtime": {
            "base_image": BASE_IMAGE_NAME,
            "base_image_digest": BASE_IMAGE_DIGEST,
            "derived_image_tag": DERIVED_IMAGE_TAG,
            "dockerfile": {
                "path": _under_root(root, dockerfile_path),
                "sha256": sha256_file(dockerfile_path),
            },
            "platform": "linux/amd64",
        },
        "preprocessing": config["preprocessing"],
        "simulation": config["simulation"],
    }
    _canonical_write(manifest_path, manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/haichau_network_v2.yaml", help="resolved YAML inputs"
    )
    parser.add_argument(
        "--new-version",
        action="store_true",
        help="deliberately replace a manifest bound to different inputs",
    )
    args = parser.parse_args(argv)
    manifest = prepare(args.config, new_version=args.new_version)
    print(
        json.dumps(
            {
                "manifest": "results/%s/experiment-manifest.json" % manifest["dataset_id"],
                "cases": len(manifest["cases"]),
                "network_sha256": manifest["network"]["sha256"],
                "generator_config_sha256": manifest["generator_config_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
