"""Fail-closed per-seed validation selector for final residual runs.

Final confirmation seeds are independent training runs.  Each run remains
ineligible for held-out evaluation until this module has selected one of its
predeclared validation checkpoints and persisted both the selection and a
fresh deterministic replay record.
"""
import copy
import json
import re
import subprocess
from pathlib import Path

import yaml

from traffic_rl.agents.schedule_residual import (
    CRITIC_UNITS, MACRO_FEATURES, MAX_MACROS, POLICY_INPUT_SCHEMA,
    ResidualDDQN)
from traffic_rl.research.artifacts import sha256_file
from traffic_rl.research.residual_release import FINAL_SEEDS, resolve_frozen_final_residual_config
from traffic_rl.research.pilot_residual_selector import (
    _GATES, _RANKING, _SHA256, _baseline_rows,
    _checkpoint_record, _manifest_cases, _quality, _replay_checkpoint,
    _traffic_feature_response, _validate_loaded_network,
    _validate_npz_fields)
from traffic_rl.train.schedule_residual_trainer import validate_config as _validate_final_config
from traffic_rl.train.network_trainer import (
    _tracked_tree_attestation, canonical_json_sha256)

_CHECKPOINTS = (4, 8, 12)
_DECISION_TYPE = "haichau_residual_final_per_seed_selection"
_PROTOCOL = "deterministic_cityflow_final_checkpoint_replay_v1"
_STATUS_REASON = "final must pass preregistered per-seed selector"
_NO_WINNER_REASON = "no validation checkpoint passed preregistered gates"


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _yaml(path, label):
    try:
        value = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is not valid YAML: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a YAML mapping" % label)
    return value


def _inside(root, supplied, label):
    root = Path(root).resolve()
    path = Path(supplied)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root)
        except ValueError:
            raise ValueError("%s must remain inside the project" % label)
    result = (root / path).resolve()
    try:
        result.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    return result


def _record(root, path, label):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _assert_no_test_reference(value, label):
    def contains(item):
        if isinstance(item, dict):
            return any((key not in ("eligible_for_test_evaluation", "test_split_accessed")
                       and contains(key)) or contains(value)
                       for key, value in item.items())
        if isinstance(item, list):
            return any(contains(value) for value in item)
        if isinstance(item, str):
            return any(token == "test" or token.startswith("testcase")
                       for token in re.split(r"[/\s_.-]+", item.lower()) if token)
        return False
    if contains(value):
        raise ValueError("held-out test evidence appears in %s" % label)


def _validate_spec(root, spec_path):
    path = _inside(root, spec_path, "final residual selector specification")
    spec = _yaml(path, "final residual selector specification")
    schema_version = spec.get("schema_version", 1)
    expected = {
        "schema_version": schema_version,
        "decision_type": _DECISION_TYPE,
        "controller_family": "schedule_residual_ddqn",
        "mode": "final",
        "learning_seeds": list(FINAL_SEEDS),
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "ranking": list(_RANKING),
        "no_eligible": "fail_closed",
        "gates": _GATES,
        "run_dir_template": (
            "results/haichau_network_v2/training/final-seed{seed}"
            if schema_version == 1 else
            "results/haichau_network_v2/training/v3c-final-seed{seed}"),
        "selection_filename": "selection.json",
        "validation_rerun_filename": "validation-rerun.json",
    }
    if schema_version not in (1, 2):
        raise ValueError("final residual selector schema version is unsupported")
    for field, expected_value in expected.items():
        if spec.get(field) != expected_value:
            raise ValueError("final residual selector %s differs from preregistration" % field)
    for field in ("manifest", "baseline_tuning_artifact", "pilot_selector_spec",
                  "selected_config"):
        if not isinstance(spec.get(field), str):
            raise ValueError("final residual selector requires %s" % field)
    return path, spec


