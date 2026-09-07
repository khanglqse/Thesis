#!/usr/bin/env python3
"""Export compact, deterministic SUMO replays for the offline thesis defense."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.agents.dqn import DQNController, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode
from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv


OUT = ROOT / "results/defense_bundle/v1"
SAMPLE_SECONDS = 5
TRAIN_SEED = 12  # median best-validation policy among seeds 11--15
DEMAND_SEED = 103  # median fixed-time PM queue among held-out demand cases


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def network_geometry(network_path):
    import sumolib
    net = sumolib.net.readNet(str(network_path))
    edges = []
    for edge in net.getEdges():
        if edge.getID().startswith(("in_", "out_")):
            edges.append({"id": edge.getID(), "shape": [
                [round(x, 2), round(y, 2)] for x, y in edge.getShape()]})
    xs = [p[0] for edge in edges for p in edge["shape"]]
    ys = [p[1] for edge in edges for p in edge["shape"]]
    return {"edges": edges, "bounds": [min(xs), min(ys), max(xs), max(ys)],
            "coordinate_units": "local SUMO metres"}


def original_metric(controller_id, scenario, demand_seed, train_seed=None):
    name = controller_id
    if train_seed is not None:
        name += "_seed%d" % train_seed
    rows = json.loads((ROOT / "results/danang_protocol_v1/evaluation" /
                       (name + ".json")).read_text())
    return next(row for row in rows if row["scenario"] == scenario and
                int(row["demand_seed"]) == demand_seed)


def export_run(config, case, controller_id):
    frames = []
    holder = {}

    def capture(base):
        if base["simulation_time"] % SAMPLE_SECONDS:
            return
        conn = holder["env"]._connection
        vehicles = []
        for vehicle_id in conn.vehicle.getIDList():
            x, y = conn.vehicle.getPosition(vehicle_id)
            vehicles.append([
                vehicle_id, round(x, 1), round(y, 1),
                round(float(conn.vehicle.getAngle(vehicle_id)), 1),
                conn.vehicle.getTypeID(vehicle_id),
            ])
        lanes = {}
        for direction, lane_ids in holder["env"]._incoming_lanes.items():
            lanes[direction] = int(sum(
                conn.lane.getLastStepHaltingNumber(lane_id) for lane_id in lane_ids))
        frames.append({"t": base["simulation_time"], "p": base["phase_index"],
                       "q": base["total_queue"], "nq": base["network_queue"],
                       "pending": base["pending"], "arrived": base["arrived"],
                       "lanes": lanes, "vehicles": vehicles})

    simulation = config["simulation"]
    static = controller_id == "published_fixed"
    env = SumoSingleJunctionEnv(
        ROOT / config["network"], ROOT / case["route_path"],
        case["scheduled_vehicles"], seed=case["demand_seed"] + 100,
        action_interval=simulation["action_interval"],
        max_steps=simulation["horizon_seconds"],
        yellow_time=simulation["yellow_time"], min_green=simulation["min_green"],
        count_norm=simulation["count_norm"],
        control_mode="static_program" if static else "agent",
        frame_callback=capture)
    holder["env"] = env
    if static:
        controller = FixedTimeController(env.num_actions)
        train_seed = None
    else:
        variant = config["training_variants"]["dueling_n3"]
        net = SharedDQN(env.obs_dim, 3, hidden=variant["hidden"], lr=variant["lr"],
                        seed=TRAIN_SEED, dueling=True,
                        grad_clip=config["training_common"]["grad_clip"])
        checkpoint = ROOT / config["protocol_dir"] / "training" / \
            ("dueling_n3_seed%d" % TRAIN_SEED) / "dqn.npz"
        net.load(checkpoint)
        controller = DQNController(net, env.agent_ids)
        train_seed = TRAIN_SEED
    try:
        metrics = run_episode(env, controller)
    finally:
        env.close()
    metrics.update(env.final_safety_metrics())
    expected = original_metric(controller_id, case["scenario"],
                               case["demand_seed"], train_seed)
    delta = abs(metrics["queue_integral_vehicle_hours"] -
                expected["queue_integral_vehicle_hours"])
    if delta > 1e-9:
        raise RuntimeError("replay metric does not reproduce frozen evaluation: %.12g" % delta)
    output = OUT / "replays" / (case["case_id"] + "__" + controller_id + ".json")
    payload = {"format_version": 1, "sample_seconds": SAMPLE_SECONDS,
               "case_id": case["case_id"], "scenario": case["scenario"],
               "controller_id": controller_id, "train_seed": train_seed,
               "demand_seed": case["demand_seed"],
               "sim_seed": case["demand_seed"] + 100,
               "metrics": {key: metrics[key] for key in (
                   "queue_integral_vehicle_hours", "arrived", "pending",
                   "completion_rate", "phase_switches", "collisions",
                   "emergency_braking")}, "frames": frames}
    output.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return output, payload["metrics"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "replays").mkdir(exist_ok=True)
    config = yaml.safe_load((ROOT / "configs/danang_pilot.yaml").read_text())
    protocol = json.loads((ROOT / "results/danang_protocol_v1/experiment-manifest.json").read_text())
    wanted = []
    for scenario in ("normal", "pm_peak"):
        wanted.append(next(c for c in protocol["cases"] if c["split"] == "test" and
                           c["scenario"] == scenario and
                           c["demand_seed"] == DEMAND_SEED))
    runs = []
    for case in wanted:
        for controller in ("published_fixed", "dueling_n3"):
            path, metrics = export_run(config, case, controller)
            runs.append({"case_id": case["case_id"], "scenario": case["scenario"],
                         "controller_id": controller,
                         "selection_rule": ("training seed 12 is the median validation policy; "
                                            "demand seed 103 is the median fixed-time PM case"),
                         "data_source_label": case["data_source_label"],
                         "measurement_window": "2025-04-01 " +
                            ("13:00-14:00" if case["scenario"] == "normal" else "17:00-18:00"),
                         "train_seed": TRAIN_SEED if controller == "dueling_n3" else None,
                         "demand_seed": DEMAND_SEED, "sim_seed": DEMAND_SEED + 100,
                         "simulator": "SUMO " + subprocess.check_output(
                             ["sumo", "--version"], text=True).splitlines()[0].split()[-1],
                         "replay_path": "replays/" + path.name,
                         "replay_sha256": sha256(path), "metrics": metrics})
    network_path = ROOT / config["network"]
    geometry_path = OUT / "network.json"
    geometry_path.write_text(json.dumps(network_geometry(network_path),
                                        separators=(",", ":")) + "\n")
    summary_source = ROOT / "results/danang_protocol_v1/summary/final-summary.json"
    manifest = {"bundle_version": 1, "created_at": "2026-09-07T22:00:00+07:00",
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "network": {"path": "network.json", "sha256": sha256(geometry_path),
                            "source_path": config["network"],
                            "coordinate_units": "local SUMO metres"},
                "initial_view": {"case_id": "test_pm_peak_demand103",
                                 "controller_left": "published_fixed",
                                 "controller_right": "dueling_n3",
                                 "simulation_time": 1800},
                "aggregate_results": {"source_path":
                    "results/danang_protocol_v1/summary/final-summary.json",
                    "sha256": sha256(summary_source)}, "runs": runs}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
