#!/usr/bin/env python3
"""Select the preregistered V3-B residual pilot checkpoint."""
import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.research.pilot_residual_selector import select_from_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        default="configs/haichau_residual_pilot_selection_v1.yaml")
    args = parser.parse_args(argv)
    os.chdir(str(ROOT))
    decision = select_from_spec(ROOT, args.spec)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
