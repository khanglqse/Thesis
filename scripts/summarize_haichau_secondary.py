#!/usr/bin/env python3
"""Summarize secondary outcomes for the bounded Hai Chau matrix.

The script consumes only completed, matched campaign summaries.  It does not
open a demand file or launch a simulator, and it keeps the queue objective and
operational secondary outcomes in separate fields.
"""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LEARNED = "schedule_residual_ddqn"
FIXED = "tuned_fixed"


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _load_campaign(path):
    data = json.loads(Path(path).read_text())
    rows = {}
    for item in data.get("runs", []):
        if item.get("returncode", 0) != 0:
            continue
        result = item.get("result", {})
        metrics = result.get("metrics", {})
        key = (metrics.get("case_id"), metrics.get("controller_id"))
        if key in rows:
            raise ValueError("duplicate completed row: %s" % (key,))
        rows[key] = metrics
    return data, rows


def _scalar(metrics):
    per_node = metrics.get("per_node_max_queue") or {}
    spillback = metrics.get("spillback_lane_seconds") or {}
    return {
        "queue_integral_vehicle_hours": float(metrics["queue_integral_vehicle_hours"]),
        "completion_rate": float(metrics["completion_rate"]),
        "insertion_rate": float(metrics["insertion_rate"]),
        "travel_time_completed_mean_seconds": float(metrics["travel_time_completed_mean"]),
        "phase_switches": float(metrics["phase_switches"]),
        "intergreen_seconds": float(metrics["intergreen_seconds"]),
        "max_node_queue": float(max(per_node.values()) if per_node else 0.0),
        "spillback_lane_seconds": float(sum(spillback.values())),
    }


def summarize(learned_path, fixed_path):
    learned_campaign, learned_rows = _load_campaign(learned_path)
    fixed_campaign, fixed_rows = _load_campaign(fixed_path)
    case_ids = sorted(case for case, controller in learned_rows if controller == LEARNED)
    if len(case_ids) != 15 or len(set(case_ids)) != 15:
        raise ValueError("learned campaign must contain exactly 15 cases")
    paired = []
    for case_id in case_ids:
        learned = learned_rows.get((case_id, LEARNED))
        fixed = fixed_rows.get((case_id, FIXED))
        if learned is None or fixed is None:
            raise ValueError("missing matched fixed/learned row: %s" % case_id)
        if learned.get("regime") != fixed.get("regime"):
            raise ValueError("regime mismatch: %s" % case_id)
        l, f = _scalar(learned), _scalar(fixed)
        paired.append({
            "case_id": case_id,
            "regime": learned["regime"],
            "learned": l,
            "fixed": f,
            "queue_reduction_percent": (f["queue_integral_vehicle_hours"] - l["queue_integral_vehicle_hours"])
                / f["queue_integral_vehicle_hours"] * 100.0,
            "completion_difference_percentage_points": (l["completion_rate"] - f["completion_rate"]) * 100.0,
            "insertion_difference_percentage_points": (l["insertion_rate"] - f["insertion_rate"]) * 100.0,
        })
    metrics = list(paired[0]["learned"])
    deltas = {}
    for name in metrics:
        l_mean = sum(row["learned"][name] for row in paired) / len(paired)
        f_mean = sum(row["fixed"][name] for row in paired) / len(paired)
        deltas[name] = {
            "fixed_mean": f_mean,
            "learned_mean": l_mean,
            "learned_minus_fixed": l_mean - f_mean,
        }
    by_regime = {}
    for regime in ("normal", "am_peak", "pm_peak"):
        subset = [row for row in paired if row["regime"] == regime]
        if len(subset) != 5:
            raise ValueError("regime %s must contain five cases" % regime)
        by_regime[regime] = {
            "cases": [row["case_id"] for row in subset],
            "queue_reduction_percent_mean": sum(row["queue_reduction_percent"] for row in subset) / 5.0,
            "completion_difference_percentage_points_mean": sum(row["completion_difference_percentage_points"] for row in subset) / 5.0,
            "insertion_difference_percentage_points_mean": sum(row["insertion_difference_percentage_points"] for row in subset) / 5.0,
            "phase_switches_learned_mean": sum(row["learned"]["phase_switches"] for row in subset) / 5.0,
            "phase_switches_fixed_mean": sum(row["fixed"]["phase_switches"] for row in subset) / 5.0,
            "spillback_lane_seconds_learned_mean": sum(row["learned"]["spillback_lane_seconds"] for row in subset) / 5.0,
            "spillback_lane_seconds_fixed_mean": sum(row["fixed"]["spillback_lane_seconds"] for row in subset) / 5.0,
        }
    return {
        "schema_version": 1,
        "evidence_scope": "bounded_15_case_matrix_seed14_step4",
        "controller_pair": {"learned": LEARNED, "fixed": FIXED},
        "horizon_seconds": learned_campaign.get("horizon_seconds"),
        "case_count": len(paired),
        "campaign_inputs": {
            "learned": {"path": str(Path(learned_path).resolve().relative_to(ROOT)), "sha256": _sha256(learned_path)},
            "fixed": {"path": str(Path(fixed_path).resolve().relative_to(ROOT)), "sha256": _sha256(fixed_path)},
        },
        "overall": deltas,
        "by_regime": by_regime,
        "paired_cases": paired,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learned", default="results/haichau_network_v2/final15-seed14-step4-residual/campaign-summary.json")
    parser.add_argument("--fixed", default="results/haichau_network_v2/final15-baselines-run2/campaign-summary.json")
    parser.add_argument("--output", default="results/haichau_network_v2/final15-seed14-secondary-summary.json")
    args = parser.parse_args(argv)
    value = summarize(ROOT / args.learned, ROOT / args.fixed)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "cases": value["case_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
