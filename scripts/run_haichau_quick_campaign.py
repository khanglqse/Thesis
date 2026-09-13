#!/usr/bin/env python3
"""Run a small, short-horizon Hai Chau comparison for iteration/demo use.

This campaign intentionally lives outside the frozen release runner.  It keeps
one test realization per time-of-day regime, truncates demand at the simulator
minimum macro horizon (300 s), and compares fixed-time, max-pressure, and one
quick residual checkpoint.  The output is exploratory evidence and must not be
used to replace the full 15-case release campaign.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
IMAGE = "traffic-rl-cityflow-research@sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"
REGIMES = ("normal", "am_peak", "pm_peak")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def scheduled(row):
    return 1 + int((int(row["endTime"]) - int(row["startTime"]))
                   // float(row["interval"]))


def short_flow(source, target, horizon):
    rows = json.loads(Path(source).read_text())
    kept = []
    count = 0
    for row in rows:
        if int(row["startTime"]) >= horizon:
            continue
        clipped = dict(row)
        clipped["endTime"] = min(int(row["endTime"]), horizon - 1)
        if clipped["endTime"] < int(clipped["startTime"]):
            continue
        kept.append(clipped)
        count += scheduled(clipped)
    if not kept or count <= 0:
        raise ValueError("short flow has no vehicles: %s" % source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(kept, indent=2, sort_keys=True) + "\n")
    return count


def run_one(root, run, output):
    run_dir = output / "runs" / run["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = run_dir / "run-manifest.json"
    manifest.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    runtime_dir = run_dir / "runtime"
    cmd = ["docker", "run", "--rm", "--platform", "linux/amd64",
           "-v", "%s:/work" % root, "-w", "/work", IMAGE,
           "python3", "scripts/evaluate_haichau_network.py",
           "--run-manifest", "/work/" + str(manifest.relative_to(root)),
           "--runtime-dir", "/work/" + str(runtime_dir.relative_to(root))]
    completed = subprocess.run(cmd, cwd=str(root), text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record = {"run_id": run["run_id"], "returncode": completed.returncode,
              "stdout": completed.stdout, "stderr": completed.stderr}
    (run_dir / "stdout.log").write_text(completed.stdout)
    (run_dir / "stderr.log").write_text(completed.stderr)
    if completed.returncode == 0:
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        record["result"] = json.loads(lines[-1])
        (run_dir / "result.json").write_text(
            json.dumps(record["result"], indent=2, sort_keys=True) + "\n")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="results/haichau_network_v2/quick-campaign")
    parser.add_argument("--seed", type=int, default=12)
    parser.add_argument("--horizon", type=int, default=300,
                        help="simulation horizon in seconds; must be a multiple of 300")
    parser.add_argument("--controllers", default="tuned_fixed,max_pressure,schedule_residual_ddqn")
    parser.add_argument("--margin", type=float, default=0.0,
                        help="residual score margin for exploratory safety fallback")
    parser.add_argument("--regime-gated", action="store_true",
                        help="exploratory policy: fixed in normal/AM, residual in PM")
    parser.add_argument("--cases-per-regime", type=int, default=1,
                        help="number of test demand realizations per regime")
    parser.add_argument("--demand-seeds", default=None,
                        help="optional comma-separated demand seeds to include")
    parser.add_argument("--checkpoint-root", default=None,
                        help="checkpoint step directory containing contract.json and weights.npz")
    args = parser.parse_args(argv)
    if args.horizon <= 0 or args.horizon % 300:
        parser.error("--horizon must be a positive multiple of 300")
    controllers = tuple(value for value in args.controllers.split(",") if value)
    allowed_controllers = {"tuned_fixed", "max_pressure", "hysteretic_mp", "schedule_residual_ddqn"}
    if not controllers or set(controllers) - allowed_controllers:
        parser.error("--controllers contains an unknown or empty controller")
    if args.cases_per_regime <= 0:
        parser.error("--cases-per-regime must be positive")
    if args.margin < 0:
        parser.error("--margin must be nonnegative")
    requested_seeds = (None if args.demand_seeds is None else
                       {int(value) for value in args.demand_seeds.split(",") if value})
    root = Path(args.root).resolve()
    output = (root / args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("quick campaign output already exists: %s" % output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / "results/haichau_network_v2/experiment-manifest.json").read_text())
    cases = {}
    for regime in REGIMES:
        candidates = sorted((case for case in manifest["cases"]
                             if case.get("split") == "test"
                             and case.get("operational_time_of_day") == regime),
                            key=lambda case: (case.get("demand_seed"), case.get("case_id")))
        if requested_seeds is not None:
            candidates = [case for case in candidates if case.get("demand_seed") in requested_seeds]
        cases[regime] = candidates[:args.cases_per_regime]
    if any(not cases[regime] for regime in REGIMES):
        raise ValueError("test manifest lacks a regime")
    quick_checkpoint = (Path(args.checkpoint_root).resolve() if args.checkpoint_root
                        else root / ("results/haichau_network_v2/training/"
                                     "quick300-seed%d/checkpoints/step-0001" % args.seed))
    contract = json.loads((quick_checkpoint / "contract.json").read_text())
    base_config = {
        "network_path": manifest["network"]["path"],
        "phase_contract_path": manifest["phase_contract"]["path"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "simulation": manifest["simulation"],
        "normalization": contract["normalization"],
        "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.0,
                    "switch_penalty": 0.0},
        "spillback_queue_threshold": contract["normalization"]["capacity_norm"],
        "safety": {"min_score_margin": args.margin},
    }
    root_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                           text=True).strip()
    runtime = manifest["runtime"]
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", IMAGE, "-f", "{{.Id}}"],
        text=True).strip()
    runs = []
    for regime in REGIMES:
        for case in cases[regime]:
            flow_target = output / "demands" / (case["case_id"] + "_%ds.json" % args.horizon)
            vehicle_count = short_flow(root / case["flow_path"], flow_target, args.horizon)
            demand_rel = str(flow_target.relative_to(root))
            for controller in controllers:
                learning_seed = args.seed if controller == "schedule_residual_ddqn" else None
                config = dict(base_config)
                if controller == "tuned_fixed":
                    config["green_duration"] = 25
                elif controller == "hysteretic_mp":
                    config["min_hold_decisions"] = 3
                else:
                    config.update({"macro": contract["macro"],
                                   "operational_mode": {
                                       "input": "declared_time_of_day",
                                       "normal": "exact_executed_fixed25_from_reset",
                                       "peaks": "raw_greedy_prevalidated_macro",
                                       "forbidden_features": ["case_id", "learning_seed",
                                           "demand_seed", "simulator_seed", "filename",
                                           "future_flow"]},
                                   "critic_units": contract["critic_units"]})
                    if args.regime_gated and controller == "schedule_residual_ddqn":
                        config["regime_gate"] = {
                            "normal": "fixed", "am_peak": "fixed",
                            "pm_peak": "residual"}
                run_id = "%s__%s__%ds" % (controller, case["case_id"], args.horizon)
                run = {
                    "run_id": run_id, "case_id": case["case_id"], "regime": regime,
                    "controller_id": controller, "learning_seed": learning_seed,
                    "demand_seed": case["demand_seed"], "simulator_seed": case["sim_seed"],
                    "scheduled_vehicles": vehicle_count, "horizon_steps": args.horizon,
                    "network_sha256": manifest["network"]["sha256"],
                    "viewer_network_sha256": manifest["network"]["sha256"],
                    "demand_sha256": sha256(flow_target), "demand_path": demand_rel,
                    "runtime_digest": IMAGE.split("@", 1)[1], "runtime_image": IMAGE,
                    "runtime_image_id": image_id,
                    "runtime_dockerfile_path": runtime["dockerfile"]["path"],
                    "runtime_dockerfile_sha256": runtime["dockerfile"]["sha256"],
                    "code_commit": root_commit, "evidence_namespace": "haichau_network_v2_quick",
                    "fresh_evaluation": True, "controlled_signals": manifest["network"]["controlled_signals"],
                    "agent_ids": manifest["network"]["agent_ids"], "resolved_config": config,
                }
                if controller == "schedule_residual_ddqn":
                    weights = quick_checkpoint / "weights.npz"
                    run.update({"checkpoint_path": str(weights.relative_to(root)),
                                "checkpoint_sha256": sha256(weights),
                                "checkpoint_contract": contract,
                                "checkpoint_contract_sha256": canonical_sha256(contract)})
                runs.append(run)
    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_one, root, run, output) for run in runs]
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda item: item["run_id"])
    (output / "campaign-summary.json").write_text(
                    json.dumps({"profile": "exploratory_short", "horizon_seconds": args.horizon,
                    "regimes": REGIMES, "controllers": controllers, "runs": records},
                   indent=2, sort_keys=True) + "\n")
    failures = sum(record["returncode"] != 0 for record in records)
    print(json.dumps({"complete": len(records) - failures, "failed": failures,
                      "total": len(records), "output": str(output)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
