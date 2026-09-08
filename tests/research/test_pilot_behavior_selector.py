import hashlib
import json
import subprocess

import pytest
import yaml

from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, choose_checkpoint, score_validation)
from traffic_rl.train.network_trainer import canonical_json_sha256


ARMS = ("bc_prior", "bc_only")
CHECKPOINTS = ("step-4", "step-8", "step-12")
CASES = (
    ("validation_normal_demand31", "normal"),
    ("validation_normal_demand32", "normal"),
    ("validation_am_peak_demand31", "am_peak"),
    ("validation_am_peak_demand32", "am_peak"),
    ("validation_pm_peak_demand31", "pm_peak"),
    ("validation_pm_peak_demand32", "pm_peak"),
)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(value)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root, *args):
    return subprocess.check_output(("git", "-C", str(root)) + args).decode().strip()


def _config(reference_start):
    return {
        "schema_version": 2,
        "model": {"feature_dim": 12, "hidden": 16, "lr": 0.001,
                  "gamma": 0.99, "n_step": 3},
        "optimizer": {"batch_size": 4, "buffer_capacity": 32,
                      "train_start": 4, "target_sync": 5,
                      "grad_clip": 10.0, "huber_delta": 1.0},
        "exploration": {"epsilon_start": 0.1, "epsilon_end": 0.02,
                        "epsilon_decay_decisions": 4320},
        "behavior_prior": {
            "type": "fixed_time_behavior_cloning", "bc_epochs": 1,
            "reference_probability_start": reference_start,
            "reference_probability_end": 0.0,
            "random_probability_start": 0.1,
            "random_probability_end": 0.02,
            "minimum_validation_reference_disagreement_rate": 0.01,
        },
        "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.2,
                   "switch_penalty": 0.05},
        "baseline": {"controller": "validation_tuned_fixed",
                     "search_green_durations": [25]},
        "tiers": {
            "pilot": {"episodes": 12, "horizon_seconds": 3600,
                      "eval_every": 4},
            "final": {"episodes": 80, "horizon_seconds": 3600,
                      "eval_every": 20},
        },
    }


def _rows(queue_delta, disagreement=0.10):
    rows = []
    for case_id, scenario in CASES:
        rows.append({
            "case_id": case_id, "scenario": scenario,
            "baseline_queue": 100.0,
            "candidate_queue": 100.0 + queue_delta,
            "baseline_completion": 1.0, "candidate_completion": 0.99,
            "baseline_insertion": 1.0, "candidate_insertion": 0.99,
            "policy_audit": {
                "evaluation_policy": "raw_ddqn_greedy",
                "reference": "validation_tuned_fixed",
                "eligible_decisions": 100,
                "reference_disagreements": int(disagreement * 100),
                "reference_disagreement_rate": disagreement,
            },
        })
    return rows


def _baseline(manifest):
    rows = [{
        "case_id": case_id, "scenario": scenario,
        "queue_integral_vehicle_seconds": 100.0,
        "completion_rate": 1.0, "insertion_rate": 1.0,
    } for case_id, scenario in CASES]
    document = {
        "schema_version": 1, "method": "validation_grid_search",
        "binding": {"manifest_sha256": canonical_json_sha256(manifest)},
        "search_space": {"fixed_green_duration": [25]},
        "selected": {"fixed_green_duration": 25},
        "candidates": [{"fixed_green_duration": 25,
                        "mean_queue_integral_vehicle_seconds": 100.0,
                        "rows": rows}],
    }
    document["tuning_sha256"] = canonical_json_sha256(document)
    return document


def _manifest(root):
    cases = []
    for index, scenario in enumerate(("normal", "am_peak", "pm_peak"), 1):
        flow = root / "flows" / ("train-%s.xml" % scenario)
        _write(flow, "train-%s" % scenario)
        cases.append({
            "case_id": "train_%s_demand%d" % (scenario, index),
            "scenario": scenario, "split": "train", "flow_path": str(
                flow.relative_to(root)), "flow_sha256": _sha256(flow),
        })
    for case_id, scenario in CASES:
        cases.append({"case_id": case_id, "scenario": scenario,
                      "split": "validation", "flow_sha256": "v" * 64})
    return {"protocol_version": 2, "cases": cases}


