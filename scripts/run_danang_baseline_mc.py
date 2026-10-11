#!/usr/bin/env python3
"""Monte-Carlo robustness of the non-learning baselines on the Da Nang junction.

Each realization k draws one count-preserving departure realization of the
observed camera profile (demand_seed = 100000 + k) plus one SUMO seed
(sim_seed = 200000 + k); all three baselines run on that same pair, so the
results are paired.  Seeds are disjoint from the protocol's train/validation/
test seeds (11, 31, 101-105, 201-205).

These are N realizations of ONE observed profile, not N independent traffic
days (see the manifest's independence_limit).

  python3 scripts/run_danang_baseline_mc.py --parity          # gate
  python3 scripts/run_danang_baseline_mc.py -n 1000 -j 10      # resumable
"""

import argparse
import hashlib
import json
import random
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import (
    HystereticMaxPressureController,
    MaxPressureController,
)
from traffic_rl.eval.runner import run_episode
from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv

CONTROLLERS = ("published_fixed", "max_pressure", "hysteretic_mp")
SCENARIOS = ("normal", "am_peak", "pm_peak")
DEMAND_SEED_BASE = 100000
SIM_SEED_BASE = 200000
OUT_DIR = ROOT / "results" / "danang_baseline_mc"

# Copied verbatim from the pruned scripts/build_danang_pilot.py (b436bc0^),
# which generated the protocol's demand realizations.
SUMO_VEHICLE_TYPES = {
    "motorcycle": {"vClass": "motorcycle", "length": "2.0", "width": "0.8",
                   "accel": "3.5", "decel": "5.0", "minGap": "0.5",
                   "maxSpeed": "13.89", "sigma": "0.7", "tau": "1.2",
                   "minGapLat": "0.30",
                   "latAlignment": "compact", "lcSublane": "1.0", "lcPushy": "0.0"},
    "car": {"vClass": "passenger", "length": "5.0", "width": "1.8",
            "accel": "2.0", "decel": "4.5", "minGap": "2.5",
            "maxSpeed": "11.11", "sigma": "0.5"},
    "truck": {"vClass": "truck", "length": "8.0", "width": "2.5",
              "accel": "1.3", "decel": "4.0", "minGap": "3.0",
              "maxSpeed": "10.0", "sigma": "0.5"},
    "bus": {"vClass": "bus", "length": "12.0", "width": "2.5",
            "accel": "1.2", "decel": "4.0", "minGap": "3.0",
            "maxSpeed": "10.0", "sigma": "0.5"},
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_sumo_vehicle_realization(network, demand, route_path, demand_seed):
    """Write an explicit, count-preserving departure realization for one seed."""
    route_path = Path(route_path)
    route_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")
    for kind in ("motorcycle", "car", "truck", "bus"):
        ET.SubElement(root, "vType", dict({"id": kind}, **SUMO_VEHICLE_TYPES[kind]))

    rng = random.Random(int(demand_seed))
    vehicles = []
    duration = float(demand["duration_seconds"])
    for movement in demand["movements"]:
        origin = movement["approach"]
        destination = movement["destination"]
        route_id = "%s_%s" % (origin, destination)
        edges = (network["route_edges"]["in_" + origin] +
                 network["route_edges"]["out_" + destination])
        ET.SubElement(root, "route", {"id": route_id, "edges": " ".join(edges)})
        for kind in ("motorcycle", "car", "truck", "bus"):
            count = int(round(movement["vehicle_rates_per_hour"][kind] *
                              duration / 3600.0))
            for index in range(count):
                depart = (index + rng.random()) * duration / max(count, 1)
                vehicles.append((depart, {
                    "id": "%s_%s_%04d" % (route_id, kind, index),
                    "type": kind,
                    "route": route_id,
                    "depart": "%.3f" % depart,
                    "departLane": "best",
                    "departPos": "random_free",
                    "departSpeed": "max",
                }))
    for _, attributes in sorted(vehicles, key=lambda item: item[0]):
        ET.SubElement(root, "vehicle", attributes)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(route_path), encoding="utf-8", xml_declaration=True)
    return {"route_sha256": _sha256(route_path), "scheduled_vehicles": len(vehicles)}


def _context():
    config = yaml.safe_load((ROOT / "configs/danang_pilot.yaml").read_text())
    protocol_dir = ROOT / config["protocol_dir"]
    manifest = json.loads((protocol_dir / "experiment-manifest.json").read_text())
    network = json.loads((ROOT / "results/research_pilot/generated/"
                          "build-manifest.json").read_text())["network"]
    demands = dict((s, json.loads((protocol_dir / "demands" /
                                   ("demand_observed_%s.json" % s)).read_text()))
                   for s in SCENARIOS)
    return config, manifest, network, demands


