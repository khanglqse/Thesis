#!/usr/bin/env python3
"""Evaluate one frozen Hai Chau campaign run inside the pinned container."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.haichau_controller_runtime import evaluate_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--raw-replay",
                        help="optional CityFlow native telemetry output for a visual demo")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    manifest_path = Path(args.run_manifest)
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    try:
        run = json.loads(manifest_path.read_text())
    except ValueError:
        raise ValueError("run manifest is not valid JSON")
    runtime_dir = Path(args.runtime_dir)
    if not runtime_dir.is_absolute():
        runtime_dir = project_root / runtime_dir
    result = evaluate_run(
        project_root, run, runtime_dir, raw_replay_path=args.raw_replay)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