def _refresh_status(run_dir):
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"] = {
        name: _sha256(run_dir / name) for name in status["artifact_sha256"]}
    _write(status_path, status)


def _pilot(root, arm, config, manifest, baseline, commit, queue_delta):
    run_dir = root / "training" / ("pilot-%s-seed11" % arm)
    manifest_hash = canonical_json_sha256(manifest)
    resolved = dict(config)
    resolved.update({"mode": "pilot", "learning_seed": 11,
                     "run": config["tiers"]["pilot"],
                     "manifest_sha256": manifest_hash,
                     "baseline_tuning_sha256": baseline["tuning_sha256"]})
    _write(run_dir / "resolved-config.json", resolved)
    _write(run_dir / "run-manifest.json", {
        "controller_id": "neighbor_phase_ddqn", "mode": "pilot",
        "learning_seed": 11, "manifest_sha256": manifest_hash,
        "code_commit": commit,
    })
    _write(run_dir / "baseline-tuning.json", baseline)
    _write(run_dir / "baseline-tuning-provenance.json", {
        "source_artifact_sha256": _sha256(root / "baseline.json"),
        "copied_artifact_sha256": _sha256(run_dir / "baseline-tuning.json"),
        "tuning_sha256": baseline["tuning_sha256"],
    })
    train_cases = [case for case in manifest["cases"] if case["split"] == "train"]
    _write(run_dir / "behavior-prior.json", {
        "source_split": "train",
        "source_case_ids": [case["case_id"] for case in train_cases],
        "train_cases": [{"case_id": case["case_id"],
                         "flow_sha256": case["flow_sha256"]}
                        for case in train_cases],
    })
    validation = {}
    for checkpoint in CHECKPOINTS:
        rows = _rows(queue_delta)
        score = score_validation(rows)
        score["training_step"] = int(checkpoint.split("-")[1])
        validation[checkpoint] = {"rows": rows, "score": score}
    _write(run_dir / "validation.json", validation)
    scores = {name: item["score"] for name, item in validation.items()}
    selected = choose_checkpoint(scores)
    _write(run_dir / "selection.json", {
        "status": "eligible", "selected_checkpoint": selected,
        "eligible_for_test_evaluation": True,
        "eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "score": scores[selected],
    })
    artifacts = (
        "run-manifest.json", "resolved-config.json", "baseline-tuning.json",
        "baseline-tuning-provenance.json", "behavior-prior.json",
        "validation.json", "selection.json",
    )
    _write(run_dir / "status.json", {
        "status": "complete", "eligible_for_test_evaluation": True,
        "artifact_sha256": dict((name, _sha256(run_dir / name))
                                  for name in artifacts),
    })
    return run_dir


