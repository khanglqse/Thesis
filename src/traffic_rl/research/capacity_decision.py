"""Fail-closed promotion of Hai Chau Stage-D capacity diagnostics."""

import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

from traffic_rl.eval.capacity_calibration import (
    LADDER_SCALES,
    evaluate_run_gates,
    evaluate_stage_gates,
)
from traffic_rl.research.artifacts import canonical_sha256, sha256_file


_NAMESPACE = "haichau_capacity_calibration_diagnostic"
_CONTROLLERS = ("fixed_time_30", "max_pressure_masked_v2")
_SCENARIOS = ("normal", "am_peak", "pm_peak")
_SEEDS = (31, 32)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _json(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError("%s is required" % label)
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError("%s is not valid JSON" % label)


def _inside(root, value, label):
    root = Path(root).resolve()
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s path escapes project root" % label)
    return path


def _verified(root, relative, expected, label):
    if not isinstance(expected, str) or not _SHA256.match(expected):
        raise ValueError("%s sha256 is invalid" % label)
    path = _inside(root, relative, label)
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError("%s sha256 mismatch" % label)
    return path


def _diagnostic_only(payload, label):
    if (payload.get("evidence_namespace") != _NAMESPACE
            or payload.get("eligible_for_release") is not False
            or payload.get("eligible_for_test_evaluation") is not False):
        raise ValueError("%s must retain diagnostic-only provenance" % label)


def _verify_binding(root, campaign, config_path):
    binding = campaign.get("binding")
    if not isinstance(binding, dict):
        raise ValueError("Stage-D binding is required")
    fields = (
        ("source_manifest_path", "source_manifest_sha256", "source manifest"),
        ("training_config_path", "training_config_sha256", "training config"),
        ("generator_config_path", "generator_config_sha256", "generator config"),
        ("network_path", "network_sha256", "network"),
        ("phase_contract_path", "phase_contract_sha256", "phase contract"),
    )
    verified = {}
    for path_key, hash_key, label in fields:
        verified[path_key] = _verified(
            root, binding.get(path_key, ""), binding.get(hash_key), label)
    runtime = binding.get("runtime", {})
    docker = runtime.get("dockerfile", {})
    _verified(root, docker.get("path", ""), docker.get("sha256"),
              "runtime Dockerfile")
    for relative, expected in binding.get("code_sha256", {}).items():
        _verified(root, relative, expected, "bound calibration code")

    config_path = _inside(root, config_path, "generator config")
    if config_path != verified["generator_config_path"]:
        raise ValueError("target config must be the Stage-D bound generator config")
    commit = binding.get("code_commit", "")
    if not re.match(r"^[0-9a-f]{40}$", str(commit)):
        raise ValueError("Stage-D code commit is invalid")
    try:
        subprocess.check_call(
            ["git", "-C", str(Path(root).resolve()), "merge-base", "--is-ancestor",
             commit, "HEAD"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("Stage-D code commit is not an ancestor of HEAD")
    return binding


def _scale_text(value):
    decimal = Decimal(str(value))
    if decimal not in {Decimal(str(item)) for item in LADDER_SCALES}:
        raise ValueError("Stage-D contains an unregistered scale")
    return format(decimal, ".2f")


def _validate_matrix(campaign):
    if campaign.get("stage") != "stage-d":
        raise ValueError("capacity decision requires Stage-D evidence")
    chosen = campaign.get("chosen_scales")
    if not isinstance(chosen, list) or not chosen:
        raise ValueError("Stage-D chosen scales are required")
    scale_texts = [_scale_text(value) for value in chosen]
    if len(scale_texts) != len(set(scale_texts)):
        raise ValueError("Stage-D scales must be unique")
    expected = {
        (scale, controller, scenario, seed)
        for scale in scale_texts
        for controller in _CONTROLLERS
        for scenario in _SCENARIOS
        for seed in _SEEDS
    }
    observed = set()
    run_ids = set()
    for run in campaign.get("runs", []):
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or run_id in run_ids:
            raise ValueError("Stage-D run IDs must be unique")
        run_ids.add(run_id)
        if (run.get("split") != "validation"
                or int(run.get("horizon_steps", -1)) != 3600):
            raise ValueError("Stage-D runs must be 3600-second validation runs")
        scenario = run.get("scenario")
        seed = int(run.get("demand_seed", -1))
        observed.add((_scale_text(run.get("scale")), run.get("controller_id"),
                      scenario, seed))
        if run.get("case_id") != "validation_%s_demand%d" % (scenario, seed):
            raise ValueError("Stage-D case identity is invalid")
    if observed != expected or len(campaign.get("runs", [])) != len(observed):
        raise ValueError("Stage-D must contain the exact Stage-D run matrix")
    return scale_texts


def _validate_result(root, stage_dir, record, validation_cases):
    run_manifest = _verified(
        root, record.get("run_manifest_path", ""),
        record.get("run_manifest_sha256"), "Stage-D run manifest")
    run_payload = _json(run_manifest, "Stage-D run manifest")
    expected_payload = copy.deepcopy(record)
    expected_payload.pop("run_manifest_path", None)
    expected_payload.pop("run_manifest_sha256", None)
    if run_payload != expected_payload:
        raise ValueError("Stage-D run manifest differs from campaign")
    _diagnostic_only(run_payload, "Stage-D run")
    if run_payload.get("split") != "validation":
        raise ValueError("Stage-D run is not validation-only")
    source_case = validation_cases.get(run_payload.get("case_id"))
    if source_case is None or any(
            run_payload.get(field) != source_case.get(field)
            for field in ("source_flow_path", "source_flow_sha256")):
        raise ValueError("Stage-D source flow is not its bound validation case")
    for prefix in ("source_flow", "demand"):
        _verified(root, run_payload.get(prefix + "_path", ""),
                  run_payload.get(prefix + "_sha256"), prefix)

    run_dir = Path(stage_dir) / "runs" / record["run_id"]
    status = _json(run_dir / "status.json", "Stage-D run status")
    if (status.get("status") != "completed"
            or status.get("run_manifest_sha256") != record["run_manifest_sha256"]):
        raise ValueError("Stage-D run status is not completed and bound")
    result_path = run_dir / "result.json"
    expected_hash = status.get("result_sha256")
    if (not result_path.is_file() or not _SHA256.match(str(expected_hash))
            or sha256_file(result_path) != expected_hash):
        raise ValueError("Stage-D result sha256 mismatch")
    result = _json(result_path, "Stage-D result")
    _diagnostic_only(result, "Stage-D result")
    if (result.get("run_manifest_sha256") != record["run_manifest_sha256"]
            or result.get("run") != run_payload):
        raise ValueError("Stage-D result differs from its bound run")
    snapshots = result.get("snapshots")
    if evaluate_run_gates(run_payload, snapshots) != result.get("gates"):
        raise ValueError("Stage-D result gates differ from recomputation")
    if not snapshots or result.get("metrics") != snapshots[-1].get("metrics"):
        raise ValueError("Stage-D terminal metrics differ from terminal snapshot")
    return result, {
        "run_id": record["run_id"],
        "result_path": str(result_path.resolve().relative_to(Path(root).resolve())),
        "result_sha256": expected_hash,
        "run_manifest_sha256": record["run_manifest_sha256"],
    }


def _reference_interval(config, scale_text):
    try:
        base = Decimal(str(config.get("reference_interval_seconds")))
    except Exception:
        raise ValueError("reference_interval_seconds must be decimal")
    if base != Decimal("72"):
        raise ValueError("Stage-D source reference_interval_seconds must equal 72")
    scale = Decimal(scale_text)
    fraction = Fraction(base) / Fraction(scale)
    with localcontext() as context:
        context.prec = 30
        decimal = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    decimal_text = format(decimal, "f")
    if "." in decimal_text:
        decimal_text = decimal_text.rstrip("0").rstrip(".")
    return {
        "base_seconds": "72", "selected_scale": scale_text,
        "formula": "72 / selected_scale",
        "exact_fraction": "%d/%d" % (fraction.numerator, fraction.denominator),
        "yaml_decimal": decimal_text,
    }


def _build_decision(root, stage_dir, config_path):
    root = Path(root).resolve()
    stage_dir = _inside(root, stage_dir, "Stage-D directory")
    campaign_path = stage_dir / "campaign-manifest.json"
    summary_path = stage_dir / "summary.json"
    campaign = _json(campaign_path, "Stage-D campaign")
    summary = _json(summary_path, "Stage-D summary")
    _diagnostic_only(campaign, "Stage-D campaign")
    _diagnostic_only(summary, "Stage-D summary")
    unsigned = copy.deepcopy(campaign)
    identity = unsigned.pop("campaign_identity_sha256", None)
    if identity != canonical_sha256(unsigned):
        raise ValueError("Stage-D campaign identity sha256 mismatch")
    scale_texts = _validate_matrix(campaign)
    binding = _verify_binding(root, campaign, config_path)
    source_manifest = _json(
        _inside(root, binding["source_manifest_path"], "source manifest"),
        "source manifest")
    validation_cases = {}
    for case in source_manifest.get("cases", []):
        if case.get("split") == "validation":
            validation_cases[case.get("case_id")] = {
                "source_flow_path": case.get("flow_path"),
                "source_flow_sha256": case.get("flow_sha256"),
            }
    expected_case_ids = {
        "validation_%s_demand%d" % (scenario, seed)
        for scenario in _SCENARIOS for seed in _SEEDS
    }
    if set(validation_cases) != expected_case_ids:
        raise ValueError("source manifest must contain exactly six validation cases")

    results, records = [], []
    for run in campaign["runs"]:
        result, record = _validate_result(
            root, stage_dir, run, validation_cases)
        results.append(result)
        records.append(record)
    recomputed = evaluate_stage_gates(campaign, results)
    if summary.get("campaign_identity_sha256") != identity:
        raise ValueError("Stage-D summary campaign identity mismatch")
    if summary.get("stage_gates") != recomputed:
        raise ValueError("Stage-D summary differs from recomputed stage gates")
    if (summary.get("status") != "diagnostic_complete"
            or summary.get("completed") != len(campaign["runs"])
            or summary.get("failed") != 0
            or summary.get("total") != len(campaign["runs"])
            or recomputed.get("complete") is not True):
        raise ValueError("Stage-D summary is incomplete")
    passing = [scale for scale in scale_texts if recomputed["scales"].get(
        str(float(Decimal(scale))), {}).get("passed") is True]
    if not passing:
        raise ValueError("Stage-D has no passing registered scale")
    selected = max(passing, key=Decimal)
    if Decimal(str(recomputed.get("highest_passing_scale"))) != Decimal(selected):
        raise ValueError("Stage-D highest-passing scale rule is inconsistent")

    config_path = _inside(root, config_path, "generator config")
    config = yaml.safe_load(config_path.read_text())
    decision = {
        "schema_version": 1,
        "decision_type": "haichau_capacity_scale_promotion",
        "selected_scale": selected,
        "selection_rule": "highest passing scale among registered Stage-D candidates",
        "registered_stage_d_candidates": sorted(scale_texts, key=Decimal),
        "reference_interval": _reference_interval(config, selected),
        "source": {
            "generator_config_path": str(config_path.relative_to(root)),
            "generator_config_sha256": sha256_file(config_path),
            "calibration_code_commit": binding["code_commit"],
            "binding_sha256": canonical_sha256(binding),
            "bound_inputs": {
                key: copy.deepcopy(binding[key])
                for key in (
                    "source_manifest_sha256", "training_config_sha256",
                    "generator_config_sha256", "network_sha256",
                    "phase_contract_sha256", "code_sha256", "runtime")
            },
        },
        "evidence": {
            "stage_d_directory": str(stage_dir.relative_to(root)),
            "campaign_sha256": sha256_file(campaign_path),
            "campaign_identity_sha256": identity,
            "summary_sha256": sha256_file(summary_path),
            "results": sorted(records, key=lambda item: item["run_id"]),
        },
    }
    decision["decision_identity_sha256"] = canonical_sha256(decision)
    return decision


def _clean_checkout(root):
    try:
        status = subprocess.check_output(
            ["git", "-C", str(Path(root).resolve()), "status", "--porcelain=v1",
             "--untracked-files=all"], stderr=subprocess.STDOUT).decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("capacity promotion requires a git checkout")
    if status.strip():
        raise ValueError("capacity promotion requires a clean git checkout")


def _updated_config_bytes(path, decimal_text):
    source = Path(path).read_text()
    pattern = re.compile(r"(?m)^reference_interval_seconds:[^\n]*$")
    if len(pattern.findall(source)) != 1:
        raise ValueError("generator config must contain one reference_interval_seconds")
    updated = pattern.sub("reference_interval_seconds: " + decimal_text, source)
    payload = yaml.safe_load(updated)
    if Decimal(str(payload.get("reference_interval_seconds"))) != Decimal(decimal_text):
        raise ValueError("updated generator config reference interval is ambiguous")
    return updated.encode("utf-8")


def _copy_stage_inputs(root, staged_root, config_path, config_bytes):
    for directory in ("datasets", "docker"):
        source = Path(root) / directory
        if source.is_dir():
            shutil.copytree(source, Path(staged_root) / directory)
    relative = Path(config_path).resolve().relative_to(Path(root).resolve())
    staged_config = Path(staged_root) / relative
    staged_config.parent.mkdir(parents=True, exist_ok=True)
    staged_config.write_bytes(config_bytes)
    return staged_config


def _generated_records(staged_root, manifest):
    staged_root = Path(staged_root).resolve()
    dataset_id = manifest.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id \
            or "/" in dataset_id or ".." in dataset_id:
        raise ValueError("prepared manifest dataset_id is invalid")
    output = staged_root / "results" / dataset_id
    manifest_path = output / "experiment-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("staged preparer did not write experiment manifest")
    loaded = _json(manifest_path, "staged experiment manifest")
    if loaded != manifest:
        raise ValueError("staged experiment manifest differs from preparer return")
    paths = {manifest_path}
    route_record = manifest.get("route_families", {})
    if route_record:
        route_path = _verified(staged_root, route_record.get("path", ""),
                               route_record.get("sha256"), "staged route families")
        paths.add(route_path)
    for case in manifest.get("cases", []):
        flow = _verified(staged_root, case.get("flow_path", ""),
                         case.get("flow_sha256"), "staged generated flow")
        paths.add(flow)
    actual = {path for path in output.rglob("*") if path.is_file()}
    if actual != paths:
        raise ValueError("staged preparer wrote an unexpected generated artifact set")
    return sorted(paths), manifest_path


def _canonical_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _install_transaction(root, replacements):
    root = Path(root).resolve()
    transaction = Path(tempfile.mkdtemp(prefix=".capacity-decision-", dir=str(root)))
    backup = transaction / "backup"
    payload = transaction / "payload"
    installed = []
    try:
        for target, content in replacements:
            target = _inside(root, target, "promotion target")
            relative = target.relative_to(root)
            staged = payload / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
            if target.exists():
                old = backup / relative
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, old)
        for target, _ in replacements:
            target = _inside(root, target, "promotion target")
            relative = target.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(payload / relative, target)
            installed.append(target)
    except Exception:
        for target in reversed(installed):
            relative = target.relative_to(root)
            old = backup / relative
            if old.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(old, target)
            elif target.exists():
                target.unlink()
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)


def apply_capacity_decision(project_root, stage_d_dir, config_path,
                            decision_path=None, new_version=False,
                            validate_only=False, prepare_fn=None):
    """Validate Stage-D evidence and optionally apply its selected scale."""
    root = Path(project_root).resolve()
    config_path = _inside(root, config_path, "generator config")
    decision = _build_decision(root, stage_d_dir, config_path)
    if validate_only:
        return decision
    if new_version is not True:
        raise ValueError("capacity promotion requires explicit --new-version")
    _clean_checkout(root)
    if sha256_file(config_path) != decision["source"]["generator_config_sha256"]:
        raise ValueError("generator config sha256 drifted after validation")
    if decision_path is None:
        decision_path = root / "results/haichau_network_v2/diagnostics/capacity-decision.json"
    decision_path = _inside(root, decision_path, "capacity decision")
    if decision_path.exists():
        raise ValueError("refusing to overwrite existing capacity decision")

    config_bytes = _updated_config_bytes(
        config_path, decision["reference_interval"]["yaml_decimal"])
    preparer = prepare_fn
    if preparer is None:
        from scripts.prepare_haichau_network_v2 import prepare
        preparer = prepare
    with tempfile.TemporaryDirectory(prefix="haichau-capacity-promotion-") as temporary:
        staged_root = Path(temporary).resolve()
        staged_config = _copy_stage_inputs(
            root, staged_root, config_path, config_bytes)
        manifest = preparer(staged_config, root=staged_root, new_version=True)
        if not isinstance(manifest, dict) or manifest.get("protocol_version") != 2:
            raise ValueError("staged preparer returned an invalid protocol manifest")
        staged_config_payload = yaml.safe_load(staged_config.read_text())
        if manifest.get("dataset_id") != staged_config_payload.get("dataset_id"):
            raise ValueError("staged manifest dataset_id differs from generator config")
        if manifest.get("generator_config_sha256") != sha256_file(staged_config):
            raise ValueError("staged manifest is not bound to the updated generator config")
        generated, staged_manifest = _generated_records(staged_root, manifest)
        generated_records = []
        replacements = [(config_path, config_bytes)]
        for source in generated:
            relative = source.relative_to(staged_root)
            content = source.read_bytes()
            replacements.append((root / relative, content))
            generated_records.append({
                "path": str(relative), "sha256": sha256_file(source)})

        applied = copy.deepcopy(decision)
        applied.pop("decision_identity_sha256", None)
        applied["application"] = {
            "new_version": True,
            "generator_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "generated_manifest_path": str(staged_manifest.relative_to(staged_root)),
            "generated_manifest_sha256": sha256_file(staged_manifest),
            "generated_artifacts": sorted(
                generated_records, key=lambda item: item["path"]),
            "preparer_path": "scripts/prepare_haichau_network_v2.py",
            "preparer_sha256": sha256_file(
                root / "scripts/prepare_haichau_network_v2.py"),
            "application_code_commit": subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"]).decode(
                    "ascii").strip(),
        }
        applied["decision_identity_sha256"] = canonical_sha256(applied)
        replacements.append((decision_path, _canonical_bytes(applied)))
        if sha256_file(config_path) != decision["source"]["generator_config_sha256"]:
            raise ValueError("generator config sha256 drifted during staging")
        _install_transaction(root, replacements)
    return applied
