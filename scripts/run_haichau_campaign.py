#!/usr/bin/env python3
"""Prepare, execute, resume, or verify the frozen Hai Chau campaign."""

import argparse
import hashlib
import json
from pathlib import Path

from traffic_rl.eval.network_campaign import (
    bind_frozen_manifest,
    expand_runs,
    run_pending,
    verify_campaign,
)
from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime
from traffic_rl.research.residual_release import FINAL_SEEDS
from traffic_rl.research.pilot_schedule_selector import (
    CONFIRMATORY_LEARNING_SEEDS, PRIMARY_LEARNED_CONTROLLER,
    validate_frozen_schedule_selection)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DETERMINISTIC_CONTROLLERS = ("tuned_fixed", "max_pressure", "hysteretic_mp")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_protocol_selection(root, protocol):
    primary = protocol.get("primary_learned_controller")
    if primary == "schedule_residual_ddqn":
        selection = protocol.get("selection")
        decisions = selection.get("decisions") if isinstance(selection, dict) else None
        if (not isinstance(decisions, dict)
                or selection.get("test_split_accessed") is not False
                or set(decisions) != set(str(seed) for seed in FINAL_SEEDS)):
            raise ValueError("frozen residual selector binding is invalid")
        return tuple(FINAL_SEEDS)
    validate_frozen_schedule_selection(root, protocol.get("selection"))
    if primary != PRIMARY_LEARNED_CONTROLLER:
        raise ValueError("frozen primary learned controller is invalid")
    return CONFIRMATORY_LEARNING_SEEDS


def _write_campaign(path, runs):
    path.mkdir(parents=True, exist_ok=True)
    target = path / "campaign-manifest.json"
    payload = {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if target.exists() and target.read_text() != encoded:
        raise ValueError("refusing to change an existing campaign manifest")
    target.write_text(encoded)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", default="results/haichau_network_v2/final")
    parser.add_argument("--manifest")
    parser.add_argument(
        "--protocol", default="results/haichau_network_v2/final/frozen-protocol.json")
    parser.add_argument("--learning-seeds")
    parser.add_argument("--controllers")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    campaign_dir = Path(args.campaign_dir)

    protocol_path = Path(args.protocol)
    if not protocol_path.is_absolute():
        protocol_path = PROJECT_ROOT / protocol_path
    if not protocol_path.is_file():
        raise ValueError("frozen protocol is required")
    protocol = json.loads(protocol_path.read_text())
    expected_seeds = _validate_protocol_selection(PROJECT_ROOT, protocol)
    primary = protocol.get("primary_learned_controller")
    controllers = tuple(DETERMINISTIC_CONTROLLERS) + (primary,)
    frozen_seeds = protocol.get("confirmatory_learning_seeds")
    if (tuple(frozen_seeds or ()) != tuple(expected_seeds)
            or frozen_seeds != protocol.get("acceptance_rules", {}).get(
                "required_learning_seeds")):
        raise ValueError("frozen confirmatory seed bindings disagree")
    if args.verify_only:
        manifest_path = Path(protocol.get("case_manifest_path", ""))
        if not manifest_path.is_absolute():
            manifest_path = PROJECT_ROOT / manifest_path
        if not manifest_path.is_file() \
                or _sha256(manifest_path) != protocol.get("case_manifest_sha256"):
            raise ValueError("frozen case manifest is missing or changed")
        manifest = bind_frozen_manifest(
            json.loads(manifest_path.read_text()), protocol)
        expected = expand_runs(manifest, frozen_seeds, controllers)
        actual = json.loads(
            (campaign_dir / "campaign-manifest.json").read_text()).get("runs")
        if actual != expected:
            raise ValueError("campaign differs from frozen protocol")
        print(json.dumps(verify_campaign(
            campaign_dir, require_release_provenance=True,
            project_root=PROJECT_ROOT), sort_keys=True))
        return 0
    if args.manifest:
        manifest_path = Path(args.manifest)
        if _sha256(manifest_path) != protocol.get("case_manifest_sha256"):
            raise ValueError("case manifest hash differs from frozen protocol")
        manifest = bind_frozen_manifest(
            json.loads(manifest_path.read_text()), protocol)
        seeds = (frozen_seeds if args.learning_seeds is None else
                 [int(value) for value in args.learning_seeds.split(",") if value])
        if seeds != frozen_seeds:
            raise ValueError("learning seeds differ from frozen acceptance rules")
        supplied_controllers = (list(controllers) if args.controllers is None else
                                [value for value in args.controllers.split(",") if value])
        if tuple(supplied_controllers) != controllers:
            raise ValueError("controllers differ from the frozen campaign contract")
        _write_campaign(campaign_dir, expand_runs(
            manifest, seeds, supplied_controllers))
    if args.prepare_only:
        return 0
    result = run_pending(campaign_dir, project_root=PROJECT_ROOT)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