def _fixture(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    manifest = _manifest(root)
    _write(root / "manifest.json", manifest)
    baseline = _baseline(manifest)
    _write(root / "baseline.json", baseline)
    configs = {"bc_prior": _config(0.75), "bc_only": _config(0.0)}
    for arm, config in configs.items():
        _write(root / "configs" / (arm + ".yaml"),
               yaml.safe_dump(config, sort_keys=True))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    commit = _git(root, "rev-parse", "HEAD")
    for arm in ARMS:
        _pilot(root, arm, configs[arm], manifest, baseline, commit,
               queue_delta=(-1.0 if arm == "bc_only" else 0.0))
    spec = {
        "schema_version": 1,
        "decision_type": "haichau_pilot_behavior_arm_selection",
        "learning_seed": 11, "mode": "pilot",
        "manifest": "manifest.json", "baseline_tuning_artifact": "baseline.json",
        "validation_checkpoints": list(CHECKPOINTS),
        "arms": dict((arm, {
            "config": "configs/%s.yaml" % arm,
            "run_dir": "training/pilot-%s-seed11" % arm,
        }) for arm in ARMS),
        "decision_output": "output/decision.json",
        "selected_config_output": "output/final-selected.yaml",
    }
    _write(root / "spec.yaml", yaml.safe_dump(spec, sort_keys=True))
    return root, spec


def test_selects_best_hash_bound_behavior_arm_and_writes_final_config(tmp_path):
    from traffic_rl.research.pilot_behavior_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    decision = select_from_spec(root, root / "spec.yaml")

    assert decision["winner"]["arm"] == "bc_only"
    assert decision["winner"]["rank_tuple"] == [-0.01, -0.01, 4, "bc_only"]
    assert yaml.safe_load((root / spec["selected_config_output"]).read_text()) \
        == yaml.safe_load((root / "configs/bc_only.yaml").read_text())
    assert len(decision["arms"]["bc_only"]["strict_normal_case_gate"]) == 2
    assert decision["arms"]["bc_prior"]["reference_disagreement_rate"] == 0.1
    assert len(decision["decision_identity_sha256"]) == 64


@pytest.mark.parametrize("mutation, message", [
    ("nonraw", "raw_ddqn_greedy"),
    ("normal_regression", "normal case"),
    ("bad_training_source", "training source"),
    ("low_disagreement", "reference disagreement"),
    ("stale_commit", "provenance"),
])
def test_rejects_invalid_behavior_arm_evidence(tmp_path, mutation, message):
    from traffic_rl.research.pilot_behavior_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    run_dir = root / "training/pilot-bc_prior-seed11"
    if mutation in ("nonraw", "normal_regression", "low_disagreement"):
        path = run_dir / "validation.json"
        validation = json.loads(path.read_text())
        for evidence in validation.values():
            if mutation == "nonraw":
                evidence["rows"][0]["policy_audit"]["evaluation_policy"] = "reference"
            elif mutation == "normal_regression":
                for row in evidence["rows"]:
                    if row["scenario"] == "normal":
                        row["candidate_queue"] = 101.0
            else:
                for row in evidence["rows"]:
                    row["policy_audit"]["reference_disagreement_rate"] = 0.0
                    row["policy_audit"]["reference_disagreements"] = 0
            score = score_validation(evidence["rows"])
            score["training_step"] = evidence["score"]["training_step"]
            evidence["score"] = score
        _write(path, validation)
        selection = json.loads((run_dir / "selection.json").read_text())
        selection["score"] = validation[selection["selected_checkpoint"]]["score"]
        _write(run_dir / "selection.json", selection)
        _refresh_status(run_dir)
    elif mutation == "bad_training_source":
        path = run_dir / "behavior-prior.json"
        evidence = json.loads(path.read_text())
        evidence["source_case_ids"] = evidence["source_case_ids"][:-1]
        _write(path, evidence)
        _refresh_status(run_dir)
    else:
        path = run_dir / "run-manifest.json"
        evidence = json.loads(path.read_text())
        evidence["code_commit"] = "0" * 40
        _write(path, evidence)
        _refresh_status(run_dir)

    with pytest.raises(ValueError, match=message):
        select_from_spec(root, root / "spec.yaml")


def test_fails_closed_when_no_arm_passes_selection(tmp_path):
    from traffic_rl.research.pilot_behavior_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    for arm in ARMS:
        run_dir = root / "training" / ("pilot-%s-seed11" % arm)
        validation_path = run_dir / "validation.json"
        validation = json.loads(validation_path.read_text())
        for evidence in validation.values():
            for row in evidence["rows"]:
                if row["scenario"] == "pm_peak":
                    row["candidate_queue"] = 101.0
            score = score_validation(evidence["rows"])
            score["training_step"] = evidence["score"]["training_step"]
            evidence["score"] = score
        _write(validation_path, validation)
        selection = json.loads((run_dir / "selection.json").read_text())
        selection.update({"status": "ineligible_negative_result",
                          "eligible_for_test_evaluation": False,
                          "score": validation["step-4"]["score"]})
        _write(run_dir / "selection.json", selection)
        status = json.loads((run_dir / "status.json").read_text())
        status.update({"status": "ineligible", "eligible_for_test_evaluation": False})
        _write(run_dir / "status.json", status)
        _refresh_status(run_dir)

    with pytest.raises(ValueError, match="neither behavior arm"):
        select_from_spec(root, root / "spec.yaml")


def test_refuses_to_overwrite_immutable_outputs(tmp_path):
    from traffic_rl.research.pilot_behavior_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    target = root / spec["decision_output"]
    _write(target, "occupied\n")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        select_from_spec(root, root / "spec.yaml")


def test_cli_is_directly_invocable_from_the_repository_root():
    completed = subprocess.run(
        ["python3", "scripts/select_haichau_pilot_behavior.py", "--help"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)

    assert completed.returncode == 0, completed.stderr
    assert "behavior-arm selection" in completed.stdout
