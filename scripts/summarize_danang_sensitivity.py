#!/usr/bin/env python3
"""Summarize synthetic demand-scale sensitivity without pseudoreplication."""

import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.report.danang import paired_effect, summarize_metric


PROTOCOL = ROOT / "results/danang_protocol_v1"
SENSITIVITY = PROTOCOL / "sensitivity"
SCALES = (0.75, 1.0, 1.25, 1.5)
METRIC = "queue_integral_vehicle_hours"


def load_rows():
    fixed = json.loads((SENSITIVITY / "published_fixed.json").read_text())
    dqn = []
    for seed in (11, 12, 13, 14, 15):
        dqn.extend(json.loads(
            (SENSITIVITY / ("dueling_n3_seed%d.json" % seed)).read_text()))
    return fixed, dqn


def main():
    fixed, dqn = load_rows()
    summary = {
        "protocol_id": "danang_observed_camera_v1_synthetic_scale_sensitivity",
        "warning": "Scaled demand is synthetic; scale 1.0 is the observed AM camera profile.",
        "metric": METRIC,
        "scales": {},
    }
    csv_rows = []
    for scale in SCALES:
        baseline_rows = [row for row in fixed if float(row["scale"]) == scale]
        learning_rows = [row for row in dqn if float(row["scale"]) == scale]
        fixed_stats = summarize_metric(baseline_rows, METRIC)
        dqn_stats = summarize_metric(learning_rows, METRIC, learning_controller=True)
        effect = paired_effect(learning_rows, baseline_rows, METRIC)
        record = {
            "scheduled_vehicles": baseline_rows[0]["scheduled"],
            "published_fixed": fixed_stats,
            "dueling_n3": dqn_stats,
            "dqn_minus_published_fixed": effect,
            "collisions_total": sum(row["collisions"] for row in baseline_rows + learning_rows),
            "emergency_braking_total": sum(
                row["emergency_braking"] for row in baseline_rows + learning_rows),
        }
        summary["scales"][str(scale)] = record
        for controller, stats in (("published_fixed", fixed_stats), ("dueling_n3", dqn_stats)):
            csv_rows.append({
                "scale": scale,
                "scheduled_vehicles": record["scheduled_vehicles"],
                "controller": controller,
                "mean_vehicle_hours": stats["mean"],
                "ci95_low": stats["bootstrap_ci95"][0],
                "ci95_high": stats["bootstrap_ci95"][1],
                "n_independent": stats["n_independent"],
            })

    output = PROTOCOL / "summary"
    output.mkdir(parents=True, exist_ok=True)
    (output / "sensitivity-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with (output / "sensitivity-summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_rows[0].keys())
        writer.writeheader()
        writer.writerows(csv_rows)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for controller, label, color in (
            ("published_fixed", "Published fixed", "#48566a"),
            ("dueling_n3", "Dueling DDQN", "#d1495b")):
        means, lows, highs = [], [], []
        for scale in SCALES:
            stats = summary["scales"][str(scale)][controller]
            means.append(stats["mean"])
            lows.append(stats["mean"] - stats["bootstrap_ci95"][0])
            highs.append(stats["bootstrap_ci95"][1] - stats["mean"])
        ax.errorbar(SCALES, means, yerr=np.asarray([lows, highs]), marker="o",
                    linewidth=2, capsize=4, label=label, color=color)
    ax.axvline(1.0, color="#2a9d8f", linestyle="--", alpha=0.8,
               label="Observed AM profile")
    ax.set_xticks(SCALES, ["0.75×", "1.00×", "1.25×", "1.50×"])
    ax.set_xlabel("Synthetic multiplier applied to observed AM demand")
    ax.set_ylabel("Stopped + pending queue integral (vehicle-hours)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "demand-sensitivity.pdf")
    fig.savefig(output / "demand-sensitivity.png", dpi=180)
    plt.close(fig)
    print(output / "sensitivity-summary.json")


if __name__ == "__main__":
    main()
