#!/usr/bin/env python3
"""Summarize a preregisterable regime-gated residual policy.

The policy keeps tuned fixed-time in normal and AM-peak demand and uses the
already-evaluated residual controller in PM-peak demand.  This is a matched
counterfactual composition of completed paired rows, not a replacement for a
fresh strict campaign.  It is useful for diagnosing whether a demand gate
removes the AM-regime failure mode before spending another full campaign.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path


DEFAULT_INPUTS = {
    12: "results/haichau_network_v2/final15-seed12-step8-summary.json",
    14: "results/haichau_network_v2/final15-seed14-step4-summary.json",
    15: "results/haichau_network_v2/final15-seed15-step8-summary.json",
}


def _read(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or not isinstance(value.get("rows"), list):
        raise ValueError("summary must contain a rows list: %s" % path)
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percent(fixed, candidate):
    return 100.0 * (fixed - candidate) / fixed if fixed else 0.0


def summarize(inputs):
    seeds = {}
    all_rows = []
    for seed, path in sorted(inputs.items()):
        source = _read(path)
        rows = []
        for row in source["rows"]:
            regime = row["regime"]
            fixed = float(row["fixed_queue_hours"])
            residual = float(row["residual_queue_hours"])
            # Normal and AM remain on the fixed plan.  PM uses the residual.
            gated = residual if regime == "pm_peak" else fixed
            rows.append({
                "case_id": row["case_id"],
                "regime": regime,
                "fixed_queue_hours": fixed,
                "residual_queue_hours": residual,
                "gated_queue_hours": gated,
                "gated_improvement_pct": _percent(fixed, gated),
            })
        fixed_total = sum(row["fixed_queue_hours"] for row in rows)
        gated_total = sum(row["gated_queue_hours"] for row in rows)
        seed_record = {
            "seed": seed,
            "source_summary": str(path),
            "case_count": len(rows),
            "fixed_queue_hours": fixed_total,
            "gated_queue_hours": gated_total,
            "improvement_pct": _percent(fixed_total, gated_total),
            "by_regime": {},
        }
        for regime in ("normal", "am_peak", "pm_peak"):
            selected = [row for row in rows if row["regime"] == regime]
            fixed = sum(row["fixed_queue_hours"] for row in selected)
            gated = sum(row["gated_queue_hours"] for row in selected)
            seed_record["by_regime"][regime] = {
                "n": len(selected),
                "fixed_queue_hours": fixed,
                "gated_queue_hours": gated,
                "improvement_pct": _percent(fixed, gated),
            }
        seeds[str(seed)] = seed_record
        for row in rows:
            enriched = dict(row)
            enriched["seed"] = seed
            all_rows.append(enriched)

    effects = [row["gated_improvement_pct"] for row in all_rows]
    fixed_total = sum(row["fixed_queue_hours"] for row in all_rows)
    gated_total = sum(row["gated_queue_hours"] for row in all_rows)
    bootstrap = []
    rng = random.Random(20260913)
    for _ in range(10000):
        sample = [effects[rng.randrange(len(effects))] for _ in effects]
        bootstrap.append(sum(sample) / len(sample))
    bootstrap.sort()
    seed_effects = [record["improvement_pct"] for record in seeds.values()]
    seed_bootstrap = []
    for _ in range(10000):
        sample = [seed_effects[rng.randrange(len(seed_effects))] for _ in seed_effects]
        seed_bootstrap.append(sum(sample) / len(sample))
    seed_bootstrap.sort()
    return {
        "schema_version": 1,
        "analysis": "regime_gated_counterfactual",
        "policy": {
            "normal": "tuned_fixed",
            "am_peak": "tuned_fixed",
            "pm_peak": "schedule_residual_ddqn",
        },
        "source_protocol": "matched_15_case_rows_per_seed",
        "interpretation": (
            "Exploratory composition of completed paired rows; a fresh gated "
            "campaign is required before strict confirmatory claims."),
        "seeds": seeds,
        "source_files": {
            str(seed): {"path": str(path), "sha256": _sha256(path)}
            for seed, path in sorted(inputs.items())
        },
        "rows": all_rows,
        "aggregate": {
            "seed_count": len(seeds),
            "case_count": len(all_rows),
            "fixed_queue_hours": fixed_total,
            "gated_queue_hours": gated_total,
            "improvement_pct": _percent(fixed_total, gated_total),
            "case_effect_mean_pct": sum(effects) / len(effects) if effects else 0.0,
            "case_effect_min_pct": min(effects) if effects else 0.0,
            "case_effect_max_pct": max(effects) if effects else 0.0,
            "case_effect_bootstrap_ci95_pct": {
                "lower": bootstrap[int(0.025 * len(bootstrap))] if bootstrap else 0.0,
                "upper": bootstrap[int(0.975 * len(bootstrap)) - 1] if bootstrap else 0.0,
                "seed": 20260913,
                "repeats": 10000,
            },
            "seed_effect_mean_pct": sum(seed_effects) / len(seed_effects) if seed_effects else 0.0,
            "seed_effect_bootstrap_ci95_pct": {
                "lower": seed_bootstrap[int(0.025 * len(seed_bootstrap))] if seed_bootstrap else 0.0,
                "upper": seed_bootstrap[int(0.975 * len(seed_bootstrap)) - 1] if seed_bootstrap else 0.0,
                "seed": 20260913,
                "repeats": 10000,
            },
        },
        "by_regime": {
            regime: {
                "fixed_queue_hours": sum(row["fixed_queue_hours"] for row in all_rows
                                          if row["regime"] == regime),
                "gated_queue_hours": sum(row["gated_queue_hours"] for row in all_rows
                                          if row["regime"] == regime),
                "improvement_pct": _percent(
                    sum(row["fixed_queue_hours"] for row in all_rows if row["regime"] == regime),
                    sum(row["gated_queue_hours"] for row in all_rows if row["regime"] == regime)),
                "case_count": sum(row["regime"] == regime for row in all_rows),
            }
            for regime in ("normal", "am_peak", "pm_peak")
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/haichau_network_v2/final15-regime-gated-summary.json")
    args = parser.parse_args(argv)
    result = summarize({seed: Path(path) for seed, path in DEFAULT_INPUTS.items()})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "aggregate": result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
