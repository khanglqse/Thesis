"""Fail-closed selection between behavior-cloning pilot arms.

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

from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, choose_checkpoint,
    choose_reporting_checkpoint, score_validation)
from traffic_rl.research.artifacts import canonical_sha256, sha256_file
from traffic_rl.train.network_trainer import canonical_json_sha256


_ARMS = ("bc_prior", "bc_only")
_CHECKPOINTS = ("step-4", "step-8", "step-12")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
        raise ValueError("behavior selection requires a git checkout")
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError("behavior selection requires a full Git commit")
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


def _validate_spec(root, spec_path):
    supplied = Path(spec_path)
    if supplied.is_absolute():
        try:
            spec_path = supplied.resolve().relative_to(Path(root).resolve())
        except ValueError:
            raise ValueError("behavior selection specification must remain inside the project")
    path = _inside(root, spec_path, "behavior selection specification")
    spec = _yaml(path, "behavior selection specification")
    if spec.get("schema_version") != 1:
        raise ValueError("behavior selection specification schema_version must equal 1")
    if spec.get("decision_type") != "haichau_pilot_behavior_arm_selection":
        raise ValueError("behavior selection decision_type is invalid")
    if spec.get("learning_seed") != 11 or spec.get("mode") != "pilot":
        raise ValueError("behavior selection is fixed to pilot seed 11")
    if tuple(spec.get("validation_checkpoints", ())) != _CHECKPOINTS:
        raise ValueError("behavior selection checkpoints must be exactly step-4, step-8, step-12")
    arms = spec.get("arms")
    if not isinstance(arms, dict) or set(arms) != set(_ARMS):
        raise ValueError("behavior selection requires bc_prior and bc_only arms")
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
            raise ValueError("behavior selection specification requires %s" % field)
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
    return prior


def _without_reference_sampling(config):
    value = copy.deepcopy(config)
    try:
        del value["behavior_prior"]["reference_probability_start"]
        del value["behavior_prior"]["reference_probability_end"]
    except (KeyError, TypeError):
        raise ValueError("behavior arm config lacks reference sampling fields")
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
        if arm == "bc_prior" and reference_start <= 0.0:
            raise ValueError("bc_prior must execute a reference prior")
        if arm == "bc_only" and (reference_start != 0.0 or reference_end != 0.0):
            raise ValueError("bc_only must not execute reference actions")
        configs[arm] = config
        record = _record(root, path, arm + " config")
        record["behavior_prior"] = copy.deepcopy(prior)
        records[arm] = record
    if _without_reference_sampling(configs["bc_prior"]) != _without_reference_sampling(configs["bc_only"]):
        raise ValueError("behavior arm configs differ outside reference sampling")
    return configs, records


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
    expected_ids, expected_hashes = _manifest_train_cases(root, manifest)
    if evidence.get("source_split") != "train":
        raise ValueError("behavior training source must be the train split")
    if evidence.get("source_case_ids") != expected_ids:
        raise ValueError("behavior training source cases differ from manifest train cases")
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


def _validation_quality(rows, baseline_rows, minimum_disagreement):
    case_ids = [row.get("case_id") if isinstance(row, dict) else None for row in rows]
    if len(rows) != 6 or set(case_ids) != set(baseline_rows):
        raise ValueError("validation evidence must contain exactly six registered rows")
    eligible, disagreements = 0, 0
    normal_gate = []
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
        denominator = _number(audit.get("eligible_decisions"),
                              "reference disagreement denominator", 1.0)
        count = _number(audit.get("reference_disagreements"),
                        "reference disagreements", 0.0, denominator)
        reported = _number(audit.get("reference_disagreement_rate"),
                           "reference disagreement rate", 0.0, 1.0)
        if abs(reported - count / denominator) > 1e-12:
            raise ValueError("reference disagreement rate does not match its count")
        eligible += int(denominator)
        disagreements += int(count)
        completion = _number(row.get("candidate_completion"),
                             "candidate completion", 0.0, 1.0)
        insertion = _number(row.get("candidate_insertion"),
                            "candidate insertion", 0.0, 1.0)
        if (float(row["baseline_completion"]) - completion > 0.02
                or float(row["baseline_insertion"]) - insertion > 0.02):
            raise ValueError("per-case completion or insertion gate failed")
        if row["scenario"] == "normal":
            passed = float(row["candidate_queue"]) <= float(row["baseline_queue"])
            normal_gate.append({"case_id": row["case_id"], "passed": passed})
            if not passed:
                raise ValueError("normal case queue exceeds its matched baseline")
    rate = float(disagreements) / eligible if eligible else 0.0
    if rate < minimum_disagreement:
        raise ValueError("reference disagreement rate is below the configured minimum")
    return rate, normal_gate


def _validate_arm(root, arm, spec, config, manifest, baseline, baseline_hash,
                  manifest_hash, current_commit):
    run_dir = _inside(root, spec["arms"][arm]["run_dir"], arm + " pilot run")
    if not run_dir.is_dir():
        raise ValueError("%s pilot run directory is missing" % arm)
    names = (
        "run-manifest.json", "resolved-config.json", "baseline-tuning.json",
        "baseline-tuning-provenance.json", "behavior-prior.json",
        "validation.json", "selection.json",
    )
    if any(not (run_dir / name).is_file() for name in names):
        raise ValueError("%s pilot artifact is missing" % arm)
    status = _validate_status(run_dir, names, arm)
    run_manifest = _json(run_dir / "run-manifest.json", arm + " run manifest")
    if (run_manifest.get("controller_id") != "neighbor_phase_ddqn"
            or run_manifest.get("mode") != "pilot"
            or run_manifest.get("learning_seed") != 11
            or run_manifest.get("manifest_sha256") != manifest_hash
            or run_manifest.get("code_commit") != current_commit):
        raise ValueError("%s pilot provenance does not match registered inputs" % arm)
    resolved = _json(run_dir / "resolved-config.json", arm + " resolved config")
    if (resolved.get("mode") != "pilot" or resolved.get("learning_seed") != 11
            or resolved.get("run") != config.get("tiers", {}).get("pilot")):
        raise ValueError("%s resolved pilot identity drift" % arm)
    for key, value in config.items():
        if resolved.get(key) != value:
            raise ValueError("%s resolved config drifts from its source config" % arm)
    if (resolved.get("manifest_sha256") != manifest_hash
            or resolved.get("baseline_tuning_sha256") != baseline["tuning_sha256"]):
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
    validation = _json(run_dir / "validation.json", arm + " validation")
    if set(validation) != set(_CHECKPOINTS):
        raise ValueError("%s validation checkpoints differ from preregistration" % arm)
    baseline_rows = _baseline_rows(_expected_cases(baseline))
    minimum = _number(config["behavior_prior"].get(
        "minimum_validation_reference_disagreement_rate"),
        arm + " minimum reference disagreement", 0.0, 1.0)
    scores, quality = {}, {}
    for checkpoint in _CHECKPOINTS:
        evidence = validation.get(checkpoint)
        if not isinstance(evidence, dict) or not isinstance(evidence.get("rows"), list):
            raise ValueError("%s validation evidence is malformed" % arm)
        rate, normal_gate = _validation_quality(
            evidence["rows"], baseline_rows, minimum)
        score = score_validation(evidence["rows"])
        reported = evidence.get("score")
        if not isinstance(reported, dict) or reported.get("training_step") not in (4, 8, 12):
            raise ValueError("%s validation score is malformed" % arm)
        score["training_step"] = reported["training_step"]
        if score != reported:
            raise ValueError("%s validation score was not recomputed from rows" % arm)
        scores[checkpoint] = score
        quality[checkpoint] = {
            "reference_disagreement_rate": rate,
            "strict_normal_case_gate": normal_gate,
        }
    selection = _json(run_dir / "selection.json", arm + " selection")
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
    selected_quality = quality[selected]
    eligible = bool(score_eligible and all(
        item["passed"] for item in selected_quality["strict_normal_case_gate"]))
    return {
        "eligible": eligible,
        "selected_checkpoint": selected,
        "rank_tuple": ([scores[selected]["worst_regret"], scores[selected]["mean_regret"],
                        scores[selected]["training_step"], arm] if eligible else None),
        "score": scores[selected],
        "reference_disagreement_rate": selected_quality["reference_disagreement_rate"],
        "strict_normal_case_gate": selected_quality["strict_normal_case_gate"],
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


def select_from_spec(root, spec_path):
    """Select a final behavior-arm configuration from two validation pilots."""
    root = Path(root).resolve()
    spec_path, spec = _validate_spec(root, spec_path)
    configs, config_records = _source_configs(root, spec)
    manifest_path = _inside(root, spec["manifest"], "experiment manifest")
    baseline_path = _inside(root, spec["baseline_tuning_artifact"], "baseline tuning")
    manifest = _json(manifest_path, "experiment manifest")
    baseline = _json(baseline_path, "baseline tuning")
    _validate_baseline(baseline)
    manifest_hash = canonical_json_sha256(manifest)
    if baseline.get("binding", {}).get("manifest_sha256") != manifest_hash:
        raise ValueError("baseline tuning manifest identity differs from experiment manifest")
    current_commit = _git_head(root)
    baseline_hash = sha256_file(baseline_path)
    outcomes = dict((arm, _validate_arm(
        root, arm, spec, configs[arm], manifest, baseline, baseline_hash,
        manifest_hash, current_commit)) for arm in _ARMS)
    eligible = [arm for arm in _ARMS if outcomes[arm]["eligible"]]
    if not eligible:
        raise ValueError("neither behavior arm is validation-eligible; selection fails closed")
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
            "raw greedy DDQN audits and reference disagreement thresholds are required, "
            "and neither eligible arm fails closed"),
        "specification": _record(root, spec_path, "behavior selection specification"),
        "inputs": {
            "code_commit": current_commit,
            "manifest": dict(_record(root, manifest_path, "experiment manifest"),
                             canonical_json_sha256=manifest_hash),
            "baseline_tuning": dict(_record(root, baseline_path, "baseline tuning"),
                                    tuning_sha256=baseline["tuning_sha256"]),
            "configs": config_records,
        },
        "validation_checkpoints": list(_CHECKPOINTS),
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
