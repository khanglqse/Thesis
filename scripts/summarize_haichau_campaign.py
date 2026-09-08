#!/usr/bin/env python3
"""Build frozen JSON/CSV summaries from verified fresh run bundles."""

import argparse
import csv
import json
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance


def _load_runs(campaign_dir):
    verify_campaign(campaign_dir)
    manifest = json.loads((campaign_dir / "campaign-manifest.json").read_text())
    rows = []
    for run in manifest["runs"]:
        run_dir = campaign_dir / "runs" / run["run_id"]
        metrics = json.loads((run_dir / "metrics.json").read_text())
        row = dict(run)
        row.update(metrics)
        rows.append(row)
    return rows


def _csv_rows(summary):
    for controller, regimes in sorted(summary.items()):
        if controller.startswith("_"):
            continue
        for regime, result in sorted(regimes.items()):
            effect = result.get("queue_difference_vs_tuned_fixed", {})
            yield {
                "controller_id": controller,
                "regime": regime,
                "n_independent": result["n_independent"],
                "statistical_unit": result["statistical_unit"],
                "queue_mean_vehicle_seconds": result["queue"]["mean"],
                "queue_difference_mean": effect.get("mean", ""),
                "queue_difference_ci95_low": effect.get("bootstrap_ci95", ["", ""])[0],
                "queue_difference_ci95_high": effect.get("bootstrap_ci95", ["", ""])[1],
                "completion_rate_mean": result["completion_rate"]["mean"],
            }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", default="results/haichau_network_v2/final")
    args = parser.parse_args(argv)
    campaign_dir = Path(args.campaign_dir)
    summary = aggregate_campaign(_load_runs(campaign_dir))
    document = {"summary": summary, "acceptance": evaluate_acceptance(summary)}
    (campaign_dir / "summary.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n")
    fieldnames = [
        "controller_id", "regime", "n_independent", "statistical_unit",
        "queue_mean_vehicle_seconds", "queue_difference_mean",
        "queue_difference_ci95_low", "queue_difference_ci95_high",
        "completion_rate_mean",
    ]
    with (campaign_dir / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_csv_rows(summary))
    print(json.dumps(document["acceptance"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
