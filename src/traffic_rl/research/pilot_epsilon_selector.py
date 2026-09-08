"""Fail-closed, validation-only selection between the two registered pilot schedules."""

import copy
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, choose_checkpoint,
    choose_reporting_checkpoint, score_validation, validate_checkpoint_selection)
from traffic_rl.research.artifacts import canonical_sha256, sha256_file
from traffic_rl.train.network_trainer import canonical_json_sha256


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEDULES = ("canonical", "epsilon2160")


def _json(path, label):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))


def _inside(root, relative, label):
    path = Path(relative)
    if path.is_absolute():
        raise ValueError("%s must be repository-relative" % label)
    resolved = (Path(root).resolve() / path).resolve()
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    return resolved


def _git_head(root):
    try:
        value = subprocess.check_output(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            stderr=subprocess.STDOUT).decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("epsilon selection requires a git checkout")
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError("epsilon selection requires a full Git commit")
    return value


def _load_yaml(path, label):
    try:
        value = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is not valid YAML: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a mapping" % label)
    return value


def _epsilon(config, label):
    exploration = config.get("exploration")
    value = exploration.get("epsilon_decay_decisions") if isinstance(exploration, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("%s epsilon_decay_decisions is invalid" % label)
    return value


def _without_epsilon(config):
    normalized = copy.deepcopy(config)
    try:
        del normalized["exploration"]["epsilon_decay_decisions"]
    except (KeyError, TypeError):
        raise ValueError("configuration is missing exploration.epsilon_decay_decisions")
    return normalized


def _validate_spec(root, spec_path):
    supplied = Path(spec_path)
    if supplied.is_absolute():
        try:
            spec_path = supplied.resolve().relative_to(Path(root).resolve())
        except ValueError:
            raise ValueError("selection specification must remain inside the project")
    spec_path = _inside(root, spec_path, "selection specification")
    spec = _load_yaml(spec_path, "selection specification")
    if spec.get("schema_version") != 1:
        raise ValueError("epsilon selection specification schema_version must equal 1")
    if spec.get("decision_type") != "haichau_pilot_epsilon_schedule_selection":
        raise ValueError("epsilon selection specification decision_type is invalid")
    if spec.get("learning_seed") != 11 or spec.get("mode") != "pilot":
        raise ValueError("epsilon selection is fixed to pilot seed 11")
    checkpoints = spec.get("validation_checkpoints")
    if checkpoints != ["step-4", "step-8", "step-12"]:
        raise ValueError("epsilon selection checkpoints must be exactly step-4, step-8, step-12")
    schedules = spec.get("schedules")
    if not isinstance(schedules, dict) or set(schedules) != set(_SCHEDULES):
        raise ValueError("epsilon selection requires canonical and epsilon2160 schedules")
    for name, expected in (("canonical", 10000), ("epsilon2160", 2160)):
        schedule = schedules[name]
        if not isinstance(schedule, dict) or schedule.get("epsilon_decay_decisions") != expected:
            raise ValueError("%s schedule has an invalid epsilon decay" % name)
        for key in ("config", "run_dir"):
            if not isinstance(schedule.get(key), str):
                raise ValueError("%s schedule requires %s" % (name, key))
    for key in ("manifest", "baseline_tuning_artifact", "decision_output",
                "selected_config_output"):
        if not isinstance(spec.get(key), str):
            raise ValueError("epsilon selection specification requires %s" % key)
    return spec_path, spec


def _assert_source_configs(root, spec):
    configs = {}
    records = {}
    for name in _SCHEDULES:
        path = _inside(root, spec["schedules"][name]["config"], name + " config")
        config = _load_yaml(path, name + " config")
        if _epsilon(config, name + " config") != spec["schedules"][name]["epsilon_decay_decisions"]:
            raise ValueError("%s config epsilon decay differs from its specification" % name)
        configs[name] = config
        records[name] = {
            "path": str(path.relative_to(root)), "sha256": sha256_file(path),
            "epsilon_decay_decisions": _epsilon(config, name + " config"),
        }
    if _without_epsilon(configs["canonical"]) != _without_epsilon(configs["epsilon2160"]):
        raise ValueError("pilot configurations differ outside only epsilon_decay_decisions")
    return configs, records


def _validate_tuning(tuning, expected_case_ids):
    if not isinstance(tuning, dict) or tuning.get("schema_version") != 1:
        raise ValueError("baseline tuning schema is invalid")
    unsigned = dict((key, value) for key, value in tuning.items()
                    if key != "tuning_sha256")
    if tuning.get("tuning_sha256") != canonical_json_sha256(unsigned):
        raise ValueError("baseline tuning hash drift")
    candidates = tuning.get("candidates")
    selected = tuning.get("selected")
    if not isinstance(candidates, list) or not isinstance(selected, dict):
        raise ValueError("baseline tuning selection is invalid")
    matches = [candidate for candidate in candidates
               if isinstance(candidate, dict)
               and candidate.get("fixed_green_duration") == selected.get("fixed_green_duration")]
    if len(matches) != 1 or not isinstance(matches[0].get("rows"), list):
        raise ValueError("selected baseline tuning rows are invalid")
    observed = [row.get("case_id") if isinstance(row, dict) else None
                for row in matches[0]["rows"]]
    if set(observed) != set(expected_case_ids) or len(observed) != len(expected_case_ids):
        raise ValueError("baseline tuning must contain exactly the registered validation cases")


def _validate_resolved_config(resolved, source, name):
    if resolved.get("mode") != "pilot" or resolved.get("learning_seed") != 11:
        raise ValueError("%s resolved config does not identify pilot seed 11" % name)
    if resolved.get("run") != source.get("tiers", {}).get("pilot"):
        raise ValueError("%s resolved pilot tier drift" % name)
    for key, source_value in source.items():
        if resolved.get(key) != source_value:
            raise ValueError("%s resolved config drifts from its source config: %s" % (name, key))


def _validate_status_artifacts(run_dir, status, required):
    status_hashes = status.get("artifact_sha256")
    if not isinstance(status_hashes, dict) or not set(required).issubset(status_hashes):
        raise ValueError("pilot status artifact hashes are incomplete")
    for relative, expected in status_hashes.items():
        path = Path(relative)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or not _SHA256.match(str(expected or ""))):
            raise ValueError("pilot status artifact hash record is invalid")
        artifact = run_dir / path
        if not artifact.is_file() or sha256_file(artifact) != expected:
            raise ValueError("pilot status artifact hash drift: %s" % relative)


