#!/usr/bin/env python3
"""Evaluate frozen controllers on synthetic AM demand-scale sensitivity cases."""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.agents.dqn import DQNController, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode
from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", choices=("published_fixed", "dueling_n3"),
                        required=True)
    parser.add_argument("--train-seed", type=int)
    args = parser.parse_args()
    if args.controller == "dueling_n3" and args.train_seed is None:
        parser.error("--train-seed is required for dueling_n3")
    config = yaml.safe_load((ROOT / "configs/danang_pilot.yaml").read_text())
    simulation = config["simulation"]
    root = ROOT / "results/danang_protocol_v1/sensitivity"
    cases = json.loads((root / "manifest.json").read_text())["cases"]
    output_name = args.controller + (
        "_seed%d" % args.train_seed if args.train_seed is not None else "") + ".json"
    output = root / output_name
    rows = []
    for case in cases:
        sim_seed = case["demand_seed"] + 100
        static = args.controller == "published_fixed"
        env = SumoSingleJunctionEnv(
            ROOT / config["network"], ROOT / case["route_path"],
            case["scheduled_vehicles"], seed=sim_seed,
            action_interval=simulation["action_interval"],
            max_steps=simulation["horizon_seconds"],
            yellow_time=simulation["yellow_time"], min_green=simulation["min_green"],
            count_norm=simulation["count_norm"],
            control_mode="static_program" if static else "agent")
        if static:
            controller = FixedTimeController(env.num_actions)
        else:
            variant = config["training_variants"]["dueling_n3"]
            net = SharedDQN(env.obs_dim, 3, hidden=variant["hidden"], lr=variant["lr"],
                            seed=args.train_seed, dueling=True,
                            grad_clip=config["training_common"]["grad_clip"])
            net.load(ROOT / config["protocol_dir"] / "training" /
                     ("dueling_n3_seed%d" % args.train_seed) / "dqn.npz")
            controller = DQNController(net, env.agent_ids)
        try:
            metrics = run_episode(env, controller)
        finally:
            env.close()
        metrics.update(env.final_safety_metrics())
        metrics.update({"case_id": case["case_id"], "scale": case["scale"],
                        "demand_seed": case["demand_seed"], "sim_seed": sim_seed,
                        "train_seed": args.train_seed, "controller_id": args.controller,
                        "data_status": case["data_status"]})
        rows.append(metrics)
        output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
        print(case["case_id"], round(metrics["queue_integral_vehicle_hours"], 2),
              flush=True)
    print(output)


if __name__ == "__main__":
    main()