def _expected_contract(config, manifest, source_tree, baseline, step):
    return {
        "schema_version": 1,
        "controller_family": "schedule_residual_ddqn",
        "feature_dim": len(MACRO_FEATURES), "feature_order": MACRO_FEATURES,
        "hidden_size": config["model"]["hidden"], "max_macros": MAX_MACROS,
        "macro": config["macro"],
        "normal_policy": "exact_executed_fixed25_from_reset",
        "critic_units": CRITIC_UNITS,
        "policy_input_schema": POLICY_INPUT_SCHEMA,
        "peak_policy": "raw_greedy_prevalidated_macro_with_baseline_tie_break",
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "simulation": manifest["simulation"], "normalization": manifest["preprocessing"],
        "code_commit": source_tree["git_commit"], "training_step": step,
        "learning_seed": config["learning_seed"], "mode": "final",
        "training_config_sha256": canonical_json_sha256(config),
        "baseline_tuning_sha256": baseline["tuning_sha256"],
    }


def _validate_status(run_dir, source_tree, required):
    status = _json(run_dir / "status.json", "final residual status")
    if (status.get("status") != "complete"
            or status.get("source_tree") != source_tree
            or status.get("eligible_for_test_evaluation") is not False
            or status.get("reason") != _STATUS_REASON
            or not isinstance(status.get("artifact_sha256"), dict)):
        raise ValueError("final residual status is not pending preregistered selection")
    hashes = status["artifact_sha256"]
    if not set(required).issubset(hashes):
        raise ValueError("final residual status hashes are incomplete")
    for relative, digest in hashes.items():
        candidate = Path(relative)
        if (candidate.is_absolute() or ".." in candidate.parts or not candidate.parts
                or not _SHA256.match(str(digest or ""))):
            raise ValueError("final residual status hash record is invalid")
        artifact = run_dir / candidate
        if not artifact.is_file() or sha256_file(artifact) != digest:
            raise ValueError("final residual artifact hash drift: %s" % relative)
    return status


def _final_config(root, spec, seed):
    config, _ = resolve_frozen_final_residual_config(
        root, spec["pilot_selector_spec"], spec["selected_config"], seed)
    _validate_final_config(config)
    return config


