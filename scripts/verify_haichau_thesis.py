#!/usr/bin/env python3
"""Fail-closed release audit for the Hai Chau network thesis extension."""

import argparse
import datetime
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from traffic_rl.eval.network_campaign import (
    bind_frozen_manifest,
    expand_runs,
    verify_campaign,
)
from traffic_rl.eval.network_replay import validate_network, validate_replay
from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime
from traffic_rl.eval.release_attestation import validate_attestation
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance
from traffic_rl.report.haichau_network import validate_claims
from traffic_rl.report.media_validation import probe_pdf, probe_png, probe_video
from traffic_rl.sim.phase_encoder import FEATURES


DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"
REQUIRED_CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)
LEARNING_CONTROLLERS = ("shared_ddqn_legacy", "neighbor_phase_ddqn")
REQUIRED_REGIMES = ("normal", "am_peak", "pm_peak")
REQUIRED_SEEDS = (11, 12, 13, 14, 15)
REQUIRED_FALLBACKS = (
    "demo-walkthrough.mp4", "result-summary.pdf", "network-overview.png",
)
REQUIRED_FRONTEND = {
    "index.html", "haichau_network_demo.css", "haichau_network_demo.js",
    "haichau_network_demo_core.js",
}
CHECKPOINT_CONTRACT_FIELDS = {
    "obs_schema_version", "feature_order", "normalization", "hidden_size",
    "action_contract", "network_compatibility", "controller_family",
}
ACTION_CONTRACTS = {
    "neighbor_phase_ddqn": {
        "type": "phase_rows", "version": 1,
        "mask_type": "boolean_selectable_green_rows",
        "padding_actions_selectable": False,
    },
    "shared_ddqn_legacy": {
        "type": "fixed_vector", "version": 1,
        "mask_type": "boolean_phase_index",
        "padding_actions_selectable": False,
        "n_actions": 3,
    },
}
THESIS_ARTIFACTS = {
    "haichau_network_results.tex", "haichau_controller_comparison.tex",
    "paired-queue-difference.png", "paired-queue-difference.pdf",
    "completion-rate.png", "completion-rate.pdf",
}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _gate(passed, detail, evidence=None):
    return {
        "passed": bool(passed),
        "detail": detail,
        "evidence": evidence if evidence is not None else {},
    }


def _json(path):
    return json.loads(Path(path).read_text())


def _inside(root, relative):
    if not relative:
        return None
    candidate = (Path(root) / relative).resolve()
    try:
        candidate.relative_to(Path(root).resolve())
    except ValueError:
        return None
    return candidate


def _protocol(root):
    path = root / "results/haichau_network_v2/final/frozen-protocol.json"
    return (_json(path), path) if path.is_file() else (None, path)


def _bound_manifest(root, protocol, prefix):
    if not protocol:
        raise ValueError("frozen-protocol.json is missing")
    path = _inside(root, protocol.get(prefix + "_manifest_path"))
    expected = protocol.get(prefix + "_manifest_sha256")
    if not path or not path.is_file() or not expected:
        raise ValueError("frozen %s manifest path/hash is missing" % prefix)
    if _sha256(path) != expected:
        raise ValueError("frozen %s manifest hash mismatch" % prefix)
    return _json(path), path


