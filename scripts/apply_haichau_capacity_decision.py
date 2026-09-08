#!/usr/bin/env python3
"""Validate and apply a hash-bound Hai Chau Stage-D capacity decision."""

import argparse
import json
from pathlib import Path

from traffic_rl.research.capacity_decision import apply_capacity_decision


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-d", required=True,
                        help="completed diagnostic Stage-D directory")
    parser.add_argument("--config", default="configs/haichau_network_v2.yaml",
                        help="Stage-D-bound generator config")
    parser.add_argument(
        "--decision",
        default="results/haichau_network_v2/diagnostics/capacity-decision.json",
        help="immutable capacity decision output")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true",
                      help="verify evidence and print the prospective decision")
    mode.add_argument("--new-version", action="store_true",
                      help="stage and deliberately regenerate the dataset version")
    args = parser.parse_args(argv)
    result = apply_capacity_decision(
        PROJECT_ROOT, args.stage_d, args.config,
        decision_path=args.decision, new_version=args.new_version,
        validate_only=args.validate_only)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
