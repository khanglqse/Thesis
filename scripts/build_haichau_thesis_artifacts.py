#!/usr/bin/env python3
"""Generate Hai Chau thesis artifacts from a frozen campaign summary."""

import argparse
import json
from pathlib import Path

from traffic_rl.report.haichau_network import (
    validate_claims,
    write_artifacts,
    write_release_manifest,
)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary", default="results/haichau_network_v2/final/summary.json")
    parser.add_argument("--output", default="paper/generated/haichau_network")
    parser.add_argument("--thesis", default="paper/thesis_danang.tex")
    parser.add_argument("--pdf", default="paper/thesis_danang.pdf")
    parser.add_argument("--record-release-only", action="store_true")
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
    if args.record_release_only:
        command += " --record-release-only"
        manifest = write_release_manifest(
            summary, Path(args.output), thesis_path, Path(args.pdf), command)
    else:
        manifest = write_artifacts(
            summary, Path(args.output), command, thesis_path=thesis_path)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
