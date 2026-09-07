#!/usr/bin/env python3
"""Evaluate one frozen controller across every held-out Da Nang test case."""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.agents.dqn import DQNController, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import (
    HystereticMaxPressureController,
    MaxPressureController,
)
from traffic_rl.eval.runner import run_episode
from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", required=True,
                        choices=("published_fixed", "max_pressure",
                                 "hysteretic_mp", "dueling_n3"))
    parser.add_argument("--train-seed", type=int)
    args = parser.parse_args()
    if args.controller == "dueling_n3" and args.train_seed is None:
        parser.error("--train-seed is required for dueling_n3")

    config = yaml.safe_load((ROOT / "configs/danang_pilot.yaml").read_text())
    protocol_dir = ROOT / config["protocol_dir"]
    manifest = json.loads((protocol_dir / "experiment-manifest.json").read_text())
    simulation = config["simulation"]
    test_seeds = config["split"]["test"]
    sim_seed_by_demand = dict(zip(test_seeds["demand_seeds"],
                                   test_seeds["sim_seeds"]))
    output_dir = protocol_dir / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ("_seed%d" % args.train_seed
              if args.controller == "dueling_n3" else "")
    output_path = output_dir / (args.controller + suffix + ".json")
    rows = []

    for case in manifest["cases"]:
        if case["split"] != "test":
            continue
        sim_seed = int(sim_seed_by_demand[case["demand_seed"]])
        static = args.controller == "published_fixed"
        env = SumoSingleJunctionEnv(
            ROOT / manifest["network_path"], ROOT / case["route_path"],
            case["scheduled_vehicles"], seed=sim_seed,
            action_interval=simulation["action_interval"],
            max_steps=simulation["horizon_seconds"],
            yellow_time=simulation["yellow_time"],
            min_green=simulation["min_green"],
            count_norm=simulation["count_norm"],
            control_mode="static_program" if static else "agent",
        )
        if args.controller == "published_fixed":
            controller = FixedTimeController(env.num_actions)
        elif args.controller == "max_pressure":
            controller = MaxPressureController(env.roadnet)
        elif args.controller == "hysteretic_mp":
            controller = HystereticMaxPressureController(
                env.roadnet, min_hold_decisions=6, switch_threshold=0)
        else:
            variant = config["training_variants"]["dueling_n3"]
            net = SharedDQN(
                env.obs_dim, 3, hidden=variant["hidden"], lr=variant["lr"],
                seed=args.train_seed,
                grad_clip=config["training_common"]["grad_clip"],
                huber_delta=config["training_common"]["huber_delta"],
                dueling=True,
            )
            checkpoint = (protocol_dir / "training" /
                          ("dueling_n3_seed%d" % args.train_seed) / "dqn.npz")
            net.load(checkpoint)
            controller = DQNController(net, env.agent_ids)
        started = time.time()
        try:
            metrics = run_episode(env, controller)
        finally:
            env.close()
        metrics.update(env.final_safety_metrics())
        metrics.update({
            "run_id": "%s%s_%s" % (args.controller, suffix, case["case_id"]),
            "controller_id": args.controller,
            "train_seed": args.train_seed,
            "demand_seed": case["demand_seed"],
            "sim_seed": sim_seed,
            "case_id": case["case_id"],
            "scenario": case["scenario"],
            "demand_sha256": case["demand_sha256"],
            "wall_seconds": time.time() - started,
        })
        rows.append(metrics)
        print(case["case_id"], round(metrics["queue_integral_vehicle_hours"], 2),
              metrics["arrived"], metrics["pending"], flush=True)
        output_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    print(output_path)


if __name__ == "__main__":
    main()
