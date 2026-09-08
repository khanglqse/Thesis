#!/usr/bin/env python3
"""Prepare, execute, resume, or verify the frozen Hai Chau campaign."""

import argparse
import json
import subprocess
from pathlib import Path

from traffic_rl.eval.network_campaign import expand_runs, run_pending, verify_campaign


def _write_campaign(path, runs):
    path.mkdir(parents=True, exist_ok=True)
    target = path / "campaign-manifest.json"
    payload = {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if target.exists() and target.read_text() != encoded:
        raise ValueError("refusing to change an existing campaign manifest")
    target.write_text(encoded)


def _subprocess_executor(run, run_dir):
    command = run.get("command")
    if not command:
        raise ValueError("run has no command; integrate the controller before execution")
    completed = subprocess.run(
        command, cwd=str(Path.cwd()), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError("executor exited %s: %s" % (
            completed.returncode, completed.stderr.strip()))
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("executor must print a JSON result on its final line")
    result = json.loads(lines[-1])
    result["stdout"] = completed.stdout
    result["stderr"] = completed.stderr
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", default="results/haichau_network_v2/final")
    parser.add_argument("--manifest")
    parser.add_argument("--learning-seeds", default="11,12,13,14,15")
    parser.add_argument("--controllers", default=(
        "tuned_fixed,max_pressure,hysteretic_mp,shared_ddqn_legacy,"
        "neighbor_phase_ddqn"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    campaign_dir = Path(args.campaign_dir)

    if args.verify_only:
        print(json.dumps(verify_campaign(campaign_dir), sort_keys=True))
        return 0
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        seeds = [int(value) for value in args.learning_seeds.split(",") if value]
        controllers = [value for value in args.controllers.split(",") if value]
        _write_campaign(campaign_dir, expand_runs(manifest, seeds, controllers))
    if args.prepare_only:
        return 0
    result = run_pending(campaign_dir, _subprocess_executor)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
