#!/usr/bin/env python3
"""Run the preregistered validation-only final selector for one residual seed."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.train_haichau_network import _make_env_factory
from traffic_rl.research.final_residual_selector import select_seed_from_spec
from traffic_rl.research.pilot_residual_selector import make_env_validation_runner
from traffic_rl.research.residual_release import resolve_frozen_final_residual_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="configs/haichau_residual_final_selection_v1.yaml")
    parser.add_argument("--learning-seed", type=int, required=True)
    args = parser.parse_args(argv)
    os.chdir(str(ROOT))
    spec_path = ROOT / args.spec
    spec = yaml.safe_load(spec_path.read_text())
    if not isinstance(spec, dict):
        parser.error("final residual selector spec must be a YAML mapping")
    manifest = json.loads((ROOT / spec["manifest"]).read_text())
    config, _ = resolve_frozen_final_residual_config(
        ROOT, spec["pilot_selector_spec"], spec["selected_config"], args.learning_seed)
    factory_config = dict(config, reward={
        "queue_weight": 1.0, "downstream_block_weight": 0.0,
        "switch_penalty": 0.0})
    runtime_parent = ROOT / "results/haichau_network_v2/training"
    runtime_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            prefix=".v3b-final-selector-runtime-", dir=str(runtime_parent)) as temp:
        factory = _make_env_factory(
            manifest, factory_config, Path(temp), "neighbor_phase_ddqn")
        decision = select_seed_from_spec(
            ROOT, args.spec, args.learning_seed, make_env_validation_runner(factory))
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
