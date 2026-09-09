#!/usr/bin/env python3
"""Verify and summarize the V3 exploratory robustness appendix."""

import argparse
import hashlib
import json
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign
from traffic_rl.eval.robustness_appendix import (
    expand_robustness_runs, summarize_robustness,
    validate_robustness_directory, write_robustness_summary,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(campaign_dir, runs):
    rows = []
    for run in runs:
        path = Path(campaign_dir) / "runs" / run["run_id"] / "metrics.json"
        metrics = json.loads(path.read_text())
        if metrics.get("condition_id") != run["condition_id"] \
                or metrics.get("study_role") != "exploratory_appendix" \
                or metrics.get("fresh_evaluation") is not True:
            raise ValueError("robustness metric scope/provenance differs from run")
        row = dict(run)
        row.update(metrics)
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir",
                        default="results/haichau_network_v2/robustness")
    parser.add_argument("--protocol", default=(
        "results/haichau_network_v2/robustness/"
        "frozen-robustness-protocol.json"))
    args = parser.parse_args(argv)
    campaign_dir = validate_robustness_directory(
        PROJECT_ROOT, Path(args.campaign_dir))
    protocol_path = Path(args.protocol)
    if not protocol_path.is_absolute():
        protocol_path = PROJECT_ROOT / protocol_path
    protocol = json.loads(protocol_path.read_text())
    runs = expand_robustness_runs(PROJECT_ROOT, protocol)
    campaign = json.loads((campaign_dir / "campaign-manifest.json").read_text())
    if campaign.get("runs") != runs or campaign.get("episode_count") != 420:
        raise ValueError("robustness campaign differs from frozen protocol")
    verify_campaign(campaign_dir, require_release_provenance=True,
                    project_root=PROJECT_ROOT)
    summary = summarize_robustness(load_rows(campaign_dir, runs))
    summary["provenance"] = {
        "frozen_robustness_protocol_sha256": _sha256(protocol_path),
        "campaign_manifest_sha256": _sha256(
            campaign_dir / "campaign-manifest.json"),
        "verified_fresh_episodes": 420,
    }
    write_robustness_summary(campaign_dir, summary)
    print(json.dumps({"episodes": 420,
                      "study_role": "exploratory_appendix"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
