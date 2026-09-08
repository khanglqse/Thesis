#!/usr/bin/env python3
"""Prepare or explicitly execute validation-only Hai Chau capacity diagnostics."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.capacity_calibration import (
    execute_campaign,
    prepare_campaign,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _scales(value):
    if value is None:
        return None
    try:
        return [float(item) for item in value.split(",") if item]
    except ValueError:
        raise argparse.ArgumentTypeError("chosen scales must be comma-separated numbers")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True,
                        choices=("scale1", "ladder", "stage-d"))
    parser.add_argument("--output", required=True,
                        help="diagnostic stage directory inside the project")
    parser.add_argument(
        "--manifest",
        default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--config", default="configs/haichau_training_v2.yaml")
    parser.add_argument("--chosen-scales", type=_scales)
    parser.add_argument("--drain-horizon", type=int, default=5400,
                        choices=(5400, 7200))
    parser.add_argument(
        "--execute", action="store_true",
        help="run CityFlow; without this flag only immutable inputs are prepared")
    args = parser.parse_args(argv)
    output = Path(args.output)
    campaign = prepare_campaign(
        PROJECT_ROOT, args.manifest, args.config, output,
        stage=args.stage, chosen_scales=args.chosen_scales,
        drain_horizon=args.drain_horizon)
    if args.execute:
        result = execute_campaign(PROJECT_ROOT, output)
        status = dict(result)
    else:
        status = {
            "status": "diagnostic_prepared",
            "runs": len(campaign["runs"]),
            "campaign_identity_sha256": campaign["campaign_identity_sha256"],
        }
    status["eligible_for_release"] = False
    status["eligible_for_test_evaluation"] = False
    print(json.dumps(status, indent=2, sort_keys=True))
    return 1 if status.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
