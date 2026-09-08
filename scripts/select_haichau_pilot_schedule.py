#!/usr/bin/env python3
"""Select the preregistered Hai Chau schedule-rehearsal arm from pilot evidence."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traffic_rl.research.pilot_schedule_selector import select_from_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec", default="configs/haichau_pilot_schedule_selection_v1.yaml",
        help="immutable schema-v1 behavior-arm selection specification")
    args = parser.parse_args(argv)
    result = select_from_spec(PROJECT_ROOT, args.spec)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
