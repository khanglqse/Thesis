#!/usr/bin/env python3
"""Train a reproducible DQN candidate on the native SUMO Da Nang pilot."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv
from traffic_rl.train.trainer import train


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="dueling_n3")
    parser.add_argument("--train-seed", type=int, required=True)
    parser.add_argument("--episodes", type=int)
    args = parser.parse_args()
    config_path = ROOT / "configs/danang_pilot.yaml"
    config = yaml.safe_load(config_path.read_text())
    protocol_dir = ROOT / config["protocol_dir"]
    protocol = json.loads((protocol_dir / "experiment-manifest.json").read_text())
    cases = dict((case["split"], case) for case in protocol["cases"]
                 if case["split"] in ("train", "validation"))
    training = dict(config["training_common"])
    training.update(config["training_variants"][args.variant])
    training["seed"] = args.train_seed
    if args.episodes is not None:
        training["episodes"] = args.episodes
    simulation = config["simulation"]

    def make_env(case, sim_seed):
        return SumoSingleJunctionEnv(
            ROOT / config["network"], ROOT / case["route_path"],
            case["scheduled_vehicles"], seed=sim_seed,
            action_interval=simulation["action_interval"],
            max_steps=simulation["horizon_seconds"],
            yellow_time=simulation["yellow_time"],
            min_green=simulation["min_green"],
            count_norm=simulation["count_norm"],
        )

    train_case = cases["train"]
    validation_case = cases["validation"]
    output = protocol_dir / "training" / ("%s_seed%d" % (args.variant, args.train_seed))
    output.mkdir(parents=True, exist_ok=True)
    run_manifest = {
        "variant": args.variant,
        "train_seed": args.train_seed,
        "training_config": training,
        "training_case": train_case,
        "validation_case": validation_case,
        "network_sha256": protocol["network_sha256"],
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "checkpoint_selection": "lowest full-horizon validation mean total queue",
    }
    (output / "run-manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n")
    train(
        lambda: make_env(train_case, config["split"]["train"]["sim_seed"]),
        training,
        str(output / "dqn.npz"),
        str(output / "train-log.json"),
        eval_env_factory=lambda: make_env(
            validation_case, config["split"]["validation"]["sim_seed"]),
    )
    run_manifest["checkpoint_sha256"] = _sha256(output / "dqn.npz")
    (output / "run-manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
