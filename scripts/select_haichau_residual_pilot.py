#!/usr/bin/env python3
"""Select the preregistered residual pilot checkpoint."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.train_haichau_network import _make_env_factory
from traffic_rl.research.pilot_residual_selector import (
    make_env_validation_runner, select_from_spec)
from traffic_rl.train.network_trainer import resolve_training_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        default="configs/haichau_residual_pilot_selection_v1.yaml")
    args = parser.parse_args(argv)
    os.chdir(str(ROOT))
    spec = yaml.safe_load((ROOT / args.spec).read_text())
    manifest = json.loads((ROOT / spec["manifest"]).read_text())
    source = yaml.safe_load((ROOT / spec["arm"]["config"]).read_text())
    config = resolve_training_config(source, "pilot", 11)
    factory_config = dict(config, reward={
        "queue_weight": 1.0, "downstream_block_weight": 0.0,
        "switch_penalty": 0.0})
    runtime_parent = ROOT / "results/haichau_network_v2/training"
    runtime_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            prefix=".v3b-selector-runtime-", dir=str(runtime_parent)) as temp:
        factory = _make_env_factory(
            manifest, factory_config, Path(temp), "neighbor_phase_ddqn")
        decision = select_from_spec(
            ROOT, args.spec,
            make_env_validation_runner(
                factory, config.get("safety", {}).get("min_score_margin", 0.0)))
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