def _validated_schedule(root, spec, source_config, name, manifest_hash,
                        baseline, baseline_hash, current_commit):
    schedule = spec["schedules"][name]
    run_dir = _inside(root, schedule["run_dir"], name + " run directory")
    if not run_dir.is_dir():
        raise ValueError("%s pilot run directory is missing" % name)
    artifact_names = (
        "status.json", "run-manifest.json", "resolved-config.json",
        "baseline-tuning.json", "baseline-tuning-provenance.json",
        "validation.json", "selection.json",
    )
    artifact_paths = {}
    for artifact in artifact_names:
        path = run_dir / artifact
        if not path.is_file():
            raise ValueError("%s pilot artifact is missing: %s" % (name, artifact))
        artifact_paths[artifact] = path
    status = _json(artifact_paths["status.json"], name + " status")
    if status.get("status") not in ("complete", "ineligible"):
        raise ValueError("%s pilot status is not terminal" % name)
    _validate_status_artifacts(run_dir, status, artifact_names[1:])
    run_manifest = _json(artifact_paths["run-manifest.json"], name + " run manifest")
    if (run_manifest.get("learning_seed") != 11
            or run_manifest.get("controller_id") != "neighbor_phase_ddqn"
            or run_manifest.get("mode") != "pilot"
            or run_manifest.get("manifest_sha256") != manifest_hash
            or run_manifest.get("code_commit") != current_commit):
        raise ValueError("%s pilot provenance does not match the registered inputs" % name)
    resolved = _json(artifact_paths["resolved-config.json"], name + " resolved config")
    _validate_resolved_config(resolved, source_config, name)
    if (resolved.get("manifest_sha256") != manifest_hash
            or resolved.get("baseline_tuning_sha256") != baseline["tuning_sha256"]):
        raise ValueError("%s resolved input identity drift" % name)
    copied = _json(artifact_paths["baseline-tuning.json"], name + " copied tuning")
    _validate_tuning(copied, spec["validation_checkpoints"] and _expected_cases(baseline))
    if copied != baseline:
        raise ValueError("%s did not use the registered baseline tuning artifact" % name)
    provenance = _json(artifact_paths["baseline-tuning-provenance.json"], name + " baseline provenance")
    if (provenance.get("source_artifact_sha256") != baseline_hash
            or provenance.get("copied_artifact_sha256") != sha256_file(artifact_paths["baseline-tuning.json"])
            or provenance.get("tuning_sha256") != baseline["tuning_sha256"]):
        raise ValueError("%s baseline provenance drift" % name)
    validation = _json(artifact_paths["validation.json"], name + " validation")
    selection = _json(artifact_paths["selection.json"], name + " selection")
    expected_cases = _expected_cases(baseline)
    if set(validation) != set(spec["validation_checkpoints"]):
        raise ValueError("%s validation checkpoints differ from the preregistration" % name)
    scores = {}
    for checkpoint in spec["validation_checkpoints"]:
        evidence = validation.get(checkpoint)
        if not isinstance(evidence, dict) or not isinstance(evidence.get("rows"), list):
            raise ValueError("%s validation evidence is malformed" % name)
        rows = evidence["rows"]
        case_ids = [row.get("case_id") if isinstance(row, dict) else None for row in rows]
        if len(case_ids) != len(expected_cases) or set(case_ids) != set(expected_cases):
            raise ValueError("%s validation evidence is not exactly the registered validation set" % name)
        _assert_fixed_baseline_rows(rows, baseline)
        score = score_validation(rows)
        reported = evidence.get("score")
        if not isinstance(reported, dict) or reported.get("training_step") not in (4, 8, 12):
            raise ValueError("%s validation score is malformed" % name)
        score["training_step"] = reported["training_step"]
        if score != reported:
            raise ValueError("%s validation score was not recomputed from its rows" % name)
        scores[checkpoint] = score
    if selection.get("eligibility_policy") != CHECKPOINT_ELIGIBILITY_POLICY:
        raise ValueError("%s selection eligibility policy drift" % name)
    try:
        selected = choose_checkpoint(scores)
        eligible = True
    except ValueError:
        selected = choose_reporting_checkpoint(scores)
        eligible = False
    if selection.get("selected_checkpoint") != selected or selection.get("score") != scores[selected]:
        raise ValueError("%s selection does not follow the registered checkpoint tuple" % name)
    if eligible:
        validate_checkpoint_selection(validation, selection, copied, expected_cases)
    elif (selection.get("status") != "ineligible_negative_result"
          or selection.get("eligible_for_test_evaluation") is not False):
        raise ValueError("%s ineligible selection status is invalid" % name)
    expected_status = "complete" if eligible else "ineligible"
    if (status.get("status") != expected_status
            or status.get("eligible_for_test_evaluation") is not eligible):
        raise ValueError("%s pilot status eligibility drift" % name)
    return {
        "eligible": eligible,
        "selected_checkpoint": selected,
        "rank_tuple": ([scores[selected]["worst_regret"], scores[selected]["mean_regret"],
                        scores[selected]["training_step"]] if eligible else None),
        "selection_status": selection.get("status"),
        "score": scores[selected],
        "run_dir": str(run_dir.relative_to(root)),
        "artifacts": dict((artifact, sha256_file(path))
                          for artifact, path in sorted(artifact_paths.items())),
    }