def _network_gate(root, protocol):
    try:
        manifest, path = _bound_manifest(root, protocol, "network")
        agents = manifest.get("agent_ids", [])
        count = manifest.get("controlled_signals")
        if count is None:
            count = manifest.get("counts", {}).get("controlled_signals")
        if count != 53 or len(agents) != 53 or len(set(agents)) != 53:
            raise ValueError("network manifest must identify 53 unique signal IDs")
        if (protocol or {}).get("agent_ids") != agents:
            raise ValueError("frozen protocol agent IDs differ from network manifest")
        artifacts = manifest.get("artifacts", {})
        if not isinstance(artifacts, dict) or not artifacts:
            raise ValueError("network manifest requires hash-bound runtime artifacts")
        verified_hashes = set()
        for name, entry in artifacts.items():
            if not isinstance(entry, dict):
                raise ValueError("network artifact metadata must be an object")
            artifact = _inside(root, entry.get("path"))
            expected = entry.get("sha256")
            if not artifact or not artifact.is_file() or _sha256(artifact) != expected:
                raise ValueError("network artifact hash mismatch: %s" % name)
            verified_hashes.add(expected)
        for field in ("network_sha256", "viewer_network_sha256"):
            if (protocol or {}).get(field) not in verified_hashes:
                raise ValueError("%s is not bound to a verified network artifact" % field)
        return _gate(True, "53-signal topology and runtime artifacts are hash-valid", {
            "path": str(path.relative_to(root)),
            "controlled_signals": count,
            "artifact_count": len(artifacts),
        })
    except Exception as exc:
        return _gate(False, str(exc))


def _load_cases(root, protocol):
    manifest, path = _bound_manifest(root, protocol, "case")
    cases = manifest.get("cases", [])
    if len(cases) != 30:
        raise ValueError("case manifest must contain exactly 30 cases")
    ids, demand_splits = set(), {}
    split_counts = dict((name, 0) for name in ("train", "validation", "test"))
    for case in cases:
        case_id = case.get("case_id")
        split = case.get("split")
        demand_hash = case.get("demand_sha256")
        if not case_id or case_id in ids:
            raise ValueError("case IDs must be present and unique")
        if split not in split_counts or not re.fullmatch(r"[0-9a-f]{64}", str(demand_hash)):
            raise ValueError("case split and demand hash must be valid")
        demand_path = _inside(root, case.get("demand_path"))
        if not demand_path or not demand_path.is_file() or _sha256(demand_path) != demand_hash:
            raise ValueError("case demand artifact hash mismatch: %s" % case_id)
        prior = demand_splits.setdefault(demand_hash, split)
        if prior != split:
            raise ValueError("demand artifact appears in multiple splits")
        if split == "test":
            for field in ("regime", "demand_seed", "simulator_seed", "horizon_steps"):
                if case.get(field) is None:
                    raise ValueError("test case requires %s" % field)
        ids.add(case_id)
        split_counts[split] += 1
    if not all(split_counts.values()):
        raise ValueError("train, validation and test splits must all be non-empty")
    return manifest, path, split_counts


def _case_gate(root, protocol):
    try:
        _, path, splits = _load_cases(root, protocol)
        return _gate(True, "30-case manifest is hash-valid and split-safe", {
            "path": str(path.relative_to(root)), "split_counts": splits,
        })
    except Exception as exc:
        return _gate(False, str(exc))


def _source_gate(root, protocol):
    try:
        identity = verify_git_checkout(root, (protocol or {}).get("code_commit"))
        return _gate(True, "checkout is clean and frozen code paths are unchanged", identity)
    except Exception as exc:
        return _gate(False, str(exc))


def _runtime_gate(root, protocol):
    try:
        identity = verify_runtime(root, protocol)
        return _gate(
            True, "CityFlow Docker image and Dockerfile identities are verified", identity)
    except Exception as exc:
        return _gate(False, str(exc))


