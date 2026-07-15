#!/usr/bin/env python3
"""Aggregate tier-2 multi-seed results into mean/std/95%-CI per controller.

Runs on the HOST (needs numpy). Reads results/<scen>/exp_ms*/comparison.json
(one per seed; the DQN row varies by training seed, baselines are identical),
writes results/multiseed/<scen>.json and prints a summary.

  PYTHONPATH=src python3 scripts/aggregate_multiseed.py haichau_rush
"""
import json
import sys
from pathlib import Path

from traffic_rl.eval.multiseed import aggregate_seeds

ROOT = Path(__file__).resolve().parent.parent


def main():
    scen = sys.argv[1] if len(sys.argv) > 1 else "haichau_rush"
    base = ROOT / "results" / scen
    paths = sorted(base.glob("exp_ms*/comparison.json"),
                   key=lambda p: int(p.parent.name.replace("exp_ms", "")))
    if not paths:
        print("no exp_ms*/comparison.json under", base)
        return 1
    per_seed_rows = [json.loads(p.read_text())["table"] for p in paths]
    agg = aggregate_seeds(per_seed_rows)

    out_dir = ROOT / "results" / "multiseed"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"scenario": scen, "n_seeds": len(per_seed_rows), "aggregate": agg}
    (out_dir / (scen + ".json")).write_text(json.dumps(payload, indent=2))

    fixed_wait = agg.get("FixedTime", {}).get("wait_hours", {}).get("mean")
    print("=== %s  (n=%d seeds) ===" % (scen, len(per_seed_rows)))
    for ctrl in ("FixedTime", "Random", "MaxPressure", "DQN"):
        if ctrl not in agg:
            continue
        q = agg[ctrl]["mean_total_queue"]
        w = agg[ctrl]["wait_hours"]
        vs = ""
        if fixed_wait and ctrl != "FixedTime":
            vs = "  vsFixed=%+.1f%%" % (100.0 * (fixed_wait - w["mean"]) / fixed_wait)
        print("  %-12s queue=%.1f±%.1f  wait_h=%.1f±%.1f (CI95=%.1f)%s" % (
            ctrl, q["mean"], q["std"], w["mean"], w["std"], w["ci95"], vs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
