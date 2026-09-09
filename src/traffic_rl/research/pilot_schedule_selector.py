"""Fail-closed selection between schedule-aware behavior-cloning pilot arms.

The selector consumes only hash-bound pilot evidence from the training and
validation splits.  It does not read the locked test split.
"""

import copy
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, choose_checkpoint,
    choose_reporting_checkpoint, score_validation,
    validate_checkpoint_selection)
from traffic_rl.research.artifacts import canonical_sha256, sha256_file
from traffic_rl.sim.phase_encoder import SCHEDULE_CONTEXT_FEATURES
from traffic_rl.train.network_trainer import (
    _tracked_tree_attestation, canonical_json_sha256)


_ARMS = ("schedule_bc_rehearsal", "schedule_bc_no_rehearsal")
_CHECKPOINTS = ("step-4", "step-8", "step-12")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PRIMARY_LEARNED_CONTROLLER = "neighbor_phase_ddqn"
PILOT_LEARNING_SEED = 11
CONFIRMATORY_LEARNING_SEEDS = (12, 13, 14, 15, 16)
FINAL_TIER = {"episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
FINAL_CHECKPOINTS = _CHECKPOINTS


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


def _inside(root, relative, label):
    path = Path(relative)
    if path.is_absolute():
        raise ValueError("%s must be repository-relative" % label)
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    return resolved


def _git_head(root):
    try:
        value = subprocess.check_output(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            stderr=subprocess.STDOUT).decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("schedule-rehearsal selection requires a git checkout")
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError("schedule-rehearsal selection requires a full Git commit")
    return value


def _record(root, path, label):
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError("%s is missing" % label)
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def _artifact(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is invalid" % label)
    path = record.get("path")
    digest = record.get("sha256")
    if not isinstance(path, str) or not _SHA256.match(str(digest or "")):
        raise ValueError("%s record is incomplete" % label)
    candidate = _inside(root, path, label)
    if not candidate.is_file() or sha256_file(candidate) != digest:
        raise ValueError("%s hash drift" % label)
    return candidate


def _number(value, label, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError("%s must be numeric" % label)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be numeric" % label)
    if not math.isfinite(number):
        raise ValueError("%s must be finite" % label)
    if minimum is not None and number < minimum:
        raise ValueError("%s is below its minimum" % label)
    if maximum is not None and number > maximum:
        raise ValueError("%s exceeds its maximum" % label)
    return number


def _contains_test_reference(value):
    if isinstance(value, dict):
        return any(
            ((key != "eligible_for_test_evaluation"
              and _contains_test_reference(key))
             or _contains_test_reference(item))
            for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_test_reference(item) for item in value)
    if isinstance(value, str):
        tokens = [token for token in re.split(
            r"[/\s_.-]+", value.lower().replace("\\", "/")) if token]
        return any(token == "test" or token.startswith("testcase")
                   for token in tokens)
    return False


def _reject_test_evidence(value, label):
    if _contains_test_reference(value):
        raise ValueError("held-out test evidence appears in %s" % label)


def _validation_case_contract(manifest):
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("experiment manifest cases are invalid")
    validation = [case for case in cases if isinstance(case, dict)
                  and case.get("split") == "validation"]
    records = {}
    for case in validation:
        case_id = case.get("case_id")
        scenario = case.get("scenario")
        if (not isinstance(case_id, str) or not case_id
                or scenario not in ("normal", "am_peak", "pm_peak")
                or case_id in records):
            raise ValueError("manifest validation case identity is invalid")
        records[case_id] = scenario
    if len(records) != 6:
        raise ValueError("manifest must contain exactly six validation cases")
    return records


def _validate_baseline_partition(baseline_rows, manifest):
    registered = _validation_case_contract(manifest)
    observed = {}
    for row in baseline_rows:
        if not isinstance(row, dict):
            raise ValueError("baseline validation row is invalid")
        case_id = row.get("case_id")
        scenario = row.get("scenario")
        if case_id in observed or registered.get(case_id) != scenario:
            raise ValueError("baseline tuning uses a non-validation case")
        observed[case_id] = scenario
    if observed != registered:
        raise ValueError("baseline tuning does not use the exact validation split")


def _validate_spec(root, spec_path):
    supplied = Path(spec_path)
    if supplied.is_absolute():
        try:
            spec_path = supplied.resolve().relative_to(Path(root).resolve())
        except ValueError:
            raise ValueError("schedule-rehearsal selection specification must remain inside the project")
    path = _inside(root, spec_path, "schedule-rehearsal selection specification")
    spec = _yaml(path, "schedule-rehearsal selection specification")
    if spec.get("schema_version") != 1:
        raise ValueError("schedule-rehearsal selection specification schema_version must equal 1")
    if spec.get("decision_type") != "haichau_pilot_schedule_rehearsal_selection":
        raise ValueError("schedule-rehearsal selection decision_type is invalid")
    if spec.get("learning_seed") != 11 or spec.get("mode") != "pilot":
        raise ValueError("schedule-rehearsal selection is fixed to pilot seed 11")
    if tuple(spec.get("validation_checkpoints", ())) != _CHECKPOINTS:
        raise ValueError("schedule-rehearsal selection checkpoints must be exactly step-4, step-8, step-12")
    arms = spec.get("arms")
    if not isinstance(arms, dict) or set(arms) != set(_ARMS):
        raise ValueError("schedule selection requires rehearsal and no-rehearsal arms")
    for arm in _ARMS:
        value = arms[arm]
        if not isinstance(value, dict):
            raise ValueError("%s arm specification is invalid" % arm)
        for field in ("config", "run_dir"):
            if not isinstance(value.get(field), str):
                raise ValueError("%s arm requires %s" % (arm, field))
    for field in ("manifest", "baseline_tuning_artifact", "decision_output",
                  "selected_config_output"):
        if not isinstance(spec.get(field), str):
            raise ValueError("schedule-rehearsal selection specification requires %s" % field)
    return path, spec


def _behavior_prior(config, arm):
    prior = config.get("behavior_prior")
    if not isinstance(prior, dict):
        raise ValueError("%s config requires behavior_prior" % arm)
    if prior.get("type") != "fixed_time_behavior_cloning":
        raise ValueError("%s behavior_prior type is invalid" % arm)
    for field in ("reference_probability_start", "reference_probability_end",
                  "random_probability_start", "random_probability_end",
                  "minimum_validation_reference_disagreement_rate"):
        _number(prior.get(field), "%s behavior_prior.%s" % (arm, field), 0.0, 1.0)
    if int(prior.get("bc_epochs", 0)) <= 0:
        raise ValueError("%s behavior_prior.bc_epochs must be positive" % arm)
    if prior.get("pre_rl_validation") is not True:
        raise ValueError("%s must enable the step-0 diagnostic" % arm)
    rehearsal = prior.get("rehearsal")
    if (not isinstance(rehearsal, dict)
            or not isinstance(rehearsal.get("enabled"), bool)
            or rehearsal.get("type") != "behavior_clone"):
        raise ValueError("%s behavior rehearsal contract is invalid" % arm)
    for field in ("every_td_updates", "batch_size"):
        value = rehearsal.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("%s behavior rehearsal %s is invalid" % (arm, field))
    return prior


def _without_rehearsal_toggle(config):
    value = copy.deepcopy(config)
    try:
        del value["behavior_prior"]["rehearsal"]["enabled"]
    except (KeyError, TypeError):
        raise ValueError("schedule arm config lacks rehearsal toggle")
    return value


def _source_configs(root, spec):
    configs, records = {}, {}
    for arm in _ARMS:
        path = _inside(root, spec["arms"][arm]["config"], arm + " config")
        config = _yaml(path, arm + " config")
        prior = _behavior_prior(config, arm)
        reference_start = _number(prior["reference_probability_start"],
                                  arm + " reference start", 0.0, 1.0)
        reference_end = _number(prior["reference_probability_end"],
                                arm + " reference end", 0.0, 1.0)
        if reference_start != 0.0 or reference_end != 0.0:
            raise ValueError("v3 schedule arms must not execute reference actions")
        observation = config.get("observation")
        cycle = observation.get("global_cycle", {}) if isinstance(
            observation, dict) else {}
        if (not isinstance(observation, dict)
                or config.get("model", {}).get("feature_dim") != 15
                or observation.get("schema_version") != 3
                or observation.get("type") !=
                "phase_rows_fixed_schedule_context"
                or observation.get("phase_row_identity") != "cycle_fraction"
                or cycle.get("encoding") != "sin_cos"
                or cycle.get("green_duration_seconds") != 25
                or cycle.get("period") !=
                "green_duration_times_selectable_green_count"):
            raise ValueError("%s schedule observation contract is invalid" % arm)
        expected_enabled = arm == "schedule_bc_rehearsal"
        if prior["rehearsal"]["enabled"] is not expected_enabled:
            raise ValueError("%s rehearsal arm toggle is invalid" % arm)
        expected_final = {
            "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
        if config.get("tiers", {}).get("final") != expected_final:
            raise ValueError(
                "%s final tier must match the preregistered five-seed recipe" % arm)
        configs[arm] = config
        record = _record(root, path, arm + " config")
        record["behavior_prior"] = copy.deepcopy(prior)
        records[arm] = record
    if (_without_rehearsal_toggle(configs["schedule_bc_rehearsal"])
            != _without_rehearsal_toggle(
                configs["schedule_bc_no_rehearsal"])):
        raise ValueError("schedule arm configs differ outside rehearsal toggle")
    return configs, records


def validate_registered_configs(root, spec_path):
    """Validate and summarize the immutable schedule-arm config relation."""
    root = Path(root).resolve()
    _, spec = _validate_spec(root, spec_path)
    configs, _ = _source_configs(root, spec)
    return dict((arm, {
        "feature_dim": config["model"]["feature_dim"],
        "rehearsal_enabled": config["behavior_prior"]["rehearsal"]["enabled"],
        "final_tier": copy.deepcopy(config["tiers"]["final"]),
    }) for arm, config in configs.items())


def _expected_cases(baseline):
    selected = baseline.get("selected", {}).get("fixed_green_duration")
    candidates = baseline.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("baseline tuning candidates are invalid")
    matched = [candidate for candidate in candidates
               if isinstance(candidate, dict)
               and candidate.get("fixed_green_duration") == selected]
    if len(matched) != 1 or not isinstance(matched[0].get("rows"), list):
        raise ValueError("baseline selected rows are invalid")
    return matched[0]["rows"]


def _validate_baseline(baseline):
    _reject_test_evidence(baseline, "baseline tuning")
    if (baseline.get("schema_version") != 1
            or baseline.get("method") != "validation_grid_search"):
        raise ValueError("baseline tuning schema is invalid")
    unsigned = dict((key, value) for key, value in baseline.items()
                    if key != "tuning_sha256")
    if baseline.get("tuning_sha256") != canonical_json_sha256(unsigned):
        raise ValueError("baseline tuning hash drift")
    rows = _expected_cases(baseline)
    if len(rows) != 6:
        raise ValueError("baseline tuning must contain six validation rows")
    ids = [row.get("case_id") if isinstance(row, dict) else None for row in rows]
    if len(set(ids)) != 6 or any(not item for item in ids):
        raise ValueError("baseline validation case identities are invalid")
    return rows


def _manifest_train_cases(root, manifest):
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("experiment manifest cases are invalid")
    train = [case for case in cases if isinstance(case, dict)
             and case.get("split") == "train"]
    if not train:
        raise ValueError("experiment manifest has no train cases")
    ids = []
    hashes = {}
    for case in train:
        case_id = case.get("case_id")
        digest = case.get("flow_sha256")
        path = case.get("flow_path")
        if (not isinstance(case_id, str) or not _SHA256.match(str(digest or ""))
                or not isinstance(path, str)):
            raise ValueError("manifest train case identity is invalid")
        flow = _inside(root, path, "manifest train flow")
        if not flow.is_file() or sha256_file(flow) != digest:
            raise ValueError("manifest train flow hash drift")
        if case_id in hashes:
            raise ValueError("manifest train case is duplicated")
        ids.append(case_id)
        hashes[case_id] = digest
    return ids, hashes


def _validate_behavior_source(root, artifact_path, manifest):
    evidence = _json(artifact_path, "behavior prior evidence")
    _reject_test_evidence(evidence, "behavior training evidence")
    expected_ids, expected_hashes = _manifest_train_cases(root, manifest)
    if evidence.get("source_split") != "train":
        raise ValueError("behavior training source must be the train split")
    if evidence.get("source_case_ids") != expected_ids:
        raise ValueError("behavior training source cases differ from manifest train cases")
    labels = _number(evidence.get("switch_eligible_labels"),
                     "switch-eligible behavior labels", 1.0)
    if (evidence.get("schema_version") != 2
            or evidence.get("loss_name") != "conditional_cross_entropy"
            or evidence.get("labels") != labels
            or _number(evidence.get("conditional_cross_entropy"),
                       "conditional behavior cross entropy", 0.0) < 0.0
            or not 0.0 <= _number(evidence.get("top1_agreement"),
                                  "behavior top1 agreement") <= 1.0):
        raise ValueError("conditional behavior training evidence is invalid")
    rows = evidence.get("train_cases")
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ValueError("behavior training source evidence is incomplete")
    observed = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("behavior training source record is invalid")
        case_id = row.get("case_id")
        if case_id in observed or row.get("flow_sha256") != expected_hashes.get(case_id):
            raise ValueError("behavior training source hash drift")
        observed.append(case_id)
    if observed != expected_ids:
        raise ValueError("behavior training source cases are not exact")


def _validate_status(run_dir, required, label):
    status = _json(run_dir / "status.json", label + " status")
    _reject_test_evidence(status, label + " status")
    hashes = status.get("artifact_sha256")
    if not isinstance(hashes, dict) or not set(required).issubset(hashes):
        raise ValueError("%s status artifact hashes are incomplete" % label)
    for relative, expected in hashes.items():
        candidate = Path(relative)
        if (candidate.is_absolute() or ".." in candidate.parts or not candidate.parts
                or not _SHA256.match(str(expected or ""))):
            raise ValueError("%s status artifact hash record is invalid" % label)
        path = run_dir / candidate
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError("%s pilot artifact hash drift: %s" % (label, relative))
    return status


def _baseline_rows(rows):
    return dict((row["case_id"], row) for row in rows)


def validation_quality(rows, baseline_rows, minimum_disagreement):
    case_ids = [row.get("case_id") if isinstance(row, dict) else None for row in rows]
    if len(rows) != 6 or set(case_ids) != set(baseline_rows):
        raise ValueError("validation evidence must contain exactly six registered rows")
    eligible, disagreements = 0, 0
    normal_gate = []
    per_case_safety = []
    for row in rows:
        baseline = baseline_rows[row["case_id"]]
        expected = {
            "scenario": baseline.get("scenario"),
            "baseline_queue": baseline.get("queue_integral_vehicle_seconds"),
            "baseline_completion": baseline.get("completion_rate"),
            "baseline_insertion": baseline.get("insertion_rate"),
        }
        if any(row.get(field) != value for field, value in expected.items()):
            raise ValueError("validation baseline evidence drift")
        audit = row.get("policy_audit")
        if not isinstance(audit, dict) or audit.get("evaluation_policy") != "raw_ddqn_greedy":
            raise ValueError("validation evaluation policy must be raw_ddqn_greedy")
        denominator = _number(audit.get("switch_eligible_decisions"),
                              "switch-eligible disagreement denominator", 1.0)
        count = _number(audit.get("switch_eligible_reference_disagreements"),
                        "switch-eligible reference disagreements", 0.0,
                        denominator)
        reported = _number(
            audit.get("switch_eligible_reference_disagreement_rate"),
            "switch-eligible reference disagreement rate", 0.0, 1.0)
        if abs(reported - count / denominator) > 1e-12:
            raise ValueError("reference disagreement rate does not match its count")
        eligible += int(denominator)
        disagreements += int(count)
        completion = _number(row.get("candidate_completion"),
                             "candidate completion", 0.0, 1.0)
        insertion = _number(row.get("candidate_insertion"),
                            "candidate insertion", 0.0, 1.0)
        safety_passed = bool(
            float(row["baseline_completion"]) - completion <= 0.02
            and float(row["baseline_insertion"]) - insertion <= 0.02)
        per_case_safety.append({"case_id": row["case_id"],
                                "passed": safety_passed})
        if row["scenario"] == "normal":
            passed = float(row["candidate_queue"]) <= float(row["baseline_queue"])
            normal_gate.append({"case_id": row["case_id"], "passed": passed})
    rate = float(disagreements) / eligible if eligible else 0.0
    return {
        "switch_eligible_reference_disagreement_rate": rate,
        "reference_disagreement_rate": rate,
        "reference_disagreement_gate": rate >= minimum_disagreement,
        "strict_normal_case_gate": normal_gate,
        "per_case_safety_gate": per_case_safety,
    }


_validation_quality = validation_quality


def _validate_arm(root, arm, spec, config, manifest, baseline, baseline_hash,
                  manifest_hash, current_commit, source_tree_attestation):
    run_dir = _inside(root, spec["arms"][arm]["run_dir"], arm + " pilot run")
    if not run_dir.is_dir():
        raise ValueError("%s pilot run directory is missing" % arm)
    checkpoint_names = tuple(
        "checkpoints/%s/%s" % (checkpoint, name)
        for checkpoint in _CHECKPOINTS
        for name in ("contract.json", "weights.npz"))
    names = (
        "run-manifest.json", "resolved-config.json", "baseline-tuning.json",
        "baseline-tuning-provenance.json", "behavior-prior.json",
        "validation.json", "selection.json", "summary.json",
    ) + checkpoint_names
    missing = [name for name in names if not (run_dir / name).is_file()]
    if missing:
        label = ("checkpoint artifact" if missing[0].startswith("checkpoints/")
                 else "pilot artifact")
        raise ValueError("%s %s is missing: %s" % (arm, label, missing[0]))
    status = _validate_status(run_dir, names, arm)
    run_manifest = _json(run_dir / "run-manifest.json", arm + " run manifest")
    if (run_manifest.get("controller_id") != "neighbor_phase_ddqn"
            or run_manifest.get("mode") != "pilot"
            or run_manifest.get("learning_seed") != 11
            or run_manifest.get("manifest_sha256") != manifest_hash
            or run_manifest.get("code_commit") != current_commit
            or run_manifest.get("source_tree") != source_tree_attestation):
        raise ValueError("%s pilot provenance does not match registered inputs" % arm)
    resolved = _json(run_dir / "resolved-config.json", arm + " resolved config")
    if (resolved.get("mode") != "pilot" or resolved.get("learning_seed") != 11
            or resolved.get("run") != config.get("tiers", {}).get("pilot")):
        raise ValueError("%s resolved pilot identity drift" % arm)
    for key, value in config.items():
        if resolved.get(key) != value:
            raise ValueError("%s resolved config drifts from its source config" % arm)
    execution_config = copy.deepcopy(config)
    execution_config["mode"] = "pilot"
    execution_config["learning_seed"] = 11
    execution_config["run"] = copy.deepcopy(config["tiers"]["pilot"])
    if "simulation" in manifest:
        execution_config["simulation"] = copy.deepcopy(manifest["simulation"])
    expected_training_config_sha256 = canonical_json_sha256(execution_config)
    if (resolved.get("manifest_sha256") != manifest_hash
            or resolved.get("baseline_tuning_sha256") != baseline["tuning_sha256"]
            or resolved.get("training_config_sha256") !=
            expected_training_config_sha256
            or resolved.get("source_tree") != source_tree_attestation):
        raise ValueError("%s resolved input identity drift" % arm)
    copied = _json(run_dir / "baseline-tuning.json", arm + " copied baseline")
    if copied != baseline:
        raise ValueError("%s copied baseline differs from registered artifact" % arm)
    provenance = _json(run_dir / "baseline-tuning-provenance.json", arm + " baseline provenance")
    if (provenance.get("source_artifact_sha256") != baseline_hash
            or provenance.get("copied_artifact_sha256") != sha256_file(run_dir / "baseline-tuning.json")
            or provenance.get("tuning_sha256") != baseline["tuning_sha256"]):
        raise ValueError("%s baseline provenance drift" % arm)
    _validate_behavior_source(root, run_dir / "behavior-prior.json", manifest)
    summary = _json(run_dir / "summary.json", arm + " summary")
    _reject_test_evidence(summary, arm + " summary")
    rehearsal = summary.get("behavior_rehearsal")
    expected_rehearsal = config["behavior_prior"]["rehearsal"]["enabled"]
    if (not isinstance(rehearsal, dict)
            or rehearsal.get("enabled") is not expected_rehearsal
            or rehearsal.get("source_split") != "train"
            or (expected_rehearsal
                and _number(rehearsal.get("updates"),
                            arm + " rehearsal updates", 1.0) < 1.0)):
        raise ValueError("%s rehearsal summary evidence is invalid" % arm)
    validation = _json(run_dir / "validation.json", arm + " validation")
    _reject_test_evidence(validation, arm + " validation")
    diagnostic_checkpoint = spec.get("diagnostic_checkpoint")
    if diagnostic_checkpoint != "step-0" \
            or set(validation) != set(_CHECKPOINTS + ("step-0",)):
        raise ValueError("%s validation checkpoints differ from preregistration" % arm)
    baseline_rows = _baseline_rows(_expected_cases(baseline))
    minimum = _number(config["behavior_prior"].get(
        "minimum_validation_reference_disagreement_rate"),
        arm + " minimum reference disagreement", 0.0, 1.0)
    scores, quality = {}, {}
    diagnostic = validation["step-0"]
    if (diagnostic.get("diagnostic_only") is not True
            or diagnostic.get("selectable") is not False
            or not isinstance(diagnostic.get("rows"), list)
            or diagnostic.get("score", {}).get("training_step") != 0):
        raise ValueError("%s step-0 diagnostic evidence is invalid" % arm)
    diagnostic_quality = _validation_quality(
        diagnostic["rows"], baseline_rows, minimum)
    diagnostic_score = score_validation(diagnostic["rows"])
    diagnostic_score["training_step"] = 0
    if diagnostic_score != diagnostic["score"]:
        raise ValueError("%s step-0 score was not recomputed from rows" % arm)
    for checkpoint in _CHECKPOINTS:
        expected_step = int(checkpoint.split("-")[1])
        checkpoint_contract = _json(
            run_dir / "checkpoints" / checkpoint / "contract.json",
            "%s %s checkpoint contract" % (arm, checkpoint))
        if (checkpoint_contract.get("controller_family") !=
                "neighbor_phase_ddqn"
                or type(checkpoint_contract.get("training_step")) is not int
                or checkpoint_contract.get("training_step") != expected_step
                or checkpoint_contract.get("feature_dim") != 15
                or checkpoint_contract.get("hidden_size") !=
                config["model"]["hidden"]
                or checkpoint_contract.get("feature_order") !=
                list(SCHEDULE_CONTEXT_FEATURES)
                or checkpoint_contract.get("observation") !=
                config["observation"]
                or checkpoint_contract.get("behavior_prior") !=
                config["behavior_prior"]
                or checkpoint_contract.get("manifest_sha256") != manifest_hash
                or checkpoint_contract.get("baseline_tuning_sha256") !=
                baseline["tuning_sha256"]
                or checkpoint_contract.get("training_config_sha256") !=
                expected_training_config_sha256
                or checkpoint_contract.get("source_tree") !=
                source_tree_attestation):
            raise ValueError(
                "%s %s checkpoint contract/config binding is invalid" %
                (arm, checkpoint))
        try:
            PhaseScoringDDQN.load_bundle(
                str(run_dir / "checkpoints" / checkpoint),
                checkpoint_contract)
        except (IOError, KeyError, ValueError) as exc:
            raise ValueError(
                "%s %s checkpoint weights are invalid: %s" %
                (arm, checkpoint, exc))
        evidence = validation.get(checkpoint)
        if not isinstance(evidence, dict) or not isinstance(evidence.get("rows"), list):
            raise ValueError("%s validation evidence is malformed" % arm)
        checkpoint_quality = _validation_quality(
            evidence["rows"], baseline_rows, minimum)
        score = score_validation(evidence["rows"])
        reported = evidence.get("score")
        if (not isinstance(reported, dict)
                or type(reported.get("training_step")) is not int
                or reported.get("training_step") != expected_step):
            raise ValueError(
                "%s validation score training_step differs from checkpoint %s" %
                (arm, checkpoint))
        score["training_step"] = reported["training_step"]
        if score != reported:
            raise ValueError("%s validation score was not recomputed from rows" % arm)
        scores[checkpoint] = score
        quality[checkpoint] = checkpoint_quality
    selection = _json(run_dir / "selection.json", arm + " selection")
    _reject_test_evidence(selection, arm + " selection")
    if selection.get("eligibility_policy") != CHECKPOINT_ELIGIBILITY_POLICY:
        raise ValueError("%s checkpoint eligibility policy drift" % arm)
    try:
        selected = choose_checkpoint(scores)
        score_eligible = True
    except ValueError:
        selected = choose_reporting_checkpoint(scores)
        score_eligible = False
    if selection.get("selected_checkpoint") != selected or selection.get("score") != scores[selected]:
        raise ValueError("%s selection does not match recomputed validation score" % arm)
    if score_eligible:
        if (selection.get("status") != "eligible"
                or selection.get("eligible_for_test_evaluation") is not True
                or status.get("status") != "complete"
                or status.get("eligible_for_test_evaluation") is not True):
            raise ValueError("%s eligible pilot status drift" % arm)
    elif (selection.get("status") != "ineligible_negative_result"
          or selection.get("eligible_for_test_evaluation") is not False
          or status.get("status") != "ineligible"
          or status.get("eligible_for_test_evaluation") is not False):
        raise ValueError("%s ineligible pilot status drift" % arm)
    qualified = []
    for checkpoint in _CHECKPOINTS:
        checkpoint_quality = quality[checkpoint]
        if (scores[checkpoint].get("eligible")
                and checkpoint_quality["reference_disagreement_gate"]
                and all(item["passed"] for item in
                        checkpoint_quality["strict_normal_case_gate"])
                and all(item["passed"] for item in
                        checkpoint_quality["per_case_safety_gate"])):
            qualified.append(checkpoint)
    eligible = bool(qualified)
    if eligible:
        selected = min(
            qualified,
            key=lambda checkpoint: (
                float(scores[checkpoint]["worst_regret"]),
                float(scores[checkpoint]["mean_regret"]),
                int(scores[checkpoint]["training_step"])))
    selected_quality = quality[selected]
    return {
        "eligible": eligible,
        "selected_checkpoint": selected,
        "rank_tuple": ([scores[selected]["worst_regret"], scores[selected]["mean_regret"],
                        scores[selected]["training_step"], arm] if eligible else None),
        "score": scores[selected],
        "reference_disagreement_rate": selected_quality["reference_disagreement_rate"],
        "reference_disagreement_gate": selected_quality[
            "reference_disagreement_gate"],
        "strict_normal_case_gate": selected_quality["strict_normal_case_gate"],
        "per_case_safety_gate": selected_quality["per_case_safety_gate"],
        "step_0_diagnostic": {
            "selectable": False,
            "score": diagnostic_score,
            "switch_eligible_reference_disagreement_rate": diagnostic_quality[
                "switch_eligible_reference_disagreement_rate"],
        },
        "run_dir": str(run_dir.relative_to(root)),
        "artifacts": dict((name, sha256_file(run_dir / name)) for name in names),
    }


def _write_outputs(selected_path, selected_bytes, decision_path, decision):
    if selected_path.exists() or decision_path.exists():
        existing = selected_path if selected_path.exists() else decision_path
        raise ValueError("refusing to overwrite existing selection output: %s" % existing)
    decision_bytes = (json.dumps(decision, indent=2, sort_keys=True) + "\n").encode("utf-8")
    staged = []
    try:
        for path, payload in ((selected_path, selected_bytes),
                              (decision_path, decision_bytes)):
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temporary = Path(temporary)
            if sha256_file(temporary) != hashlib.sha256(payload).hexdigest():
                raise ValueError("staged selection output hash drift")
            staged.append((path, temporary))
        for path, temporary in staged:
            os.replace(str(temporary), str(path))
    finally:
        for _, temporary in staged:
            if temporary.exists():
                temporary.unlink()



def validate_final_schedule_selection(root, decision_path):
    """Validate immutable V3 schedule selection for a descendant release commit."""
    root = Path(root).resolve()
    supplied = Path(decision_path)
    if supplied.is_absolute():
        try:
            supplied = supplied.resolve().relative_to(root)
        except ValueError:
            raise ValueError("pilot schedule selection must remain inside the project")
    decision_path = _inside(root, supplied, "pilot schedule selection")
    decision = _json(decision_path, "pilot schedule selection")
    _reject_test_evidence(decision, "pilot schedule selection")
    if (decision.get("schema_version") != 1
            or decision.get("decision_type")
            != "haichau_pilot_schedule_rehearsal_selection"):
        raise ValueError("pilot schedule selection schema is invalid")
    identity = decision.get("decision_identity_sha256")
    unsigned = dict(decision)
    unsigned.pop("decision_identity_sha256", None)
    if (not _SHA256.match(str(identity or ""))
            or identity != canonical_sha256(unsigned)):
        raise ValueError("pilot schedule selection identity hash drift")
    specification = _artifact(
        root, decision.get("specification"), "schedule selection specification")
    _, spec = _validate_spec(root, specification)
    if (spec.get("learning_seed") != PILOT_LEARNING_SEED
            or tuple(decision.get("validation_checkpoints", ())) != _CHECKPOINTS
            or decision.get("diagnostic_checkpoint") != "step-0"):
        raise ValueError("pilot schedule selection protocol drift")
    inputs = decision.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("pilot schedule selection inputs are invalid")
    source_tree = inputs.get("source_tree")
    code_commit = inputs.get("code_commit")
    if (not re.fullmatch(r"[0-9a-f]{40,64}", str(code_commit or ""))
            or not isinstance(source_tree, dict)
            or source_tree.get("git_commit") != code_commit
            or source_tree.get("tracked_worktree") != "clean"
            or source_tree.get("index") != "clean"):
        raise ValueError("pilot schedule selection source identity is invalid")
    manifest_record = inputs.get("manifest")
    manifest_path = _artifact(
        root, manifest_record, "schedule pilot manifest")
    manifest = _json(manifest_path, "schedule pilot manifest")
    manifest_hash = canonical_json_sha256(manifest)
    if (manifest_record.get("path") != spec["manifest"]
            or manifest_record.get("canonical_json_sha256") != manifest_hash):
        raise ValueError("schedule pilot manifest binding is invalid")
    baseline_record = inputs.get("baseline_tuning")
    baseline_path = _artifact(
        root, baseline_record, "schedule pilot baseline tuning")
    baseline = _json(baseline_path, "schedule pilot baseline tuning")
    _validate_baseline_partition(_validate_baseline(baseline), manifest)
    if (baseline_record.get("path") != spec["baseline_tuning_artifact"]
            or baseline_record.get("tuning_sha256") != baseline.get("tuning_sha256")
            or baseline.get("binding", {}).get("manifest_sha256") != manifest_hash):
        raise ValueError("schedule pilot baseline binding is invalid")
    config_records = inputs.get("configs")
    outcomes = decision.get("arms")
    winner = decision.get("winner")
    if (not isinstance(config_records, dict) or set(config_records) != set(_ARMS)
            or not isinstance(outcomes, dict) or set(outcomes) != set(_ARMS)
            or not isinstance(winner, dict)):
        raise ValueError("pilot schedule selection arm records are invalid")
    configs, expected_config_records = _source_configs(root, spec)
    if config_records != expected_config_records:
        raise ValueError("schedule pilot source config binding is invalid")
    for arm in _ARMS:
        recomputed = _validate_arm(
            root, arm, spec, configs[arm], manifest, baseline,
            sha256_file(baseline_path), manifest_hash, code_commit, source_tree)
        if outcomes[arm] != recomputed:
            raise ValueError("%s pilot outcome differs from source evidence" % arm)
    eligible = [arm for arm in _ARMS if outcomes[arm]["eligible"]]
    if not eligible:
        raise ValueError("pilot schedule selection records no eligible arm")
    expected_winner = min(
        eligible, key=lambda arm: tuple(outcomes[arm]["rank_tuple"]))
    if (winner.get("arm") != expected_winner
            or winner.get("selected_checkpoint")
            != outcomes[expected_winner]["selected_checkpoint"]
            or winner.get("rank_tuple") != outcomes[expected_winner]["rank_tuple"]
            or winner.get("config") != config_records[expected_winner]):
        raise ValueError("pilot schedule selection winner is invalid")
    selected_path = _artifact(
        root, decision.get("selected_config"), "selected config")
    selected_config = _yaml(selected_path, "selected config")
    if selected_config != configs[expected_winner]:
        raise ValueError("selected config differs from winning schedule config")
    return {
        "path": str(decision_path.relative_to(root)),
        "sha256": sha256_file(decision_path),
        "decision_identity_sha256": identity,
        "primary_learned_controller": PRIMARY_LEARNED_CONTROLLER,
        "pilot_learning_seed": PILOT_LEARNING_SEED,
        "winner": {
            "arm": expected_winner,
            "selected_checkpoint": winner["selected_checkpoint"],
            "config": dict(config_records[expected_winner]),
        },
        "selected_config": {
            "path": str(selected_path.relative_to(root)),
            "sha256": sha256_file(selected_path),
            "config": selected_config,
        },
    }


def validate_frozen_schedule_selection(root, binding):
    """Revalidate the compact V3 selector binding stored by release freeze."""
    if not isinstance(binding, dict):
        raise ValueError("pilot V3 schedule selection binding is missing")
    selection = validate_final_schedule_selection(root, binding.get("path"))
    compact = dict(
        (key, value) for key, value in selection.items()
        if key != "selected_config")
    compact["selected_config"] = dict(
        (key, value) for key, value in selection["selected_config"].items()
        if key != "config")
    if binding != compact:
        raise ValueError("pilot V3 schedule selection binding drift")
    return selection


def validate_final_checkpoint_selection(
        validation, selection, tuning, expected_case_ids):
    """Validate the exact V3 final checkpoint schedule and selected step."""
    if not isinstance(validation, dict) \
            or set(validation) != set(FINAL_CHECKPOINTS):
        raise ValueError(
            "final validation checkpoints must be exactly step-4, step-8, step-12")
    for checkpoint in FINAL_CHECKPOINTS:
        evidence = validation.get(checkpoint)
        score = evidence.get("score") if isinstance(evidence, dict) else None
        expected_step = int(checkpoint.split("-")[1])
        if (not isinstance(score, dict)
                or type(score.get("training_step")) is not int
                or score.get("training_step") != expected_step):
            raise ValueError(
                "validation score training_step differs from checkpoint %s" %
                checkpoint)
    selected = validate_checkpoint_selection(
        validation, selection, tuning, expected_case_ids)
    if selected not in FINAL_CHECKPOINTS:
        raise ValueError("selected checkpoint must be step-4, step-8 or step-12")
    recomputed_best = choose_checkpoint(dict(
        (checkpoint, validation[checkpoint]["score"])
        for checkpoint in FINAL_CHECKPOINTS))
    if selected != recomputed_best:
        raise ValueError(
            "selected checkpoint differs from best eligible checkpoint")
    expected_step = int(selected.split("-")[1])
    if selection.get("score", {}).get("training_step") != expected_step:
        raise ValueError("selected score training_step differs from selected checkpoint")
    return selected


def validate_final_checkpoint_schedule_contract(contract, selected_config):
    """Bind each final checkpoint's schedule features to the selected V3 YAML."""
    if not isinstance(contract, dict) or not isinstance(selected_config, dict):
        raise ValueError("final checkpoint schedule contract is invalid")
    for field in ("observation", "behavior_prior"):
        expected = selected_config.get(field)
        if not isinstance(expected, dict) or contract.get(field) != expected:
            raise ValueError("final checkpoint schedule contract drift: %s" % field)


def validate_final_resolved_config(resolved, selected_config, learning_seed):
    """Require a final run to use the exact V3 config and a confirmation seed."""
    if not isinstance(resolved, dict) or not isinstance(selected_config, dict):
        raise ValueError("final resolved training configuration is invalid")
    if learning_seed not in CONFIRMATORY_LEARNING_SEEDS:
        raise ValueError("final training requires a registered confirmatory seed")
    if (resolved.get("mode") != "final"
            or resolved.get("learning_seed") != learning_seed):
        raise ValueError("final resolved training configuration identity drift")
    final_tier = selected_config.get("tiers", {}).get("final")
    if final_tier != FINAL_TIER or resolved.get("run") != FINAL_TIER:
        raise ValueError("final resolved training tier drift")
    for key, value in selected_config.items():
        if resolved.get(key) != value:
            raise ValueError(
                "final resolved training configuration differs from selected config")


def select_from_spec(root, spec_path):
    """Select a final schedule-rehearsal configuration from two validation pilots."""
    root = Path(root).resolve()
    source_tree_attestation = _tracked_tree_attestation(str(root))
    spec_path, spec = _validate_spec(root, spec_path)
    configs, config_records = _source_configs(root, spec)
    manifest_path = _inside(root, spec["manifest"], "experiment manifest")
    baseline_path = _inside(root, spec["baseline_tuning_artifact"], "baseline tuning")
    manifest = _json(manifest_path, "experiment manifest")
    baseline = _json(baseline_path, "baseline tuning")
    _validate_baseline_partition(_validate_baseline(baseline), manifest)
    manifest_hash = canonical_json_sha256(manifest)
    if baseline.get("binding", {}).get("manifest_sha256") != manifest_hash:
        raise ValueError("baseline tuning manifest identity differs from experiment manifest")
    current_commit = source_tree_attestation["git_commit"]
    baseline_hash = sha256_file(baseline_path)
    outcomes = dict((arm, _validate_arm(
        root, arm, spec, configs[arm], manifest, baseline, baseline_hash,
        manifest_hash, current_commit, source_tree_attestation)) for arm in _ARMS)
    eligible = [arm for arm in _ARMS if outcomes[arm]["eligible"]]
    if not eligible:
        raise ValueError("neither schedule arm is validation-eligible; selection fails closed")
    winner = min(eligible, key=lambda arm: tuple(outcomes[arm]["rank_tuple"]))
    decision_path = _inside(root, spec["decision_output"], "behavior decision output")
    selected_path = _inside(root, spec["selected_config_output"], "behavior selected config output")
    selected_bytes = yaml.safe_dump(configs[winner], sort_keys=True).encode("utf-8")
    decision = {
        "schema_version": 1,
        "decision_type": spec["decision_type"],
        "selection_rule": (
            "select the eligible arm with lexicographically lowest worst normalized "
            "queue regret, mean regret, earlier training step, then arm name; "
            "all selected normal cases must not exceed their matched baseline, "
            "raw greedy DDQN switch-eligible disagreement audits are required; "
            "step-0 is diagnostic-only and cannot be selected, "
            "and neither eligible arm fails closed"),
        "specification": _record(root, spec_path, "schedule-rehearsal selection specification"),
        "inputs": {
            "code_commit": current_commit,
            "source_tree": source_tree_attestation,
            "manifest": dict(_record(root, manifest_path, "experiment manifest"),
                             canonical_json_sha256=manifest_hash),
            "baseline_tuning": dict(_record(root, baseline_path, "baseline tuning"),
                                    tuning_sha256=baseline["tuning_sha256"]),
            "configs": config_records,
        },
        "validation_checkpoints": list(_CHECKPOINTS),
        "diagnostic_checkpoint": "step-0",
        "arms": outcomes,
        "winner": {"arm": winner, "selected_checkpoint": outcomes[winner]["selected_checkpoint"],
                   "rank_tuple": outcomes[winner]["rank_tuple"],
                   "config": config_records[winner]},
        "selected_config": {"path": str(selected_path.relative_to(root)),
                            "sha256": hashlib.sha256(selected_bytes).hexdigest()},
    }
    decision["decision_identity_sha256"] = canonical_sha256(decision)
    _write_outputs(selected_path, selected_bytes, decision_path, decision)
    return decision