def _checkpoint_contract_valid(contract, protocol, controller):
    if not isinstance(contract, dict) or not CHECKPOINT_CONTRACT_FIELDS.issubset(contract):
        return False
    try:
        features = contract["feature_order"]
        normalization = contract["normalization"]
        compatibility = contract["network_compatibility"]
        compatibility_fields = {
            "network_sha256": "network_sha256",
            "phase_contract_sha256": "phase_contract_sha256",
            "generator_config_sha256": "generator_config_sha256",
            "manifest_sha256": "experiment_manifest_sha256",
        }
        hidden = contract["hidden_size"]
        if isinstance(hidden, bool) or not isinstance(hidden, int) or hidden <= 0:
            return False
        if contract["obs_schema_version"] != 2 \
                or contract["controller_family"] != controller:
            return False
        if (not isinstance(features, list) or not features
                or any(not isinstance(item, str) or not item for item in features)
                or len(set(features)) != len(features)):
            return False
        if (not isinstance(normalization, dict)
                or normalization != (protocol or {}).get("normalization")
                or any(isinstance(value, bool) or not math.isfinite(float(value))
                       or float(value) <= 0 for value in normalization.values())):
            return False
        if controller == "neighbor_phase_ddqn" and features != list(FEATURES):
            return False
        if contract["action_contract"] != ACTION_CONTRACTS.get(controller):
            return False
        if not isinstance(compatibility, dict) \
                or set(compatibility) != set(compatibility_fields):
            return False
        for contract_field, protocol_field in compatibility_fields.items():
            value = compatibility.get(contract_field)
            if (not re.fullmatch(r"[0-9a-f]{64}", str(value or ""))
                    or value != (protocol or {}).get(protocol_field)):
                return False
        aliases = {
            "hidden": hidden,
            "count_norm": normalization["count_norm"],
            "capacity_norm": normalization["capacity_norm"],
            "network_sha256": compatibility["network_sha256"],
        }
        return all(name not in contract or contract[name] == value
                   for name, value in aliases.items())
    except (TypeError, ValueError, OverflowError):
        return False


def _checkpoint_gate(root, protocol):
    entries = (protocol or {}).get("checkpoints", [])
    if not isinstance(entries, list):
        return _gate(False, "frozen checkpoint list must be an array")
    cells, valid, evidence = set(), True, []
    for entry in entries:
        if not isinstance(entry, dict):
            valid = False
            evidence.append({"controller_id": None, "learning_seed": None,
                             "valid": False})
            continue
        controller = entry.get("controller_id")
        seed = entry.get("learning_seed")
        cell = (controller, seed)
        path = _inside(root, entry.get("path"))
        expected = entry.get("sha256")
        contract = entry.get("checkpoint_contract")
        contract_path = _inside(root, entry.get("contract_path"))
        contract_file_sha256 = entry.get("contract_file_sha256")
        stored_contract = None
        if contract_path and contract_path.is_file() \
                and contract_file_sha256 \
                and _sha256(contract_path) == contract_file_sha256:
            try:
                stored_contract = _json(contract_path)
            except (OSError, ValueError):
                stored_contract = None
        okay = bool(
            controller in LEARNING_CONTROLLERS and seed in REQUIRED_SEEDS
            and cell not in cells and path and path.is_file() and expected
            and _sha256(path) == expected
            and entry.get("validation_eligible") is True
            and stored_contract == contract
            and _checkpoint_contract_valid(contract, protocol, controller)
            and entry.get("checkpoint_contract_sha256") == _canonical_hash(contract))
        valid = valid and okay
        cells.add(cell)
        evidence.append({
            "controller_id": controller, "learning_seed": seed, "valid": okay,
        })
    expected_cells = set((controller, seed) for controller in LEARNING_CONTROLLERS
                         for seed in REQUIRED_SEEDS)
    valid = valid and cells == expected_cells
    return _gate(valid, "all learned runs require full hash-bound checkpoint contracts", {
        "cells": evidence,
    })


def _acceptance_rules(protocol):
    rules = (protocol or {}).get("acceptance_rules", {})
    if set(rules.get("required_learning_seeds", ())) != set(REQUIRED_SEEDS):
        raise ValueError("acceptance rules must freeze learning seeds 11--15")
    if set(rules.get("required_regimes", ())) != set(REQUIRED_REGIMES):
        raise ValueError("acceptance rules must freeze normal/AM/PM regimes")
    if int(rules.get("minimum_learning_seeds", 0)) < 5:
        raise ValueError("acceptance rules require at least five learning seeds")
    if int(rules.get("minimum_demand_units", 0)) < 2:
        raise ValueError("acceptance rules require at least two matched demand units")
    if rules.get("bootstrap_seed") != 20260908 or rules.get("bootstrap_samples") != 10000:
        raise ValueError("bootstrap configuration differs from the declared implementation")
    thresholds = {
        "normal_point_limit": 0.0,
        "normal_ci_margin_fraction": 0.05,
        "peak_ci_upper_limit": 0.0,
        "completion_degradation_limit": 0.02,
    }
    if any(rules.get(name) != value for name, value in thresholds.items()):
        raise ValueError("acceptance thresholds differ from the predeclared implementation")
    return rules


