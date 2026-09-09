#!/usr/bin/env python3
"""Run the preregistered V3-B residual smoke/pilot in the CityFlow image."""
import argparse
import json
import os
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.train_haichau_network import _make_env_factory
from traffic_rl.train.network_trainer import resolve_training_config
from traffic_rl.train.schedule_residual_trainer import train_residual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("smoke", "pilot"))
    parser.add_argument("--learning-seed", type=int, default=11)
    parser.add_argument("--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--config", default="configs/haichau_training_v3b_residual.yaml")
    parser.add_argument("--baseline-tuning-artifact",
                        default="results/haichau_network_v2/training/final-baseline-tuning.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    os.chdir(str(ROOT))
    manifest = json.loads((ROOT / args.manifest).read_text())
    config = resolve_training_config(yaml.safe_load((ROOT / args.config).read_text()),
                                      args.mode, args.learning_seed)
    # The environment's legacy local reward is ignored. Macro rewards consume
    # the exact network+pending integrals accumulated at each simulator second.
    factory_config = dict(config, reward={"queue_weight": 1.0,
                                        "downstream_block_weight": 0.0,
                                        "switch_penalty": 0.0})
    output = ROOT / args.output
    factory = _make_env_factory(manifest, factory_config, output, "neighbor_phase_ddqn")
    summary = train_residual(factory, manifest, config, str(output), str(ROOT),
                              str(ROOT / args.baseline_tuning_artifact))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