def _expected_cases(baseline):
    selected = baseline["selected"]["fixed_green_duration"]
    candidate = next(value for value in baseline["candidates"]
                     if value["fixed_green_duration"] == selected)
    return [row["case_id"] for row in candidate["rows"]]


def _assert_fixed_baseline_rows(rows, baseline):
    selected = baseline["selected"]["fixed_green_duration"]
    candidate = next(value for value in baseline["candidates"]
                     if value["fixed_green_duration"] == selected)
    by_case = dict((row["case_id"], row) for row in candidate["rows"])
    for row in rows:
        fixed = by_case[row["case_id"]]
        expected = {
            "scenario": fixed.get("scenario"),
            "baseline_queue": fixed.get("queue_integral_vehicle_seconds"),
            "baseline_completion": fixed.get("completion_rate"),
            "baseline_insertion": fixed.get("insertion_rate"),
        }
        if any(row.get(field) != value for field, value in expected.items()):
            raise ValueError("fixed baseline evidence drift")


def _sha256_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def _write_outputs(selected_path, selected_bytes, decision_path, decision):
    if selected_path.exists() or decision_path.exists():
        existing = selected_path if selected_path.exists() else decision_path
        raise ValueError("refusing to overwrite existing selection output: %s" % existing)
    decision_bytes = (json.dumps(decision, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = []
    try:
        for path, payload in ((selected_path, selected_bytes),
                              (decision_path, decision_bytes)):
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, staged = tempfile.mkstemp(
                prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            staged = Path(staged)
            if sha256_file(staged) != _sha256_bytes(payload):
                raise ValueError("staged selection output hash drift")
            temporary.append((path, staged, payload))
        for path, staged, payload in temporary:
            os.replace(str(staged), str(path))
            if sha256_file(path) != _sha256_bytes(payload):
                raise ValueError("written selection output hash drift")
    finally:
        for _, staged, _ in temporary:
            if staged.exists():
                staged.unlink()


def _selection_artifact(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is invalid" % label)
    path = record.get("path")
    expected = record.get("sha256")
    if not isinstance(path, str) or not _SHA256.match(str(expected or "")):
        raise ValueError("%s record is incomplete" % label)
    artifact = _inside(root, path, label)
    if not artifact.is_file() or sha256_file(artifact) != expected:
        raise ValueError("%s hash drift" % label)
    return artifact


def _validate_pilot_artifacts(root, schedule, name):
    if not isinstance(schedule, dict):
        raise ValueError("%s pilot evidence is incomplete" % name)
    run_dir = _inside(root, schedule.get("run_dir"), name + " pilot run directory")
    artifacts = schedule.get("artifacts")
    if not run_dir.is_dir() or not isinstance(artifacts, dict):
        raise ValueError("%s pilot evidence is incomplete" % name)
    required = {
        "status.json", "run-manifest.json", "resolved-config.json",
        "baseline-tuning.json", "baseline-tuning-provenance.json",
        "validation.json", "selection.json",
    }
    if not required.issubset(artifacts):
        raise ValueError("%s pilot evidence is incomplete" % name)
    for relative, expected in artifacts.items():
        candidate = Path(relative)
        if (candidate.is_absolute() or ".." in candidate.parts or not candidate.parts
                or not _SHA256.match(str(expected or ""))):
            raise ValueError("%s pilot artifact record is invalid" % name)
        artifact = run_dir / candidate
        if not artifact.is_file() or sha256_file(artifact) != expected:
            raise ValueError("%s pilot artifact hash drift: %s" % (name, relative))


def validate_final_selection(root, decision_path):
    """Return one hash-checked pilot decision and final selected configuration.

    This intentionally validates only immutable pilot evidence already recorded in
    the selector output.  It is safe to run after final training, whose commit is
    expected to be newer than the pilot-selection commit.
    """
    root = Path(root).resolve()
    if not isinstance(decision_path, (str, Path)):
        raise ValueError("pilot epsilon selection path is required")
    supplied = Path(decision_path)
    if supplied.is_absolute():
        try:
            decision_path = supplied.resolve().relative_to(root)
        except ValueError:
            raise ValueError("pilot epsilon selection must remain inside the project")
    decision_path = _inside(root, decision_path, "pilot epsilon selection")
    decision = _json(decision_path, "pilot epsilon selection")
    if (decision.get("schema_version") != 1
            or decision.get("decision_type")
            != "haichau_pilot_epsilon_schedule_selection"):
        raise ValueError("pilot epsilon selection schema is invalid")
    identity = decision.get("decision_identity_sha256")
    unsigned = dict(decision)
    unsigned.pop("decision_identity_sha256", None)
    if (not _SHA256.match(str(identity or ""))
            or identity != canonical_sha256(unsigned)):
        raise ValueError("pilot epsilon selection identity hash drift")
    inputs = decision.get("inputs")
    if (not isinstance(inputs, dict)
            or not re.fullmatch(r"[0-9a-f]{40,64}",
                                str(inputs.get("code_commit") or ""))):
        raise ValueError("pilot epsilon selection inputs are invalid")
    manifest = _selection_artifact(root, inputs.get("manifest"), "pilot manifest")
    if not isinstance(_json(manifest, "pilot manifest"), dict):
        raise ValueError("pilot manifest is invalid")
    _selection_artifact(root, inputs.get("baseline_tuning"), "pilot baseline tuning")
    configs = inputs.get("configs")
    schedules = decision.get("schedules")
    winner = decision.get("winner")
    selected = decision.get("selected_config")
    if (not isinstance(configs, dict) or set(configs) != set(_SCHEDULES)
            or not isinstance(schedules, dict) or set(schedules) != set(_SCHEDULES)
            or not isinstance(winner, dict) or not isinstance(selected, dict)):
        raise ValueError("pilot epsilon selection schedule records are invalid")
    winner_name = winner.get("schedule")
    if winner_name not in _SCHEDULES or winner.get("config") != configs[winner_name]:
        raise ValueError("pilot epsilon selection winner is invalid")
    for name in _SCHEDULES:
        source = _selection_artifact(root, configs[name], name + " source config")
        source_config = _load_yaml(source, name + " source config")
        if _epsilon(source_config, name + " source config") != configs[name].get(
                "epsilon_decay_decisions"):
            raise ValueError("%s source config epsilon drift" % name)
        _validate_pilot_artifacts(root, schedules[name], name)
    selected_path = _selection_artifact(root, selected, "selected config")
    selected_config = _load_yaml(selected_path, "selected config")
    winner_path = _selection_artifact(root, configs[winner_name], "winning source config")
    winner_config = _load_yaml(winner_path, "winning source config")
    if selected_config != winner_config:
        raise ValueError("selected config differs from winning pilot config")
    return {
        "path": str(decision_path.relative_to(root)),
        "sha256": sha256_file(decision_path),
        "decision_identity_sha256": identity,
        "winner": {
            "schedule": winner_name,
            "config": dict(configs[winner_name]),
        },
        "selected_config": {
            "path": str(selected_path.relative_to(root)),
            "sha256": sha256_file(selected_path),
            "config": selected_config,
        },
    }


def validate_final_resolved_config(resolved, selected_config, learning_seed):
    """Require a final run to retain every selected pilot configuration field."""
    if not isinstance(resolved, dict) or not isinstance(selected_config, dict):
        raise ValueError("final resolved training configuration is invalid")
    if (resolved.get("mode") != "final"
            or resolved.get("learning_seed") != learning_seed):
        raise ValueError("final resolved training configuration identity drift")
    final_tier = selected_config.get("tiers", {}).get("final")
    if not isinstance(final_tier, dict) or resolved.get("run") != final_tier:
        raise ValueError("final resolved training tier drift")
    for key, value in selected_config.items():
        if resolved.get(key) != value:
            raise ValueError("final resolved training configuration differs from selected config")


def select_from_spec(root, spec_path):
    """Select one final epsilon configuration using only registered validation evidence."""
    root = Path(root).resolve()
    spec_path, spec = _validate_spec(root, spec_path)
    configs, config_records = _assert_source_configs(root, spec)
    manifest_path = _inside(root, spec["manifest"], "experiment manifest")
    baseline_path = _inside(root, spec["baseline_tuning_artifact"], "baseline tuning")
    if not manifest_path.is_file() or not baseline_path.is_file():
        raise ValueError("registered manifest and baseline tuning artifact are required")
    actual_manifest = _json(manifest_path, "experiment manifest")
    actual_manifest_hash = canonical_json_sha256(actual_manifest)
    baseline = _json(baseline_path, "registered baseline tuning")
    expected_cases = _expected_cases(baseline) if isinstance(baseline, dict) else []
    _validate_tuning(baseline, expected_cases)
    manifest_hash = baseline.get("binding", {}).get("manifest_sha256")
    if not _SHA256.match(str(manifest_hash or "")):
        raise ValueError("baseline tuning must bind the experiment manifest identity")
    if actual_manifest_hash != manifest_hash:
        raise ValueError("experiment manifest identity differs from baseline tuning binding")
    baseline_hash = sha256_file(baseline_path)
    current_commit = _git_head(root)
    outcomes = dict((name, _validated_schedule(
        root, spec, configs[name], name, manifest_hash, baseline, baseline_hash,
        current_commit)) for name in _SCHEDULES)
    canonical = outcomes["canonical"]
    fast = outcomes["epsilon2160"]
    if not canonical["eligible"] and not fast["eligible"]:
        raise ValueError("neither pilot is validation-eligible; selection fails closed")
    if not canonical["eligible"]:
        winner = "epsilon2160"
    elif fast["eligible"] and tuple(fast["rank_tuple"]) < tuple(canonical["rank_tuple"]):
        winner = "epsilon2160"
    else:
        winner = "canonical"
    decision_path = _inside(root, spec["decision_output"], "decision output")
    selected_config_path = _inside(root, spec["selected_config_output"], "selected config output")
    selected_config_bytes = yaml.safe_dump(configs[winner], sort_keys=True).encode("utf-8")
    decision = {
        "schema_version": 1,
        "decision_type": spec["decision_type"],
        "selection_rule": (
            "select the sole eligible schedule; when both are eligible epsilon2160 "
            "wins only when strictly lexicographically better by worst normalized "
            "queue regret, mean normalized queue regret, then earlier training step; "
            "ties retain canonical; neither eligible fails closed"),
        "specification": {"path": str(spec_path.relative_to(root)),
                          "sha256": sha256_file(spec_path)},
        "inputs": {
            "code_commit": current_commit,
            "manifest": {"path": str(manifest_path.relative_to(root)),
                         "sha256": sha256_file(manifest_path),
                         "canonical_json_sha256": actual_manifest_hash},
            "baseline_tuning": {"path": str(baseline_path.relative_to(root)),
                               "sha256": baseline_hash,
                               "tuning_sha256": baseline["tuning_sha256"]},
            "configs": config_records,
        },
        "validation_checkpoints": list(spec["validation_checkpoints"]),
        "schedules": outcomes,
        "winner": {
            "schedule": winner,
            "selected_checkpoint": outcomes[winner]["selected_checkpoint"],
            "rank_tuple": outcomes[winner]["rank_tuple"],
            "config": config_records[winner],
        },
        "selected_config": {
            "path": str(selected_config_path.relative_to(root)),
            "sha256": _sha256_bytes(selected_config_bytes),
        },
    }
    decision["decision_identity_sha256"] = canonical_sha256(decision)
    _write_outputs(selected_config_path, selected_config_bytes, decision_path, decision)
    return decision
