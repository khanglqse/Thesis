#!/usr/bin/env python3
"""Package the separate partial-telemetry Hai Chau visual demo."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(output):
    output = (ROOT / output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing visual bundle")
    (output / "replays").mkdir(parents=True)
    sources = {
        ROOT / "frontend/haichau_network_demo.html": output / "index.html",
        ROOT / "frontend/haichau_network_demo.css": output / "haichau_network_demo.css",
        ROOT / "frontend/haichau_network_demo.js": output / "haichau_network_demo.js",
        ROOT / "frontend/haichau_network_demo_core.js": output / "haichau_network_demo_core.js",
        ROOT / "scripts/haichau_demo_launcher.py": output / "launch_demo.py",
        ROOT / "results/haichau_network_v2/release-inputs/viewer-network-enriched.json": output / "network.json",
        ROOT / "results/haichau_network_v2/demo-bounded/summary.json": output / "summary.json",
        ROOT / "results/haichau_network_v2/demo-visual-work/pm_peak__fixed.json": output / "replays/pm_peak__fixed.json",
        ROOT / "results/haichau_network_v2/demo-visual-work/pm_peak__ddqn.json": output / "replays/pm_peak__ddqn.json",
    }
    for source, target in sources.items():
        if not source.is_file():
            raise ValueError("visual bundle source is missing: %s" % source)
        shutil.copy2(source, target)
    command = output / "launch_demo.command"
    command.write_text(
        "#!/bin/sh\ncd \"$(dirname \"$0\")\"\nexec python3 launch_demo.py --bundle . \"$@\"\n")
    command.chmod(0o755)
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output))] = sha256(path)
    manifest = {
        "bundle_version": 2,
        "controlled_signals": 53,
        "demand_label": "synthetic network demand constrained by Da Nang evidence",
        "network_path": "network.json",
        "aggregate_path": "summary.json",
        "queue_color_max": 50,
        "acceptance": {
            "accepted": False,
            "reason": "partial 0-1200 second visual telemetry; final metrics are stored end-of-run evidence",
        },
        "visual_scope": {
            "regimes": ["pm_peak"], "start_seconds": 0, "end_seconds": 1200,
            "sample_seconds": 5, "complete_horizon": False,
            "recorded_replay": True,
            "metrics_provenance": (
                "stored complete 3600-second evaluations; separate from partial visual telemetry"),
        },
        "guided_demo": {
            "time_seconds": 1085,
            "junction_id": "420249521",
        },
        "replays": [
            {"run_id": "tuned_fixed__test_pm_peak_demand105__3600s",
             "case_id": "test_pm_peak_demand105", "regime": "pm_peak",
             "controller_id": "tuned_fixed", "path": "replays/pm_peak__fixed.json"},
            {"run_id": "schedule_residual_ddqn__test_pm_peak_demand105__3600s",
             "case_id": "test_pm_peak_demand105", "regime": "pm_peak",
             "controller_id": "neighbor_phase_ddqn", "source_controller_id": "schedule_residual_ddqn",
             "path": "replays/pm_peak__ddqn.json"},
        ],
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"output": str(output.relative_to(ROOT)), "files": len(files),
            "bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/haichau_network_v2/demo-visual")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