def _make_controller(name, env):
    if name == "published_fixed":
        return FixedTimeController(env.num_actions)
    if name == "max_pressure":
        return MaxPressureController(env.roadnet)
    # Same hysteresis as scripts/evaluate_danang_protocol.py.
    return HystereticMaxPressureController(
        env.roadnet, min_hold_decisions=6, switch_threshold=0)


def run_case(config, manifest, route_path, scheduled, sim_seed, controller):
    simulation = config["simulation"]
    env = SumoSingleJunctionEnv(
        ROOT / manifest["network_path"], route_path, scheduled, seed=sim_seed,
        action_interval=simulation["action_interval"],
        max_steps=simulation["horizon_seconds"],
        yellow_time=simulation["yellow_time"],
        min_green=simulation["min_green"],
        count_norm=simulation["count_norm"],
        control_mode=("static_program" if controller == "published_fixed"
                      else "agent"),
    )
    started = time.time()
    try:
        metrics = run_episode(env, _make_controller(controller, env))
    finally:
        env.close()
    metrics.update(env.final_safety_metrics())
    metrics["wall_seconds"] = time.time() - started
    return metrics


def _realization(task):
    scenario, k = task
    config, manifest, network, demands = _context()
    demand_seed, sim_seed = DEMAND_SEED_BASE + k, SIM_SEED_BASE + k
    rows = []
    with tempfile.TemporaryDirectory(prefix="danang-mc-") as tmp:
        route = Path(tmp) / "route.rou.xml"
        realization = write_sumo_vehicle_realization(
            network, demands[scenario], route, demand_seed)
        for controller in CONTROLLERS:
            m = run_case(config, manifest, route,
                         realization["scheduled_vehicles"], sim_seed, controller)
            rows.append({
                "scenario": scenario, "k": k, "controller": controller,
                "demand_seed": demand_seed, "sim_seed": sim_seed,
                "route_sha256": realization["route_sha256"],
                "scheduled_vehicles": realization["scheduled_vehicles"],
                "queue_integral_vehicle_hours": m["queue_integral_vehicle_hours"],
                "arrived": m.get("arrived"), "pending": m.get("pending"),
                "collisions": m.get("collisions"),
                "emergency_braking": m.get("emergency_braking"),
                "wall_seconds": round(m["wall_seconds"], 2),
            })
    return rows


def parity():
    """Reproduce test_am_peak_demand101 (sim_seed 201) and compare to the
    frozen protocol evaluation before trusting any Monte-Carlo run."""
    config, manifest, network, demands = _context()
    case = next(c for c in manifest["cases"]
                if c["case_id"] == "test_am_peak_demand101")
    ok = True
    with tempfile.TemporaryDirectory(prefix="danang-mc-parity-") as tmp:
        route = Path(tmp) / "route.rou.xml"
        r = write_sumo_vehicle_realization(network, demands["am_peak"], route, 101)
        same_hash = r["route_sha256"] == case["demand_sha256"]
        same_count = r["scheduled_vehicles"] == case["scheduled_vehicles"]
        print("route sha256 match:", same_hash, "| vehicles match:", same_count)
        ok = ok and same_count
        for controller in ("published_fixed", "max_pressure"):
            frozen = json.loads((ROOT / config["protocol_dir"] / "evaluation" /
                                 (controller + ".json")).read_text())
            ref = next(x for x in frozen if x["case_id"] == case["case_id"])
            m = run_case(config, manifest, route, r["scheduled_vehicles"],
                         201, controller)
            new = m["queue_integral_vehicle_hours"]
            old = ref["queue_integral_vehicle_hours"]
            match = abs(new - old) < 1e-6
            print("%-16s frozen %.4f  now %.4f  match=%s  (%.1fs)"
                  % (controller, old, new, match, m["wall_seconds"]))
            ok = ok and match
    print("PARITY", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity", action="store_true")
    parser.add_argument("-n", type=int, default=1000)
    parser.add_argument("-j", type=int, default=10)
    parser.add_argument("--out", default=str(OUT_DIR / "runs.jsonl"))
    args = parser.parse_args()
    if args.parity:
        return parity()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        counts = {}
        for line in out.read_text().splitlines():
            row = json.loads(line)
            key = (row["scenario"], row["k"])
            counts[key] = counts.get(key, 0) + 1
        done = set(key for key, c in counts.items() if c == len(CONTROLLERS))
    tasks = [(s, k) for k in range(args.n) for s in SCENARIOS
             if (s, k) not in done]
    print("realizations done %d, remaining %d" % (len(done), len(tasks)), flush=True)
    started = time.time()
    with Pool(args.j) as pool, out.open("a") as stream:
        for i, rows in enumerate(pool.imap_unordered(_realization, tasks), 1):
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            if i % 10 == 0 or i == len(tasks):
                print("%d/%d  %.0fs elapsed" % (i, len(tasks), time.time() - started),
                      flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
