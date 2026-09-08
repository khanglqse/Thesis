#!/usr/bin/env python3
"""Generate Hai Chau thesis artifacts from a frozen campaign summary."""

import argparse
import json
from pathlib import Path

from traffic_rl.report.haichau_network import validate_claims, write_artifacts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary", default="results/haichau_network_v2/final/summary.json")
    parser.add_argument("--output", default="paper/generated/haichau_network")
    parser.add_argument("--thesis", default="paper/thesis_danang.tex")
    args = parser.parse_args(argv)
    summary_path = Path(args.summary)
    summary = json.loads(summary_path.read_text())
    thesis_path = Path(args.thesis)
    errors = validate_claims(thesis_path.read_text(), summary)
    if errors:
        raise ValueError("unsupported thesis claims:\n- " + "\n- ".join(errors))
    command = (
        "PYTHONPATH=src python3 scripts/build_haichau_thesis_artifacts.py "
        "--summary %s --output %s" % (args.summary, args.output))
    manifest = write_artifacts(summary, Path(args.output), command)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
