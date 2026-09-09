#!/usr/bin/env python3
"""Prepare, execute, resume, or verify the frozen V3 robustness campaign."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.network_campaign import run_pending, verify_campaign
from traffic_rl.eval.robustness_appendix import (
    expand_robustness_runs, validate_robustness_directory,
    write_campaign_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("frozen robustness protocol is invalid: %s" % exc)
    if not isinstance(value, dict):
        raise ValueError("frozen robustness protocol must be an object")
    return value


def _expected_campaign(runs):
    return {"campaign_version": 3,
            "evidence_namespace": "haichau_network_v2",
            "appendix_evidence_namespace": "haichau_network_v2/robustness",
            "study_role": "exploratory_appendix", "episode_count": 420,
            "runs": runs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir",
                        default="results/haichau_network_v2/robustness")
    parser.add_argument("--protocol", default=(
        "results/haichau_network_v2/robustness/"
        "frozen-robustness-protocol.json"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    campaign_dir = validate_robustness_directory(
        PROJECT_ROOT, Path(args.campaign_dir))
    protocol_path = Path(args.protocol)
    if not protocol_path.is_absolute():
        protocol_path = PROJECT_ROOT / protocol_path
    protocol = _load(protocol_path)
    runs = expand_robustness_runs(PROJECT_ROOT, protocol)
    manifest_path = campaign_dir / "campaign-manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != _expected_campaign(runs):
            raise ValueError("robustness campaign differs from frozen protocol")
    else:
        write_campaign_manifest(campaign_dir, runs)
    if args.prepare_only:
        return 0
    if args.verify_only:
        result = verify_campaign(campaign_dir, require_release_provenance=True,
                                 project_root=PROJECT_ROOT)
    else:
        result = run_pending(campaign_dir, project_root=PROJECT_ROOT)
    print(json.dumps(result, sort_keys=True))
    return 1 if result.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
