#!/usr/bin/env python3
"""Diagnose pressure policies on frozen validation cases only; never run test cases."""
import argparse
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.train_haichau_network import _make_env_factory
from traffic_rl.eval.pressure_validation import evaluate_pressure_validation
from traffic_rl.train.network_trainer import resolve_training_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--config", default="configs/haichau_training_v2.yaml")
    parser.add_argument("--baseline-tuning-artifact", required=True)
    parser.add_argument("--output", required=True,
                        help="new diagnostic directory; existing directories are refused")
    args = parser.parse_args(argv)
    manifest = json.loads((ROOT / args.manifest).read_text())
    config = yaml.safe_load((ROOT / args.config).read_text())
    # Resolve only the common horizon/reward/env configuration. No learner is built.
    resolved = resolve_training_config(config, "final", learning_seed=11)
    resolved["simulation"] = manifest["simulation"]
    output = ROOT / args.output
    factory = _make_env_factory(manifest, resolved, output, "neighbor_phase_ddqn")
    result = evaluate_pressure_validation(
        factory, manifest, resolved, str(ROOT / args.baseline_tuning_artifact),
        output, ROOT)
    print(json.dumps({"status": result["status"], "rows": len(result["rows"]),
                      "diagnostic_path": str(output / "diagnostic.json"),
                      "eligible_for_release": False}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
