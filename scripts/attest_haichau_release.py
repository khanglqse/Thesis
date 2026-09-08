#!/usr/bin/env python3
"""Execute the canonical Hai Chau release checks and record their evidence."""

import argparse
import json
from pathlib import Path

from traffic_rl.eval.release_attestation import create_attestation


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        default="results/haichau_network_v2/final/frozen-protocol.json")
    parser.add_argument(
        "--output",
        default="results/haichau_network_v2/verification/clean-checkout.json")
    args = parser.parse_args(argv)
    protocol_path = (PROJECT_ROOT / args.protocol).resolve()
    output_path = (PROJECT_ROOT / args.output).resolve()
    protocol_path.relative_to(PROJECT_ROOT)
    output_path.relative_to(PROJECT_ROOT)
    protocol = json.loads(protocol_path.read_text())
    record = create_attestation(PROJECT_ROOT, protocol, output_path)
    print(json.dumps({
        "output": str(output_path.relative_to(PROJECT_ROOT)),
        "passed": record["passed"],
        "verified_commit": record["verified_commit"],
    }, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
