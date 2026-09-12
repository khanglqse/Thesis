#!/usr/bin/env python3
"""Summarize one or more exploratory Hai Chau campaign directories."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
from statistics import mean, median


def bootstrap_ci(values, repeats=10000, seed=20260913):
    rng = random.Random(seed)
    samples = []
    values = list(values)
    for _ in range(repeats):
        samples.append(mean(rng.choice(values) for _ in values))
    samples.sort()
    return {"lower_95_pct": samples[int(0.025 * repeats)],
            "upper_95_pct": samples[int(0.975 * repeats) - 1],
            "repeats": repeats, "seed": seed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaigns", nargs="+", help="campaign directories")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    cases = {}
    horizons = set()
    for name in args.campaigns:
        summary = json.loads((Path(name) / "campaign-summary.json").read_text())
        horizons.add(summary.get("horizon_seconds"))
        for record in summary["runs"]:
            if record.get("returncode") != 0:
                raise ValueError("campaign contains a failed run: %s" % record["run_id"])
            metrics = record["result"]["metrics"]
            controller = record["run_id"].split("__", 1)[0]
            cases.setdefault(metrics["case_id"], {})[controller] = metrics
    if horizons != {3600}:
        raise ValueError("summary is intended for full-hour comparisons")
    rows = []
    by_regime = defaultdict(list)
    for case_id, values in sorted(cases.items()):
        if set(values) != {"tuned_fixed", "schedule_residual_ddqn"}:
            continue
        fixed = values["tuned_fixed"]
        residual = values["schedule_residual_ddqn"]
        base = float(fixed["queue_integral_vehicle_hours"])
        candidate = float(residual["queue_integral_vehicle_hours"])
        improvement = 100.0 * (base - candidate) / base
        by_regime[fixed["regime"]].append(improvement)
        rows.append({"case_id": case_id, "regime": fixed["regime"],
                     "fixed_queue_hours": base, "residual_queue_hours": candidate,
                     "improvement_pct": improvement,
                     "fixed_completion_rate": fixed["completion_rate"],
                     "residual_completion_rate": residual["completion_rate"]})
    if not rows:
        raise ValueError("no matched fixed/residual cases")
    fixed_total = sum(row["fixed_queue_hours"] for row in rows)
    residual_total = sum(row["residual_queue_hours"] for row in rows)
    output = {"schema_version": 1, "profile": "exploratory_short_full_hour",
              "horizon_seconds": 3600, "case_count": len(rows), "rows": rows,
              "aggregate": {"fixed_queue_hours": fixed_total,
                             "residual_queue_hours": residual_total,
                             "improvement_pct": 100.0 * (fixed_total - residual_total) / fixed_total},
              "paired_bootstrap_ci_pct": bootstrap_ci(
                  [row["improvement_pct"] for row in rows]),
              "by_regime": {regime: {"n": len(values), "mean_improvement_pct": mean(values),
                                     "median_improvement_pct": median(values),
                                     "min_improvement_pct": min(values),
                                     "max_improvement_pct": max(values),
                                     "paired_bootstrap_ci_pct": bootstrap_ci(values)}
                            for regime, values in sorted(by_regime.items())},
              "interpretation": "aggregate comparison only; not a replacement for frozen release campaign"}
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_count": len(rows), "aggregate_improvement_pct":
                      output["aggregate"]["improvement_pct"], "output": args.output}, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