def _validate_run(root, spec, seed, validation_runner):
    config = _final_config(root, spec, seed)
    run_relative = spec["run_dir_template"].format(seed=seed)
    run_dir = _inside(root, run_relative, "final residual run")
    if not run_dir.is_dir():
        raise ValueError("final residual run directory is missing")
    required = ["run-manifest.json", "resolved-config.json", "baseline-tuning.json",
                "learning-curve.json", "summary.json"]
    for step in _CHECKPOINTS:
        required.extend(["validation-step-%04d.json" % step,
                         "checkpoints/step-%04d/contract.json" % step,
                         "checkpoints/step-%04d/weights.npz" % step])
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise ValueError("final residual artifact is missing: " + missing[0])
    run_manifest = _json(run_dir / "run-manifest.json", "final residual run manifest")
    source_tree = run_manifest.get("source_tree")
    if (not isinstance(source_tree, dict)
            or run_manifest.get("code_commit") != source_tree.get("git_commit")):
        raise ValueError("final residual source provenance is incomplete")
    if _tracked_tree_attestation(str(root)) != source_tree:
        raise ValueError("final residual source commit differs from clean selector tree")
    status = _validate_status(run_dir, source_tree, required)
    manifest_path = _inside(root, spec["manifest"], "experiment manifest")
    manifest = _json(manifest_path, "experiment manifest")
    validation, training_ids = _manifest_cases(manifest)
    baseline_path = _inside(root, spec["baseline_tuning_artifact"], "baseline tuning artifact")
    baseline = _json(baseline_path, "baseline tuning artifact")
    tuned_rows = _baseline_rows(baseline, validation, config, manifest)
    manifest_hash = canonical_json_sha256(manifest)
    if (run_manifest.get("controller_family") != "schedule_residual_ddqn"
            or run_manifest.get("mode") != "final"
            or run_manifest.get("learning_seed") != seed
            or run_manifest.get("manifest_sha256") != manifest_hash
            or run_manifest.get("network_sha256") != manifest["network"]["sha256"]
            or run_manifest.get("phase_contract_sha256") != manifest["phase_contract"]["sha256"]
            or run_manifest.get("runtime") != manifest["runtime"]
            or run_manifest.get("training_case_ids") != training_ids
            or run_manifest.get("validation_case_ids") != [case["case_id"] for case in validation]
            or run_manifest.get("test_split_accessed") is not False
            or run_manifest.get("policy_input_schema") != POLICY_INPUT_SCHEMA):
        raise ValueError("final residual run manifest drift")
    resolved = _json(run_dir / "resolved-config.json", "final residual resolved config")
    expected_resolved = copy.deepcopy(config)
    expected_resolved.update({"source_tree": source_tree, "manifest_sha256": manifest_hash,
                              "baseline_tuning_sha256": baseline["tuning_sha256"]})
    if resolved != expected_resolved:
        raise ValueError("final residual resolved config differs from frozen release")
    if _json(run_dir / "baseline-tuning.json", "copied final baseline") != baseline:
        raise ValueError("final residual copied baseline differs from registered source")
    summary = _json(run_dir / "summary.json", "final residual summary")
    if (summary.get("schema_version") != 1
            or summary.get("controller_family") != "schedule_residual_ddqn"
            or summary.get("mode") != "final" or summary.get("learning_seed") != seed
            or summary.get("episodes") != 12
            or summary.get("test_split_accessed") is not False
            or summary.get("selection") != "requires_preregistered_final_residual_selector"):
        raise ValueError("final residual summary contract drift")
    summaries = {item.get("training_step"): item for item in summary.get("checkpoints", [])
                 if isinstance(item, dict)}
    if set(summaries) != set(_CHECKPOINTS):
        raise ValueError("final residual summary checkpoint set drift")
    qualities, bindings, rerun_checkpoints = {}, {}, {}
    prior_baselines, replay_baselines, fixed25 = None, None, {}
    for step in _CHECKPOINTS:
        name = "step-%d" % step
        directory = run_dir / "checkpoints" / ("step-%04d" % step)
        expected_contract = _expected_contract(config, manifest, source_tree, baseline, step)
        if _json(directory / "contract.json", name + " contract") != expected_contract:
            raise ValueError("%s checkpoint contract drift" % name)
        record = _checkpoint_record(run_dir, step)
        artifact_path = run_dir / ("validation-step-%04d.json" % step)
        artifact = _json(artifact_path, name + " validation")
        if (artifact.get("schema_version") != 1
                or artifact.get("controller_family") != "schedule_residual_ddqn"
                or artifact.get("mode") != "final" or artifact.get("learning_seed") != seed
                or artifact.get("training_step") != step
                or artifact.get("checkpoint") != record
                or artifact.get("reload_score_identity") is not True):
            raise ValueError("%s validation identity drift" % name)
        if summaries[step] != {"training_step": step,
                               "validation_path": artifact_path.name,
                               "checkpoint": record}:
            raise ValueError("%s summary checkpoint binding drift" % name)
        _validate_npz_fields(directory / "weights.npz")
        try:
            network = ResidualDDQN.load_bundle(str(directory), expected_contract)
        except (IOError, KeyError, ValueError, TypeError) as exc:
            raise ValueError("%s checkpoint reload failed: %s" % (name, exc))
        _validate_loaded_network(network, config)
        quality, current = _quality(artifact.get("rows"), validation, tuned_rows,
                                    manifest["network"]["agent_ids"], prior_baselines)
        prior_baselines = current
        replay_rows, replay_current = _replay_checkpoint(
            validation_runner, network, step, artifact.get("rows"), validation,
            tuned_rows, manifest["network"]["agent_ids"], replay_baselines, fixed25)
        replay_baselines = replay_current
        quality["traffic_feature_response"] = _traffic_feature_response(network)
        quality["gates"]["checkpoint_traffic_feature_response"] = True
        quality["training_step"] = step
        quality["checkpoint"] = record
        quality["validation"] = _record(root, artifact_path, name + " validation")
        qualities[name] = quality
        bindings[name] = {"checkpoint": record, "validation": quality["validation"]}
        rerun_checkpoints[name] = {"training_step": step, "checkpoint": record,
                                   "rows": replay_rows}
    rerun = {"schema_version": 1, "protocol": _PROTOCOL,
             "source_commit": source_tree["git_commit"],
             "manifest": _record(root, manifest_path, "experiment manifest"),
             "baseline_tuning": _record(root, baseline_path, "baseline tuning artifact"),
             "learning_seed": seed, "checkpoints": rerun_checkpoints,
             "test_split_accessed": False}
    eligible = [(quality["mean_peak_queue_regret_percent"], quality["training_step"], name)
                for name, quality in qualities.items() if quality["eligible"]]
    eligible.sort()
    winner = None
    if eligible:
        _, step, name = eligible[0]
        winner = {"checkpoint": name, "training_step": step,
                  "mean_peak_queue_regret_percent": qualities[name]["mean_peak_queue_regret_percent"],
                  "checkpoint_artifacts": bindings[name]}
    decision = {"schema_version": 1, "decision_type": _DECISION_TYPE,
                "status": "selected" if winner else "rejected", "learning_seed": seed,
                "source_tree": source_tree, "run_manifest": _record(root, run_dir / "run-manifest.json", "final run manifest"),
                "final_status_before_selection": _record(root, run_dir / "status.json", "final run status"),
                "ranking": list(_RANKING), "gates": copy.deepcopy(_GATES),
                "checkpoints": qualities, "winner": winner,
                "test_split_accessed": False}
    return decision, rerun


