#!/usr/bin/env python3
"""Summarize direct exploratory regime-gated Hai Chau replays.

The gate uses tuned fixed-time in normal/AM and the residual checkpoint in PM.
Seed summaries are compacted from direct gate campaigns. If an older checkout
contains only a PM-only summary for seed 13 or 16, the script retains the
clearly labelled fallback derivation using common deterministic fixed-time
normal/AM totals.
"""

import argparse
import json
import random
import statistics
from pathlib import Path


def _read(path):
    return json.loads(Path(path).read_text())


def _bootstrap(values, repeats, seed):
    rng = random.Random(seed)
    means = sorted(
        statistics.mean(rng.choice(values) for _ in values)
        for _ in range(repeats))
    return [means[int(0.025 * repeats)], means[int(0.975 * repeats) - 1]]


def _fixed_rows(campaign_summary):
    rows = {}
    for record in campaign_summary["runs"]:
        if record.get("returncode") != 0:
            raise ValueError("fixed baseline contains a failed run")
        metrics = record["result"]["metrics"]
        if metrics.get("controller_id") == "tuned_fixed":
            rows[metrics["case_id"]] = metrics
    if not rows:
        raise ValueError("fixed baseline has no tuned_fixed rows")
    return rows


def _seed_result(summary, seed, fixed):
    residual = [row for row in summary["rows"]
                if row.get("controller_id") == "schedule_residual_ddqn"]
    if not residual:
        raise ValueError("seed summary has no residual rows")
    effects = []
    for row in residual:
        base = fixed.get(row["case_id"])
        if base is None or base.get("demand_sha256") != row.get("demand_sha256"):
            raise ValueError("fixed/residual demand hash mismatch: %s" % row["case_id"])
        fixed_seconds = float(base["queue_integral_vehicle_seconds"])
        gated_seconds = float(row["queue_integral_vehicle_seconds"])
        effects.append(100.0 * (fixed_seconds - gated_seconds) / fixed_seconds)
    fixed_by_regime = {}
    for row in fixed.values():
        fixed_by_regime.setdefault(row["regime"], []).append(row)
    full_coverage = len(residual) == 15
    if full_coverage:
        fixed_hours = sum(float(fixed[r["case_id"]]["queue_integral_vehicle_seconds"])
                          for r in residual) / 3600.0
        gated_hours = sum(float(r["queue_integral_vehicle_seconds"])
                          for r in residual) / 3600.0
        coverage = "full_15_cases"
    elif len(residual) == 5 and {r["regime"] for r in residual} == {"pm_peak"}:
        fixed_hours = sum(float(row["queue_integral_vehicle_seconds"])
                          for row in fixed.values()) / 3600.0
        gated_hours = fixed_hours
        for row in residual:
            gated_hours += (float(row["queue_integral_vehicle_seconds"])
                            - float(fixed[row["case_id"]]["queue_integral_vehicle_seconds"])) / 3600.0
        coverage = "pm_5_cases"
    else:
        raise ValueError("seed summary must contain 15 cases or five PM cases")
    pm_fixed = sum(float(row["queue_integral_vehicle_seconds"])
                   for row in fixed_by_regime["pm_peak"])
    pm_gated = sum(float(row["queue_integral_vehicle_seconds"])
                   for row in residual if row["regime"] == "pm_peak")
    return {
        "learning_seed": seed,
        "source_summary": summary.get("profile"),
        "coverage": coverage,
        "case_count": len(residual),
        "case_effects_covered": len(effects),
        "case_level_regressions": sum(value < 0 for value in effects),
        "case_level_improvements": sum(value > 0 for value in effects),
        "case_level_effect_min_pct": min(effects),
        "case_level_effect_max_pct": max(effects),
        "fixed_queue_hours": fixed_hours,
        "gated_queue_hours": gated_hours,
        "derived_full_day_improvement_pct": 100.0 * (fixed_hours - gated_hours) / fixed_hours,
        "pm_improvement_pct": 100.0 * (pm_fixed - pm_gated) / pm_fixed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="results/haichau_network_v2")
    parser.add_argument("--baseline", default="final15-seed12-step8-run2/campaign-summary.json")
    parser.add_argument("--output", default="final15-regime-gated-direct-multi-seed-summary.json")
    parser.add_argument("--bootstrap-repeats", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260913)
    args = parser.parse_args(argv)
    root = Path(args.root)
    baseline = _fixed_rows(_read(root / args.baseline))
    names = {
        12: "final15-regime-gated-seed12-direct-summary.json",
        13: "final15-regime-gated-seed13-full-direct-summary.json",
        14: "final15-regime-gated-seed14-direct-summary.json",
        15: "final15-regime-gated-seed15-direct-summary.json",
        16: "final15-regime-gated-seed16-full-direct-summary.json",
    }
    # Keep backward compatibility with a checkout that has only the earlier
    # PM-only compact summaries. New full summaries are preferred whenever
    # the fresh normal/AM fixed runs are available.
    for seed, fallback in ((13, "final15-regime-gated-seed13-pm-direct-summary.json"),
                           (16, "final15-regime-gated-seed16-pm-direct-summary.json")):
        if not (root / names[seed]).is_file():
            names[seed] = fallback
    results = []
    for seed, name in names.items():
        summary = _read(root / name)
        result = _seed_result(summary, seed, baseline)
        result["source_summary"] = name
        results.append(result)
    values = [row["derived_full_day_improvement_pct"] for row in results]
    output = {
        "schema_version": 1,
        "profile": "exploratory_regime_gated_direct_multi_seed",
        "evidence_namespace": "haichau_network_v2",
        "policy": {"normal": "tuned_fixed", "am_peak": "tuned_fixed",
                   "pm_peak": "schedule_residual_ddqn"},
        "learning_seeds": list(names),
        "seed_results": results,
        "aggregate_across_seed_summaries": {
            "mean_derived_full_day_improvement_pct": statistics.mean(values),
            "min_pct": min(values), "max_pct": max(values),
            "values_pct": values,
            "bootstrap_ci95_pct": _bootstrap(values, args.bootstrap_repeats,
                                               args.bootstrap_seed),
            "bootstrap_repeats": args.bootstrap_repeats,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "interpretation": (
            "Fresh direct evidence for the gate covers all 15 cases for seeds "
            "12, 14, and 15, and the five PM test cases for seeds 13 and 16. "
            "Seeds 13 and 16 use fresh fixed normal/AM replays plus fresh PM gate "
            "replays; older PM-only artifacts remain supported as a fallback. "
            "Case-level effects are computed against the common fresh fixed-time baseline. "
            "This is exploratory evidence outside the frozen strict confirmatory "
            "protocol; it must not be reported as a five-seed strict release."),
    }
    path = root / args.output
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(path), "mean_pct": statistics.mean(values),
                      "ci95_pct": output["aggregate_across_seed_summaries"]["bootstrap_ci95_pct"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
