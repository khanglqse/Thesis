#!/usr/bin/env python3
"""Freeze the V3 exploratory robustness appendix without running CityFlow."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.robustness_appendix import freeze_robustness_protocol
from traffic_rl.eval.primary_v3_validation import PRIMARY_RELATIVE


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/haichau_robustness_v3.yaml")
    parser.add_argument("--output", default="results/haichau_network_v2/robustness")
    args = parser.parse_args(argv)
    protocol = freeze_robustness_protocol(
        PROJECT_ROOT, PROJECT_ROOT / PRIMARY_RELATIVE, args.config, args.output)
    print(json.dumps({"episode_count": protocol["episode_count"],
                      "output": args.output,
                      "study_role": protocol["study_role"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
