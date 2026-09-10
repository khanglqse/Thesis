#!/usr/bin/env python3
"""Export verified Hai Chau network runs into a bounded offline bundle."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign
from traffic_rl.eval.network_replay import (
    METRIC_KEYS,
    validate_network as _validate_network,
    validate_replay,
)
from traffic_rl.report.haichau_demo_fallbacks import validate_fallbacks


DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"
VIEWER_METRIC_KEYS = METRIC_KEYS + (
    "pending_integral_vehicle_seconds",
)
def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_bundle(campaign_dir, output_dir, network_path, selected_run_ids,
                  fallback_dir=None, require_release_provenance=False,
                  fallback_paths=None, project_root=None):
    if fallback_paths is not None:
        raise ValueError(
            "export requires one validated fallback directory, not individually supplied fallback files")
    campaign_dir = Path(campaign_dir)
    output_dir = Path(output_dir)
    network_path = Path(network_path)
    verify_campaign(
        campaign_dir, require_release_provenance=require_release_provenance,
        project_root=Path(__file__).resolve().parent.parent)
    campaign = json.loads((campaign_dir / "campaign-manifest.json").read_text())
    runs = dict((run["run_id"], run) for run in campaign["runs"])
    if len(selected_run_ids) != len(set(selected_run_ids)):
        raise ValueError("selected replay run IDs must be unique")
    unknown = sorted(set(selected_run_ids) - set(runs))
    if unknown:
        raise ValueError("selected replay run is not in campaign: %s" % unknown[0])

    network = json.loads(network_path.read_text())
    node_ids = _validate_network(network)
    network_sha256 = _sha256(network_path)
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
    shutil.copyfile(network_path, output_dir / "network.json")
    _write_json(output_dir / "aggregate-summary.json", summary)

    primary_controller = summary.get("summary", {}).get("_metadata", {}).get(
        "primary_learned_controller", "neighbor_phase_ddqn")
    if primary_controller not in ("neighbor_phase_ddqn", "schedule_residual_ddqn"):
        raise ValueError("summary has an unsupported learned controller")
    replay_entries = []
    grids = {}
    for run_id in selected_run_ids:
        run = runs[run_id]
        expected_network = run.get(
            "viewer_network_sha256", run.get("network_sha256"))
        if network_sha256 != expected_network:
            raise ValueError("viewer network hash does not match campaign run")
        run_dir = campaign_dir / "runs" / run_id
        status = json.loads((run_dir / "status.json").read_text())
        if "replay.json" not in status.get("artifact_sha256", {}):
            raise ValueError("selected run has no hash-verified replay: %s" % run_id)
        metrics = json.loads((run_dir / "metrics.json").read_text())
        replay = json.loads((run_dir / "replay.json").read_text())
        validate_replay(run, metrics, replay, node_ids)
        grid = tuple(frame["t"] for frame in replay["frames"])
        prior_grid = grids.setdefault(run["regime"], grid)
        if grid != prior_grid:
            raise ValueError("matched replay pair must use the same full time grid")
        exported = dict(replay)
        exported.update({
            "run_id": run_id,
            "case_id": run["case_id"],
            "regime": run["regime"],
            "controller_id": run["controller_id"],
            "learning_seed": run.get("learning_seed"),
            "demand_seed": run["demand_seed"],
            "simulator_seed": run["simulator_seed"],
            "checkpoint_path": run.get("checkpoint_path"),
            "checkpoint_sha256": run.get("checkpoint_sha256"),
            "checkpoint_contract_sha256": run.get("checkpoint_contract_sha256"),
            "metrics": dict((key, metrics.get(key)) for key in VIEWER_METRIC_KEYS
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
        if controller_ids != {"tuned_fixed", primary_controller} \
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
    fallback_provenance = None
    if fallback_dir is not None:
        project_root = Path(project_root or Path(__file__).resolve().parent.parent)
        fallback_provenance = validate_fallbacks(
            project_root, fallback_dir, campaign_dir)
        expected_run_ids = fallback_provenance["walkthrough_render"]["runs"]
        if list(selected_run_ids) != expected_run_ids:
            raise ValueError(
                "selected replay run IDs must exactly equal predeclared walkthrough runs")
        source_dir = Path(fallback_dir).resolve()
        for name in ("demo-walkthrough.mp4", "result-summary.pdf",
                     "network-overview.png", "fallback-provenance.json"):
            source = source_dir / name
            target = output_dir / "fallbacks" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if name != "fallback-provenance.json":
                fallbacks[name] = str(target.relative_to(output_dir))

    files = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output_dir))] = _sha256(path)
    manifest = {
        "bundle_version": 2,
        "controlled_signals": 53,
        "demand_label": DEMAND_LABEL,
        "network_sha256": network_sha256,
        "campaign_manifest_sha256": _sha256(
            campaign_dir / "campaign-manifest.json"),
        "summary_sha256": _canonical_hash(summary),
        "network_path": "network.json",
        "aggregate_path": "aggregate-summary.json",
        "acceptance": (summary.get("acceptance")
                       if isinstance(summary.get("acceptance"), dict) else None),
        "replays": replay_entries,
        "fallbacks": fallbacks,
        "fallback_provenance_path": (
            "fallbacks/fallback-provenance.json" if fallback_provenance else None),
        "fallback_provenance_sha256": (
            _sha256(output_dir / "fallbacks/fallback-provenance.json")
            if fallback_provenance else None),
        "walkthrough_run_ids": (
            fallback_provenance["walkthrough_render"]["runs"]
            if fallback_provenance else None),
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
    parser.add_argument("--fallback-dir", required=True,
                        help="directory built by build_haichau_demo_fallbacks.py")
    args = parser.parse_args(argv)
    manifest = export_bundle(
        args.campaign_dir, args.output, args.network, args.run_ids,
        args.fallback_dir,
        require_release_provenance=True)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
