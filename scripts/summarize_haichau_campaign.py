#!/usr/bin/env python3
"""Build frozen JSON/CSV summaries from verified fresh run bundles."""

import argparse
import csv
import json
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance


def _load_runs(campaign_dir):
    verify_campaign(
        campaign_dir, require_release_provenance=True,
        project_root=Path(__file__).resolve().parent.parent)
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
    parser.add_argument(
        "--protocol", default="results/haichau_network_v2/final/frozen-protocol.json")
    args = parser.parse_args(argv)
    campaign_dir = Path(args.campaign_dir)
    protocol = json.loads(Path(args.protocol).read_text())
    rules = protocol.get("acceptance_rules", {})
    summary = aggregate_campaign(
        _load_runs(campaign_dir),
        required_learning_seeds=rules.get("required_learning_seeds"),
        required_regimes=rules.get("required_regimes", ("normal", "am_peak", "pm_peak")),
        minimum_learning_seeds=rules.get("minimum_learning_seeds", 5),
        minimum_demand_units=rules.get("minimum_demand_units", 1),
        normal_point_limit=rules.get("normal_point_limit", 0.0),
        normal_ci_margin_fraction=rules.get("normal_ci_margin_fraction", 0.05),
        peak_ci_upper_limit=rules.get("peak_ci_upper_limit", 0.0),
        completion_degradation_limit=rules.get(
            "completion_degradation_limit", 0.02),
    )
    document = {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": (
                "synthetic network demand constrained by Da Nang evidence"),
            "evidence_namespace": "haichau_network_v2",
        },
        "summary": summary,
        "acceptance": evaluate_acceptance(summary),
    }
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
