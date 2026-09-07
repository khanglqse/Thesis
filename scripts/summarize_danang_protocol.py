#!/usr/bin/env python3
"""Create final statistical tables and figures from held-out Da Nang runs."""

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
CONTROLLERS = ("published_fixed", "max_pressure", "hysteretic_mp", "dueling_n3")
SCENARIOS = ("normal", "am_peak", "pm_peak")
METRICS = (
    "queue_integral_vehicle_hours", "arrived", "pending", "completion_rate",
    "final_average_travel_time", "phase_switches",
)


def load_rows():
    rows = {}
    evaluation = PROTOCOL / "evaluation"
    for controller in CONTROLLERS[:-1]:
        rows[controller] = json.loads((evaluation / (controller + ".json")).read_text())
    learning = []
    for seed in (11, 12, 13, 14, 15):
        learning.extend(json.loads(
            (evaluation / ("dueling_n3_seed%d.json" % seed)).read_text()))
    rows["dueling_n3"] = learning
    return rows


def main():
    rows = load_rows()
    summary = {"protocol_id": "danang_observed_camera_v1", "controllers": {},
               "dqn_minus_published_fixed": {}}
    flat = []
    for controller in CONTROLLERS:
        summary["controllers"][controller] = {}
        for scenario in SCENARIOS:
            selected = [row for row in rows[controller] if row["scenario"] == scenario]
            record = {}
            for metric in METRICS:
                record[metric] = summarize_metric(
                    selected, metric, learning_controller=controller == "dueling_n3")
                item = record[metric]
                flat.append({
                    "controller": controller, "scenario": scenario, "metric": metric,
                    "mean": item["mean"], "median": item["median"],
                    "ci95_low": item["bootstrap_ci95"][0],
                    "ci95_high": item["bootstrap_ci95"][1],
                    "n_independent": item["n_independent"],
                })
            record["collisions_total"] = sum(row["collisions"] for row in selected)
            record["emergency_braking_total"] = sum(
                row["emergency_braking"] for row in selected)
            summary["controllers"][controller][scenario] = record

    for scenario in SCENARIOS:
        learning = [row for row in rows["dueling_n3"] if row["scenario"] == scenario]
        baseline = [row for row in rows["published_fixed"]
                    if row["scenario"] == scenario]
        summary["dqn_minus_published_fixed"][scenario] = paired_effect(
            learning, baseline, "queue_integral_vehicle_hours")

    output = PROTOCOL / "summary"
    output.mkdir(parents=True, exist_ok=True)
    (output / "final-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with (output / "final-summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=flat[0].keys())
        writer.writeheader()
        writer.writerows(flat)

    labels = {"published_fixed": "Published fixed", "max_pressure": "Max-Pressure",
              "hysteretic_mp": "Hysteretic MP", "dueling_n3": "Dueling DDQN"}
    x = np.arange(len(SCENARIOS)); width = 0.19
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for index, controller in enumerate(CONTROLLERS):
        values, low, high = [], [], []
        for scenario in SCENARIOS:
            item = summary["controllers"][controller][scenario][
                "queue_integral_vehicle_hours"]
            values.append(item["mean"]); low.append(item["mean"] - item["bootstrap_ci95"][0])
            high.append(item["bootstrap_ci95"][1] - item["mean"])
        ax.bar(x + (index - 1.5) * width, values, width, label=labels[controller],
               yerr=np.asarray([low, high]), capsize=3)
    ax.set_xticks(x, ["Normal 13:00", "AM peak 08:00", "PM peak 17:00"])
    ax.set_ylabel("Stopped + pending queue integral (vehicle-hours)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output / "controller-comparison.pdf")
    fig.savefig(output / "controller-comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.6))
    for seed in (11, 12, 13, 14, 15):
        log = json.loads((PROTOCOL / "training" /
                         ("dueling_n3_seed%d" % seed) / "train-log.json").read_text())
        points = [(row["episode"] + 1, row["greedy_eval_queue"])
                  for row in log["episodes"] if "greedy_eval_queue" in row]
        ax.plot([point[0] for point in points], [point[1] for point in points],
                marker="o", alpha=0.75, label="seed %d" % seed)
    ax.set_xlabel("Training episode")
    ax.set_ylabel("Full-hour validation mean queue (vehicles)")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(output / "validation-learning-curves.pdf")
    fig.savefig(output / "validation-learning-curves.png", dpi=180)
    plt.close(fig)
    print(output / "final-summary.json")


if __name__ == "__main__":
    main()
