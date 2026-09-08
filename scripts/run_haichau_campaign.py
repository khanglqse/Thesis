#!/usr/bin/env python3
"""Prepare, execute, resume, or verify the frozen Hai Chau campaign."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from traffic_rl.eval.network_campaign import (
    CONTROLLERS,
    bind_frozen_manifest,
    expand_runs,
    run_pending,
    verify_campaign,
)
from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    runtime = verify_runtime(PROJECT_ROOT, run)
    if runtime["runtime_image_id"] != run.get("runtime_image_id"):
        raise ValueError("executor Docker image ID differs from frozen run")
    docker_command = [
        "docker", "run", "--rm", "--network", "none",
        "-v", "%s:/work" % PROJECT_ROOT, "-w", "/work",
        run["runtime_image"],
    ] + list(command)
    completed = subprocess.run(
        docker_command, cwd=str(PROJECT_ROOT), universal_newlines=True,
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
    parser.add_argument(
        "--protocol", default="results/haichau_network_v2/final/frozen-protocol.json")
    parser.add_argument("--learning-seeds", default="11,12,13,14,15")
    parser.add_argument("--controllers", default=(
        "tuned_fixed,max_pressure,hysteretic_mp,shared_ddqn_legacy,"
        "neighbor_phase_ddqn"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    campaign_dir = Path(args.campaign_dir)

    protocol_path = Path(args.protocol)
    if not protocol_path.is_absolute():
        protocol_path = PROJECT_ROOT / protocol_path
    if not protocol_path.is_file():
        raise ValueError("frozen protocol is required")
    protocol = json.loads(protocol_path.read_text())
    verify_git_checkout(PROJECT_ROOT, protocol.get("code_commit"))
    verify_runtime(PROJECT_ROOT, protocol)

    if args.verify_only:
        manifest_path = Path(protocol.get("case_manifest_path", ""))
        if not manifest_path.is_absolute():
            manifest_path = PROJECT_ROOT / manifest_path
        if not manifest_path.is_file() \
                or _sha256(manifest_path) != protocol.get("case_manifest_sha256"):
            raise ValueError("frozen case manifest is missing or changed")
        manifest = bind_frozen_manifest(
            json.loads(manifest_path.read_text()), protocol)
        seeds = protocol.get("acceptance_rules", {}).get(
            "required_learning_seeds", [])
        expected = expand_runs(manifest, seeds, CONTROLLERS)
        actual = json.loads(
            (campaign_dir / "campaign-manifest.json").read_text()).get("runs")
        if actual != expected:
            raise ValueError("campaign differs from frozen protocol")
        print(json.dumps(verify_campaign(campaign_dir), sort_keys=True))
        return 0
    if args.manifest:
        manifest_path = Path(args.manifest)
        if _sha256(manifest_path) != protocol.get("case_manifest_sha256"):
            raise ValueError("case manifest hash differs from frozen protocol")
        manifest = bind_frozen_manifest(
            json.loads(manifest_path.read_text()), protocol)
        seeds = [int(value) for value in args.learning_seeds.split(",") if value]
        frozen_seeds = protocol.get("acceptance_rules", {}).get(
            "required_learning_seeds")
        if seeds != frozen_seeds:
            raise ValueError("learning seeds differ from frozen acceptance rules")
        controllers = [value for value in args.controllers.split(",") if value]
        if tuple(controllers) != CONTROLLERS:
            raise ValueError("controllers differ from the frozen campaign contract")
        _write_campaign(campaign_dir, expand_runs(manifest, seeds, controllers))
    if args.prepare_only:
        return 0
    result = run_pending(campaign_dir, _subprocess_executor)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