def _expected_runs(root, protocol):
    case_manifest, _, _ = _load_cases(root, protocol)
    rules = _acceptance_rules(protocol)
    manifest = bind_frozen_manifest(case_manifest, protocol)
    if len(manifest["agent_ids"]) != 53:
        raise ValueError("frozen protocol must bind the exact 53 agent IDs")
    if set(manifest["controller_configs"]) != set(REQUIRED_CONTROLLERS):
        raise ValueError("frozen protocol must bind every controller config")
    return expand_runs(
        manifest, rules["required_learning_seeds"], REQUIRED_CONTROLLERS)


def _campaign_gates(root, protocol):
    campaign_dir = root / "results/haichau_network_v2/final"
    try:
        expected_runs = _expected_runs(root, protocol)
        campaign = _json(campaign_dir / "campaign-manifest.json")
        if campaign.get("evidence_namespace") != "haichau_network_v2":
            raise ValueError("campaign evidence namespace is invalid")
        if campaign.get("runs") != expected_runs:
            raise ValueError("campaign run matrix differs from frozen cases/config/checkpoints")
        verified = verify_campaign(campaign_dir)
        provenance_error = None
        try:
            verify_campaign(
                campaign_dir, require_release_provenance=True, project_root=root)
        except Exception as exc:
            provenance_error = str(exc)
        runs = campaign["runs"]
        metrics_rows = []
        for run in runs:
            metrics = _json(campaign_dir / "runs" / run["run_id"] / "metrics.json")
            row = dict(run)
            row.update(metrics)
            metrics_rows.append(row)
        regimes = set(run["regime"] for run in runs)
        horizon_ok = all(row["completed_steps"] == row["horizon_steps"]
                         and row["observed_steps"] == row["horizon_steps"]
                         for row in metrics_rows)
        matched = _gate(
            provenance_error is None,
            ("campaign exactly matches frozen cases/config/checkpoints and trusted execution"
             if provenance_error is None else
             "campaign verification failed: %s" % provenance_error), {
            "verified_runs": verified["complete"],
            "campaign_sha256": _sha256(campaign_dir / "campaign-manifest.json"),
        })
        scenarios = _gate(regimes == set(REQUIRED_REGIMES),
                          "campaign regimes must be exactly normal, AM peak and PM peak", {
                              "regimes": sorted(regimes),
                          })
        horizons = _gate(horizon_ok and bool(runs), "all run horizons must be complete", {
            "run_count": len(runs),
        })
        return matched, scenarios, horizons, metrics_rows
    except Exception as exc:
        detail = "campaign verification failed: %s" % exc
        failed = _gate(False, detail)
        return failed, failed, failed, None


def _expected_summary(protocol, rows):
    rules = _acceptance_rules(protocol)
    summary = aggregate_campaign(
        rows,
        required_learning_seeds=rules["required_learning_seeds"],
        required_regimes=rules["required_regimes"],
        minimum_learning_seeds=rules["minimum_learning_seeds"],
        minimum_demand_units=rules["minimum_demand_units"],
        normal_point_limit=rules["normal_point_limit"],
        normal_ci_margin_fraction=rules["normal_ci_margin_fraction"],
        peak_ci_upper_limit=rules["peak_ci_upper_limit"],
        completion_degradation_limit=rules["completion_degradation_limit"],
    )
    return {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": DEMAND_LABEL,
            "evidence_namespace": "haichau_network_v2",
        },
        "summary": summary,
        "acceptance": evaluate_acceptance(summary),
    }


