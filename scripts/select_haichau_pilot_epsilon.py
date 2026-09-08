#!/usr/bin/env python3
"""Select the preregistered Hai Chau final epsilon schedule from two pilots."""

import argparse
import json
from pathlib import Path

from traffic_rl.research.pilot_epsilon_selector import select_from_spec


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec", default="configs/haichau_pilot_epsilon_selection_v1.yaml",
        help="immutable schema-v1 pilot-selection specification")
    args = parser.parse_args(argv)
    result = select_from_spec(PROJECT_ROOT, args.spec)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
