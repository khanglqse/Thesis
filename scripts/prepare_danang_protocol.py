#!/usr/bin/env python3
"""Materialize independent Da Nang departure realizations and protocol manifest."""

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_danang_pilot import (
    build_observed_camera_demand_files,
    write_sumo_vehicle_realization,
)
from traffic_rl.eval.runner import validate_experiment_manifest


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(config_path=ROOT / "configs/danang_pilot.yaml"):
    config_path = Path(config_path)
    config = yaml.safe_load(config_path.read_text())
    output = ROOT / config["protocol_dir"]
    demands_dir = output / "demands"
    demands_dir.mkdir(parents=True, exist_ok=True)
    pilot_manifest = json.loads(
        (ROOT / "results/research_pilot/generated/build-manifest.json").read_text())
    network = pilot_manifest["network"]
    demands = build_observed_camera_demand_files(
        ROOT / config["source_camera_csv"], demands_dir)

    cases = []

    def add_case(split, scenario, demand_seed):
        case_id = "%s_%s_demand%d" % (split, scenario, demand_seed)
        route_path = demands_dir / (case_id + ".rou.xml")
        realization = write_sumo_vehicle_realization(
            network, demands[scenario], route_path, demand_seed)
        cases.append({
            "case_id": case_id,
            "split": split,
            "scenario": scenario,
            "demand_seed": demand_seed,
            "demand_sha256": realization["route_sha256"],
            "route_path": str(route_path.relative_to(ROOT)),
            "scheduled_vehicles": realization["scheduled_vehicles"],
            "data_source_label": "observed_digitized_partial_coverage",
            "source_id": demands[scenario]["source_id"],
        })

    for split in ("train", "validation"):
        row = config["split"][split]
        add_case(split, row["scenario"], int(row["demand_seed"]))
    test = config["split"]["test"]
    for scenario in test["scenarios"]:
        for demand_seed in test["demand_seeds"]:
            add_case("test", scenario, int(demand_seed))

    manifest = {
        "protocol_version": 1,
        "protocol_id": "danang_observed_camera_v1",
        "network_path": config["network"],
        "network_sha256": _sha256(ROOT / config["network"]),
        "config_path": str(config_path.relative_to(ROOT)),
        "config_sha256": _sha256(config_path),
        "independence_limit": (
            "departure realizations are independent, but all observed profiles "
            "come from one published date and are not independent survey days"
        ),
        "cases": cases,
        "runs": [],
    }
    manifest["validation"] = validate_experiment_manifest(manifest)
    (output / "experiment-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    result = prepare()
    print(json.dumps(result["validation"], indent=2))