def _summary_gates(root, protocol, rows):
    path = root / "results/haichau_network_v2/final/summary.json"
    if rows is None or not path.is_file():
        missing = _gate(False, "verified campaign rows or frozen summary.json are missing")
        return missing, missing, None
    try:
        expected = _expected_summary(protocol, rows)
        actual = _json(path)
        if actual != expected:
            raise ValueError("summary/acceptance does not exactly recompute from verified runs")
        acceptance = actual["acceptance"]
        statistics_gate = _gate(
            acceptance.get("minimum_independent_units_met") is True,
            "numeric hierarchical statistics satisfy frozen independent-unit rules", {
                "summary_sha256": _canonical_hash(actual),
                "minimum_independent_units_met": acceptance.get(
                    "minimum_independent_units_met"),
            })
        acceptance_gate = _gate(
            isinstance(acceptance.get("accepted"), bool),
            "predeclared acceptance is exactly recomputed, including negative outcomes",
            acceptance,
        )
        return statistics_gate, acceptance_gate, actual
    except Exception as exc:
        failed = _gate(False, str(exc))
        return failed, failed, None


def _thesis_gate(root, summary):
    artifact_path = root / "paper/generated/haichau_network/artifact-manifest.json"
    release_path = root / "paper/generated/haichau_network/thesis-release.json"
    thesis_path = root / "paper/thesis_danang.tex"
    pdf_path = root / "paper/thesis_danang.pdf"
    if summary is None or not all(path.is_file() for path in (
            artifact_path, release_path, thesis_path, pdf_path)):
        return _gate(False, "summary-derived thesis artifact/release manifests are missing")
    try:
        artifacts = _json(artifact_path)
        release = _json(release_path)
        summary_hash = _canonical_hash(summary)
        if artifacts.get("summary_sha256") != summary_hash:
            raise ValueError("thesis artifact summary hash mismatch")
        artifact_hashes = artifacts.get("artifacts", {})
        required = THESIS_ARTIFACTS | set(
            name + ".provenance.json" for name in THESIS_ARTIFACTS)
        if set(artifact_hashes) != required:
            raise ValueError("thesis generated artifact set is incomplete")
        media_probes = {}
        for name, expected in artifact_hashes.items():
            path = _inside(artifact_path.parent, name)
            if not path or not path.is_file() or _sha256(path) != expected:
                raise ValueError("thesis artifact hash mismatch: %s" % name)
            if name.endswith(".provenance.json"):
                sidecar = _json(path)
                if sidecar.get("summary_sha256") != summary_hash:
                    raise ValueError("thesis sidecar summary hash mismatch: %s" % name)
            elif name.endswith(".png"):
                media_probes[name] = probe_png(path)
            elif name.endswith(".pdf"):
                media_probes[name] = probe_pdf(path)
        thesis_hash = _sha256(thesis_path)
        if artifacts.get("thesis_source_sha256") != thesis_hash:
            raise ValueError("thesis source changed after artifact generation")
        if validate_claims(thesis_path.read_text(), summary):
            raise ValueError("thesis contains unsupported claims")
        pdf_probe = probe_pdf(pdf_path)
        expected_release = {
            "summary_sha256": summary_hash,
            "artifact_manifest_sha256": _sha256(artifact_path),
            "thesis_source_sha256": thesis_hash,
            "pdf_sha256": _sha256(pdf_path),
        }
        if any(release.get(key) != value for key, value in expected_release.items()):
            raise ValueError("compiled thesis release hashes are stale")
        return _gate(True, "table, figures, sidecars, source and PDF are hash-bound", {
            "summary_sha256": summary_hash,
            "pdf_sha256": expected_release["pdf_sha256"],
            "pdf_probe": pdf_probe,
            "generated_media_probes": media_probes,
        })
    except Exception as exc:
        return _gate(False, str(exc))


