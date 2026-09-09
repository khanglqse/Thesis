#!/usr/bin/env python3
"""Evaluate one frozen V3 robustness run inside the pinned CityFlow image."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.robustness_runtime import evaluate_robustness_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    manifest_path = Path(args.run_manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    run = json.loads(manifest_path.read_text())
    runtime_dir = Path(args.runtime_dir)
    if not runtime_dir.is_absolute():
        runtime_dir = root / runtime_dir
    result = evaluate_robustness_run(root, run, runtime_dir)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