def _evaluate(root, spec_path, seed, validation_runner):
    root = Path(root).resolve()
    _, spec = _validate_spec(root, spec_path)
    if seed not in FINAL_SEEDS:
        raise ValueError("final residual seed must be one of %s" % (FINAL_SEEDS,))
    return _validate_run(root, spec, seed, validation_runner)


def _run_dir_from_spec(root, spec_path, seed):
    _, spec = _validate_spec(root, spec_path)
    return _inside(root, spec["run_dir_template"].format(seed=seed), "final residual run"), spec


def _transition_status(root, run_dir, prior, decision, rerun_path, selection_path):
    status = copy.deepcopy(prior)
    hashes = status["artifact_sha256"]
    hashes[selection_path.name] = sha256_file(selection_path)
    hashes[rerun_path.name] = sha256_file(rerun_path)
    status["artifact_sha256"] = hashes
    status["selection"] = _record(root, selection_path, "final selection")
    status["validation_rerun"] = _record(root, rerun_path, "final validation rerun")
    if decision["status"] == "selected":
        status["eligible_for_test_evaluation"] = True
        status["reason"] = "validation checkpoint selected by preregistered per-seed selector"
    else:
        status["eligible_for_test_evaluation"] = False
        status["reason"] = _NO_WINNER_REASON
    _write_json(run_dir / "status.json", status)


def select_seed_from_spec(root, spec_path, seed, validation_runner=None):
    """Validate one final seed, persist immutable evidence, then transition status.

    A rejected decision is persisted and returns normally; neither rejection nor
    an exception can make the seed eligible for test evaluation.
    """
    root = Path(root).resolve()
    run_dir, spec = _run_dir_from_spec(root, spec_path, seed)
    selection_path = run_dir / spec["selection_filename"]
    rerun_path = run_dir / spec["validation_rerun_filename"]
    if selection_path.exists() or rerun_path.exists():
        raise ValueError("final residual selector outputs already exist; decisions are immutable")
    prior = _json(run_dir / "status.json", "final residual status")
    decision, rerun = _evaluate(root, spec_path, seed, validation_runner)
    _assert_no_test_reference(decision, "final residual selection")
    _assert_no_test_reference(rerun, "final residual validation rerun")
    _write_json(rerun_path, rerun)
    decision["validation_rerun"] = _record(root, rerun_path, "final validation rerun")
    _write_json(selection_path, decision)
    _transition_status(root, run_dir, prior, decision, rerun_path, selection_path)
    return decision


def validate_registered_spec(root, spec_path):
    """Return the fixed per-seed selection scope for release checks."""
    _, spec = _validate_spec(Path(root).resolve(), spec_path)
    return {"learning_seeds": list(spec["learning_seeds"]),
            "validation_checkpoints": list(spec["validation_checkpoints"]),
            "test_split_accessed": False}