def _probe_fallback(name, path):
    if name.endswith(".mp4"):
        return probe_video(path)
    if name.endswith(".pdf"):
        return probe_pdf(path)
    if name.endswith(".png"):
        return probe_png(path)
    raise ValueError("unsupported fallback media type: %s" % name)


def audit_demo(root, protocol=None, campaign=None, summary=None):
    root = Path(root).resolve()
    demo = root / "results/haichau_network_v2/demo"
    manifest_path = demo / "manifest.json"
    if not manifest_path.is_file():
        return _gate(False, "offline demo manifest is missing")
    try:
        manifest = _json(manifest_path)
        if manifest.get("controlled_signals") != 53 \
                or manifest.get("demand_label") != DEMAND_LABEL:
            return _gate(False, "offline demo scope/label is invalid")
        files = manifest.get("files", {})
        actual_files = {
            str(path.relative_to(demo)) for path in demo.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if set(files) != actual_files:
            return _gate(False, "offline demo file set differs from its hash manifest", {
                "unlisted": sorted(actual_files - set(files)),
                "missing": sorted(set(files) - actual_files),
            })
        for relative, expected in files.items():
            path = _inside(demo, relative)
            if not path or not path.is_file() or _sha256(path) != expected:
                return _gate(False, "offline demo file hash mismatch: %s" % relative)
        frontend = [path for path in demo.iterdir()
                    if path.suffix.lower() in {".html", ".css", ".js"}]
        for path in frontend:
            if re.search(r"https?://|(?<!:)//[A-Za-z0-9]", path.read_text()):
                return _gate(False, "offline demo has a remote dependency: %s" % path.name)
        if not REQUIRED_FRONTEND.issubset(files):
            return _gate(False, "offline demo frontend payload is incomplete")
        if protocol is None:
            protocol, _ = _protocol(root)
        if protocol is None:
            return _gate(False, "offline demo is not bound to a frozen protocol")
        network_path = _inside(demo, manifest.get("network_path"))
        if not network_path or _sha256(network_path) != protocol.get("viewer_network_sha256"):
            return _gate(False, "offline demo network hash differs from frozen protocol")
        if manifest.get("network_sha256") != _sha256(network_path):
            return _gate(False, "offline demo manifest network hash mismatch")
        network = _json(network_path)
        node_ids = validate_network(network)
        fallbacks = manifest.get("fallbacks", {})
        if set(fallbacks) != set(REQUIRED_FALLBACKS):
            return _gate(False, "offline demo fallbacks are incomplete")
        fallback_probes = {}
        for name, relative in fallbacks.items():
            path = _inside(demo, relative)
            if not path or relative not in files:
                return _gate(False, "offline demo fallback is invalid: %s" % name)
            fallback_probes[name] = _probe_fallback(name, path)
        final = root / "results/haichau_network_v2/final"
        if campaign is None:
            campaign = _json(final / "campaign-manifest.json")
        if summary is None:
            summary = _json(final / "summary.json")
        if manifest.get("campaign_manifest_sha256") != _sha256(
                final / "campaign-manifest.json"):
            return _gate(False, "offline demo campaign hash mismatch")
        if manifest.get("summary_sha256") != _canonical_hash(summary):
            return _gate(False, "offline demo summary hash mismatch")
        if _json(demo / manifest["aggregate_path"]) != summary:
            return _gate(False, "offline aggregate does not match frozen summary")
        runs = dict((run["run_id"], run) for run in campaign.get("runs", []))
        replays = manifest.get("replays", [])
        if len(replays) != 6:
            return _gate(False, "offline demo requires exactly three matched replay pairs")
        for regime in REQUIRED_REGIMES:
            entries = [entry for entry in replays if entry.get("regime") == regime]
            if len(entries) != 2 or set(entry.get("controller_id") for entry in entries) != {
                    "tuned_fixed", "neighbor_phase_ddqn"} \
                    or len(set(entry.get("case_id") for entry in entries)) != 1:
                return _gate(False, "offline demo replay pair is not matched: %s" % regime)
            grids = []
            for entry in entries:
                run = runs.get(entry.get("run_id"))
                if not run or any(entry.get(field) != run.get(field) for field in (
                        "case_id", "regime", "controller_id")):
                    return _gate(False, "offline replay identity differs from campaign")
                run_dir = final / "runs" / run["run_id"]
                source = _json(run_dir / "replay.json")
                exported = _json(demo / entry["path"])
                metrics = _json(run_dir / "metrics.json")
                validate_replay(run, metrics, exported, node_ids)
                for field in (
                        "run_id", "case_id", "regime", "controller_id",
                        "learning_seed", "demand_seed", "simulator_seed"):
                    if exported.get(field) != run.get(field):
                        return _gate(False, "offline replay payload identity differs from run")
                if exported.get("frames") != source.get("frames"):
                    return _gate(False, "offline replay frames differ from verified run")
                grids.append(tuple(frame["t"] for frame in exported["frames"]))
            if grids[0] != grids[1]:
                return _gate(False, "offline replay pair time grids differ")
        return _gate(True, "offline demo is bound to verified runs and frozen evidence", {
            "replay_count": len(replays), "fallbacks": fallback_probes,
        })
    except Exception as exc:
        return _gate(False, "offline demo verification failed: %s" % exc)


def _clean_checkout_gate(root, protocol):
    path = root / "results/haichau_network_v2/verification/clean-checkout.json"
    if not path.is_file():
        return _gate(False, "clean-checkout verification record is missing")
    try:
        record = _json(path)
        evidence = validate_attestation(root, protocol or {}, record)
        return _gate(
            True,
            "verifier-generated command logs bind the clean checkout and release hashes",
            evidence)
    except Exception as exc:
        return _gate(False, "clean-checkout verification failed: %s" % exc)


def verify_project(root, skip_clean_checkout=False):
    root = Path(root).resolve()
    protocol, protocol_path = _protocol(root)
    matched, scenarios, horizons, rows = _campaign_gates(root, protocol)
    statistics_gate, acceptance_gate, summary = _summary_gates(root, protocol, rows)
    campaign = None
    campaign_path = root / "results/haichau_network_v2/final/campaign-manifest.json"
    if campaign_path.is_file():
        campaign = _json(campaign_path)
    gates = {
        "source_revision": _source_gate(root, protocol),
        "network_53_signals": _network_gate(root, protocol),
        "thirty_case_split": _case_gate(root, protocol),
        "runtime_pinned": _runtime_gate(root, protocol),
        "five_learning_seeds": _checkpoint_gate(root, protocol),
        "fresh_matched_runs": matched,
        "scenario_coverage": scenarios,
        "horizon_complete": horizons,
        "hierarchical_statistics": statistics_gate,
        "acceptance_reported": acceptance_gate,
        "thesis_artifacts": _thesis_gate(root, summary),
        "offline_demo": audit_demo(root, protocol, campaign, summary),
    }
    if not skip_clean_checkout:
        gates["clean_checkout"] = _clean_checkout_gate(root, protocol)
    failed = [name for name, value in gates.items() if not value["passed"]]
    return {
        "verification_version": 5,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_path": str(protocol_path.relative_to(root)),
        "complete": not failed,
        "failed_gates": failed,
        "gates": gates,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument(
        "--output", default="results/haichau_network_v2/verification/final-report.json")
    parser.add_argument("--skip-clean-checkout", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    report = verify_project(root, skip_clean_checkout=args.skip_clean_checkout)
    output = _inside(root, args.output)
    if not args.no_write:
        if output is None:
            raise ValueError("output must remain inside the project root")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "complete": report["complete"],
        "failed_gates": report["failed_gates"],
        "report": None if args.no_write else str(output.relative_to(root)),
    }, sort_keys=True))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
