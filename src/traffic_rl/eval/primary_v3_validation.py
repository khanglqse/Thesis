"""Authoritative validation of the completed primary Hai Chau V3 release."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from traffic_rl.eval.network_campaign import (
    bind_frozen_manifest, canonical_sha256, expand_runs, verify_campaign,
)
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance
from traffic_rl.research.pilot_schedule_selector import (
    CONFIRMATORY_LEARNING_SEEDS, PRIMARY_LEARNED_CONTROLLER,
    validate_frozen_schedule_selection,
)


RESIDUAL_PRIMARY_CONTROLLER = "schedule_residual_ddqn"
SUPPORTED_PRIMARY_CONTROLLERS = (PRIMARY_LEARNED_CONTROLLER,
                                 RESIDUAL_PRIMARY_CONTROLLER)
DETERMINISTIC_PRIMARY_CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
)


def _primary_controllers(protocol):
    controller = protocol.get("primary_learned_controller")
    if controller not in SUPPORTED_PRIMARY_CONTROLLERS:
        raise ValueError("primary V3 controller is unsupported")
    return DETERMINISTIC_PRIMARY_CONTROLLERS + (controller,)


# Backward-compatible name for the legacy neighbor-DDQN release tests.
PRIMARY_CONTROLLERS = DETERMINISTIC_PRIMARY_CONTROLLERS + (PRIMARY_LEARNED_CONTROLLER,)
PRIMARY_RUN_COUNT = 120
PRIMARY_FINAL_RELATIVE = Path("results/haichau_network_v2/final")
PRIMARY_RELATIVE = PRIMARY_FINAL_RELATIVE / "frozen-protocol.json"
_PRIMARY_FILENAMES = frozenset((
    "frozen-protocol.json", "campaign-manifest.json", "summary.json",
))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_CHECKPOINT_ARTIFACTS = frozenset((
    "checkpoint/weights.npz", "checkpoint/contract.json", "validation.json",
    "selection.json", "resolved-config.json", "baseline-tuning.json",
    "run-manifest.json",
))


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _inside_file(root, value, label):
    root = Path(root).resolve()
    path = Path(str(value or ""))
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return path


def canonical_primary_release_path(root, filename, supplied=None):
    """Return one non-symlink regular file at its exact primary release path."""
    if filename not in _PRIMARY_FILENAMES:
        raise ValueError("unknown canonical primary release artifact")
    root = Path(root).resolve()
    canonical = root / PRIMARY_FINAL_RELATIVE / filename
    if supplied is not None:
        candidate = Path(str(supplied))
        candidate = candidate if candidate.is_absolute() else root / candidate
        candidate = Path(os.path.abspath(str(candidate)))
        if candidate != canonical:
            raise ValueError(
                "primary V3 artifact must use its canonical lexical final path")
    current = root
    for component in (PRIMARY_FINAL_RELATIVE / filename).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(
                "canonical primary release artifact cannot be a symbolic link")
    if not canonical.is_file() \
            or not stat.S_ISREG(canonical.stat().st_mode):
        raise ValueError("canonical primary release artifact is missing")
    return canonical


def canonical_primary_protocol_path(root, supplied=None):
    """Return the sole primary protocol path accepted by the V3 verifier."""
    return canonical_primary_release_path(
        root, "frozen-protocol.json", supplied=supplied)


def _hash_bound_file(root, value, expected, label):
    path = _inside_file(root, value, label)
    if not _SHA256.match(str(expected or "")) or _sha256(path) != expected:
        raise ValueError("%s hash drift" % label)
    return path


def _inside_directory(root, value, label):
    root = Path(root).resolve()
    path = (root / str(value or "")).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    if not path.is_dir():
        raise ValueError("%s is missing" % label)
    return path


def _validate_checkpoint_bindings(root, protocol, controller):
    entries = protocol.get("checkpoints")
    if not isinstance(entries, list) or len(entries) != len(
            CONFIRMATORY_LEARNING_SEEDS):
        raise ValueError("primary V3 requires exactly five checkpoints")
    validated = []
    for seed in CONFIRMATORY_LEARNING_SEEDS:
        matches = [entry for entry in entries
                   if isinstance(entry, dict)
                   and entry.get("controller_id") == controller
                   and entry.get("learning_seed") == seed]
        if len(matches) != 1:
            raise ValueError("primary V3 requires one checkpoint per seed 12--16")
        entry = matches[0]
        if controller == RESIDUAL_PRIMARY_CONTROLLER:
            selection = entry.get("selection", {})
            if not isinstance(selection, dict):
                raise ValueError("residual checkpoint selection binding is invalid")
            selection_path = _hash_bound_file(
                root, selection.get("path"), selection.get("sha256"),
                "residual checkpoint selection")
            decision = _json(selection_path, "residual checkpoint selection")
            if (decision.get("status") != "selected"
                    or decision.get("learning_seed") != seed
                    or decision.get("test_split_accessed") is not False):
                raise ValueError("residual checkpoint is not validation-eligible")
        elif entry.get("validation_eligible") is not True:
            raise ValueError("primary checkpoint is not validation-eligible")
        checkpoint = _hash_bound_file(
            root, entry.get("path"), entry.get("sha256"), "checkpoint")
        contract = entry.get("checkpoint_contract")
        if (not isinstance(contract, dict)
                or contract.get("controller_family")
                != controller
                or canonical_sha256(contract)
                != entry.get("checkpoint_contract_sha256")):
            raise ValueError("primary checkpoint contract is invalid")
        contract_path = _hash_bound_file(
            root, entry.get("contract_path"),
            entry.get("contract_file_sha256"), "checkpoint contract")
        if _json(contract_path, "checkpoint contract") != contract:
            raise ValueError("primary checkpoint contract file differs")
        run_dir = _inside_directory(
            root, entry.get("source_run_dir"), "checkpoint source run")
        if controller == RESIDUAL_PRIMARY_CONTROLLER:
            if checkpoint.parent != contract_path.parent:
                raise ValueError("residual checkpoint is outside its source run")
        elif (checkpoint != (run_dir / "checkpoint/weights.npz").resolve()
                or contract_path
                != (run_dir / "checkpoint/contract.json").resolve()):
            raise ValueError("primary checkpoint is outside its source run")
        status_path = _hash_bound_file(
            root, str(Path(entry["source_run_dir"]) / "status.json"),
            entry.get("source_status_sha256"), "checkpoint source status")
        status = _json(status_path, "checkpoint source status")
        if (status.get("status") != "complete"
                or status.get("eligible_for_test_evaluation") is not True):
            raise ValueError(
                "primary checkpoint source is not complete and validation-eligible")
        artifacts = entry.get("source_artifacts")
        if controller == RESIDUAL_PRIMARY_CONTROLLER:
            rerun = entry.get("validation_rerun", {})
            rerun_path = _hash_bound_file(
                root, rerun.get("path"), rerun.get("sha256"),
                "residual validation rerun")
            if _json(rerun_path, "residual validation rerun").get(
                    "test_split_accessed") is not False:
                raise ValueError("residual checkpoint validation rerun used test evidence")
        else:
            if (not isinstance(artifacts, dict)
                    or not _REQUIRED_CHECKPOINT_ARTIFACTS.issubset(set(artifacts))
                    or artifacts != status.get("artifact_sha256")):
                raise ValueError("primary checkpoint source artifact binding is invalid")
            for relative, digest in artifacts.items():
                artifact_path = (run_dir / str(relative)).resolve()
                try:
                    artifact_path.relative_to(run_dir)
                except ValueError:
                    raise ValueError("checkpoint source artifact escapes its run")
                _hash_bound_file(
                    root, artifact_path, digest, "checkpoint source artifact")
        validated.append({
            "learning_seed": seed,
            "path": str(checkpoint.relative_to(Path(root).resolve())),
            "sha256": entry["sha256"],
        })
    return validated


def validate_primary_v3_protocol(root, protocol_path, primary=None):
    """Validate the hash-bound primary protocol before any test flow is opened."""
    root = Path(root).resolve()
    path = canonical_primary_protocol_path(root, protocol_path)
    document = _json(path, "primary frozen protocol")
    if primary is not None and document != primary:
        raise ValueError("primary frozen protocol changed while validating")

    # Validation selection is rechecked before opening the held-out case manifest.
    controller = document.get("primary_learned_controller")
    if controller == PRIMARY_LEARNED_CONTROLLER:
        validate_frozen_schedule_selection(root, document.get("selection"))
    elif controller != RESIDUAL_PRIMARY_CONTROLLER:
        raise ValueError("primary V3 controller is unsupported")
    if (document.get("protocol_version") != 1
            or document.get("evidence_namespace") != "haichau_network_v2"):
        raise ValueError("primary V3 frozen protocol identity is invalid")
    seeds = tuple(document.get("confirmatory_learning_seeds", ()))
    required = tuple(document.get("acceptance_rules", {}).get(
        "required_learning_seeds", ()))
    if (controller not in SUPPORTED_PRIMARY_CONTROLLERS
            or seeds != CONFIRMATORY_LEARNING_SEEDS
            or required != CONFIRMATORY_LEARNING_SEEDS
            or 11 in seeds):
        raise ValueError("primary V3 controller/seeds must be exact seeds 12--16")
    checkpoints = _validate_checkpoint_bindings(root, document, controller)
    case_path = _hash_bound_file(
        root, document.get("case_manifest_path"),
        document.get("case_manifest_sha256"), "primary case manifest")
    return {
        "path": path,
        "document": document,
        "case_manifest_path": case_path,
        "checkpoints": checkpoints,
    }


def _load_verified_rows(campaign_dir, runs):
    rows = []
    for run in runs:
        metrics = _json(
            Path(campaign_dir) / "runs" / run["run_id"] / "metrics.json",
            "primary run metrics")
        row = dict(run)
        row.update(metrics)
        rows.append(row)
    return rows


def _expected_summary(protocol, rows):
    rules = protocol["acceptance_rules"]
    summary = aggregate_campaign(
        rows,
        required_learning_seeds=rules["required_learning_seeds"],
        required_regimes=rules.get(
            "required_regimes", ("normal", "am_peak", "pm_peak")),
        minimum_learning_seeds=rules.get("minimum_learning_seeds", 5),
        minimum_demand_units=rules.get("minimum_demand_units", 1),
        normal_point_limit=rules.get("normal_point_limit", 0.0),
        normal_ci_margin_fraction=rules.get("normal_ci_margin_fraction", 0.05),
        peak_ci_upper_limit=rules.get("peak_ci_upper_limit", 0.0),
        completion_degradation_limit=rules.get(
            "completion_degradation_limit", 0.02),
        primary_learned_controller=protocol["primary_learned_controller"],
    )
    return {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
            "evidence_namespace": "haichau_network_v2",
        },
        "summary": summary,
        "acceptance": evaluate_acceptance(summary),
    }


def validate_primary_v3_reference(root, protocol_path, primary=None):
    """Recompute and verify the exact complete primary campaign and summary."""
    validated = validate_primary_v3_protocol(root, protocol_path, primary=primary)
    protocol = validated["document"]
    case_document = _json(
        validated["case_manifest_path"], "primary case manifest")
    bound = bind_frozen_manifest(case_document, protocol)
    expected_runs = expand_runs(
        bound, list(CONFIRMATORY_LEARNING_SEEDS), _primary_controllers(protocol))
    if len(expected_runs) != PRIMARY_RUN_COUNT:
        raise ValueError("primary frozen protocol must expand to exactly 120 runs")

    campaign_path = canonical_primary_release_path(
        root, "campaign-manifest.json")
    campaign_dir = campaign_path.parent
    campaign = _json(campaign_path, "primary campaign manifest")
    expected_campaign = {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": expected_runs,
    }
    if campaign != expected_campaign:
        raise ValueError("primary campaign differs from frozen protocol")
    status = verify_campaign(
        campaign_dir, require_release_provenance=True, project_root=root)
    if status != {"complete": PRIMARY_RUN_COUNT, "total": PRIMARY_RUN_COUNT}:
        raise ValueError("primary campaign is incomplete")

    rows = _load_verified_rows(campaign_dir, expected_runs)
    expected_summary = _expected_summary(protocol, rows)
    summary_path = canonical_primary_release_path(root, "summary.json")
    if _json(summary_path, "primary summary") != expected_summary:
        raise ValueError("primary summary differs from verified campaign")
    return {
        "campaign_manifest_path": campaign_path,
        "campaign_manifest_sha256": _sha256(campaign_path),
        "summary_path": summary_path,
        "summary_sha256": _sha256(summary_path),
        "run_count": PRIMARY_RUN_COUNT,
        "controllers": list(_primary_controllers(protocol)),
        "learning_seeds": list(CONFIRMATORY_LEARNING_SEEDS),
    }
