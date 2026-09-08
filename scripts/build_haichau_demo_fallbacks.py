#!/usr/bin/env python3
"""Generate decoder-validated fallback media from final Hai Chau v2 evidence."""

import argparse
import json
from pathlib import Path

from traffic_rl.report.haichau_demo_fallbacks import build_fallbacks


ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--output", default="results/haichau_network_v2/demo-fallbacks")
    args = parser.parse_args(argv)
    print(json.dumps(build_fallbacks(args.root, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
