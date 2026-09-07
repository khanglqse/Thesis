#!/usr/bin/env python3
"""Build labeled synthetic demand-scale cases around the observed AM profile."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_danang_pilot import (
    build_observed_camera_demand_files,
    scale_demand,
    write_sumo_vehicle_realization,
)


def main():
    output = ROOT / "results/danang_protocol_v1/sensitivity"
    demands_dir = output / "demands"
    base = build_observed_camera_demand_files(
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        demands_dir)["am_peak"]
    network = json.loads((ROOT / "results/research_pilot/generated/build-manifest.json").read_text())[
        "network"]
    cases = []
    for scale in (0.75, 1.0, 1.25, 1.5):
        demand = scale_demand(base, scale)
        for seed in (101, 102, 103, 104, 105):
            case_id = "am_scale_%03d_demand%d" % (round(scale * 100), seed)
            path = demands_dir / (case_id + ".rou.xml")
            artifact = write_sumo_vehicle_realization(
                network, demand, path, demand_seed=seed)
            cases.append({
                "case_id": case_id, "scale": scale, "demand_seed": seed,
                "scheduled_vehicles": artifact["scheduled_vehicles"],
                "route_path": str(path.relative_to(ROOT)),
                "demand_sha256": artifact["route_sha256"],
                "data_status": "synthetic_scale_sensitivity",
            })
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps({"cases": cases}, indent=2) + "\n")
    print(output / "manifest.json")


if __name__ == "__main__":
    main()

