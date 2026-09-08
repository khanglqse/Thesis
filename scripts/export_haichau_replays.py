#!/usr/bin/env python3
"""Export verified Hai Chau network runs into a bounded offline bundle."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign


DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"
METRIC_KEYS = (
    "queue_integral_vehicle_seconds", "completion_rate", "arrived",
    "running", "pending",
)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _validate_network(network):
    nodes = network.get("nodes", [])
    if network.get("controlled_signals") != 53 or len(nodes) != 53:
        raise ValueError("offline network must contain exactly 53 controlled signals")
    node_ids = [node.get("id") for node in nodes]
    if None in node_ids or len(set(node_ids)) != 53:
        raise ValueError("offline network node IDs must be present and unique")
    known = set(node_ids)
    for link in network.get("links", []):
        if link.get("source") not in known or link.get("target") not in known:
            raise ValueError("offline network link references an unknown node")
    return known


def _validate_replay(run, metrics, replay, node_ids):
    if replay.get("sample_seconds") != 5:
        raise ValueError("replay frames must use a five-second sample interval")
    frames = replay.get("frames", [])
    if not frames or len(frames) > run["horizon_steps"] // 5 + 1:
        raise ValueError("replay frame count exceeds its bounded horizon")
    times = [int(frame.get("t", -1)) for frame in frames]
    if times != sorted(set(times)) or any(
            right - left != 5 for left, right in zip(times, times[1:])):
        raise ValueError("replay frame times must be unique five-second samples")
    if times[0] < 0 or times[-1] > run["horizon_steps"]:
        raise ValueError("replay frame time is outside the run horizon")
    for frame in frames:
        states = frame.get("nodes", {})
        if set(states) != node_ids:
            raise ValueError("every replay frame must contain all 53 signal states")
        for state in states.values():
            if float(state.get("queue", -1)) < 0 or state.get("phase") is None:
                raise ValueError("replay node state requires queue and phase")
        for vehicle in frame.get("vehicles", []):
            if vehicle.get("x") is None or vehicle.get("y") is None:
                raise ValueError("visible vehicle requires x and y")
    replay_metrics = replay.get("metrics", {})
    for key in METRIC_KEYS:
        if key in metrics and replay_metrics.get(key) != metrics[key]:
            raise ValueError("replay metric mismatch: %s" % key)


def export_bundle(campaign_dir, output_dir, network_path, selected_run_ids,
                  fallback_paths=None):
    campaign_dir = Path(campaign_dir)
    output_dir = Path(output_dir)
    network_path = Path(network_path)
    verify_campaign(campaign_dir)
    campaign = json.loads((campaign_dir / "campaign-manifest.json").read_text())
    runs = dict((run["run_id"], run) for run in campaign["runs"])
    if len(selected_run_ids) != len(set(selected_run_ids)):
        raise ValueError("selected replay run IDs must be unique")
    unknown = sorted(set(selected_run_ids) - set(runs))
    if unknown:
        raise ValueError("selected replay run is not in campaign: %s" % unknown[0])

    network = json.loads(network_path.read_text())
    node_ids = _validate_network(network)
    summary_path = campaign_dir / "summary.json"
    if not summary_path.is_file():
        raise ValueError("frozen campaign summary is missing")
    summary = json.loads(summary_path.read_text())
    scope = summary.get("study_scope", {})
    if scope.get("controlled_signals") != 53 \
            or scope.get("demand_label") != DEMAND_LABEL:
        raise ValueError("summary has an invalid 53-node synthetic-demand label")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("refusing to overwrite a non-empty demo directory")
    (output_dir / "replays").mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "network.json", network)
    _write_json(output_dir / "aggregate-summary.json", summary)

    replay_entries = []
    for run_id in selected_run_ids:
        run = runs[run_id]
        run_dir = campaign_dir / "runs" / run_id
        status = json.loads((run_dir / "status.json").read_text())
        if "replay.json" not in status.get("artifact_sha256", {}):
            raise ValueError("selected run has no hash-verified replay: %s" % run_id)
        metrics = json.loads((run_dir / "metrics.json").read_text())
        replay = json.loads((run_dir / "replay.json").read_text())
        _validate_replay(run, metrics, replay, node_ids)
        exported = dict(replay)
        exported.update({
            "run_id": run_id,
            "case_id": run["case_id"],
            "regime": run["regime"],
            "controller_id": run["controller_id"],
            "learning_seed": run.get("learning_seed"),
            "demand_seed": run["demand_seed"],
            "simulator_seed": run["simulator_seed"],
            "metrics": dict((key, metrics.get(key)) for key in METRIC_KEYS
                            if key in metrics),
        })
        relative = "replays/%s.json" % run_id
        _write_json(output_dir / relative, exported)
        replay_entries.append({
            "run_id": run_id, "case_id": run["case_id"],
            "regime": run["regime"], "controller_id": run["controller_id"],
            "path": relative,
        })
    for regime in sorted(set(entry["regime"] for entry in replay_entries)):
        selected = [entry for entry in replay_entries if entry["regime"] == regime]
        controller_ids = set(entry["controller_id"] for entry in selected)
        if controller_ids != {"tuned_fixed", "neighbor_phase_ddqn"} \
                or len(set(entry["case_id"] for entry in selected)) != 1:
            raise ValueError("each demo regime requires one fresh matched controller pair")

    frontend = Path(__file__).resolve().parent.parent / "frontend"
    frontend_files = {
        "haichau_network_demo.html": "index.html",
        "haichau_network_demo.css": "haichau_network_demo.css",
        "haichau_network_demo.js": "haichau_network_demo.js",
        "haichau_network_demo_core.js": "haichau_network_demo_core.js",
    }
    for source, destination in frontend_files.items():
        source_path = frontend / source
        if not source_path.is_file():
            raise ValueError("viewer source is missing: %s" % source)
        shutil.copyfile(source_path, output_dir / destination)

    fallbacks = {}
    for name, source in (fallback_paths or {}).items():
        source = Path(source)
        if not source.is_file():
            raise ValueError("fallback is missing: %s" % source)
        target = output_dir / "fallbacks" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        fallbacks[name] = str(target.relative_to(output_dir))

    files = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output_dir))] = _sha256(path)
    manifest = {
        "bundle_version": 2,
        "controlled_signals": 53,
        "demand_label": DEMAND_LABEL,
        "network_path": "network.json",
        "aggregate_path": "aggregate-summary.json",
        "replays": replay_entries,
        "fallbacks": fallbacks,
        "files": files,
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", default="results/haichau_network_v2/final")
    parser.add_argument("--output", default="results/haichau_network_v2/demo")
    parser.add_argument("--network", required=True)
    parser.add_argument("--run-id", action="append", dest="run_ids", required=True)
    parser.add_argument("--fallback-mp4")
    parser.add_argument("--fallback-pdf")
    parser.add_argument("--fallback-png")
    args = parser.parse_args(argv)
    fallbacks = {}
    for name, value in (("demo-walkthrough.mp4", args.fallback_mp4),
                        ("result-summary.pdf", args.fallback_pdf),
                        ("network-overview.png", args.fallback_png)):
        if value:
            fallbacks[name] = value
    manifest = export_bundle(
        args.campaign_dir, args.output, args.network, args.run_ids, fallbacks)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
