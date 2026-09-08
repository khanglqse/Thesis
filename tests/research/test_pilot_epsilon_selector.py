import copy
import hashlib
import json
import subprocess

import pytest
import yaml

from traffic_rl.eval.checkpoint_selection import (
    choose_checkpoint, choose_reporting_checkpoint, score_validation)
from traffic_rl.train.network_trainer import canonical_json_sha256


VALIDATION_CASES = [
    "validation_normal_demand31", "validation_normal_demand32",
    "validation_am_peak_demand31", "validation_am_peak_demand32",
    "validation_pm_peak_demand31", "validation_pm_peak_demand32",
]


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(value)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_status_hashes(run_dir):
    path = run_dir / "status.json"
    status = json.loads(path.read_text())
    status["artifact_sha256"] = {
        name: _sha256(run_dir / name)
        for name in status["artifact_sha256"]
    }
    path.write_text(json.dumps(status))


def _rows(regret=0.0):
    rows = []
    for case_id in VALIDATION_CASES:
        scenario = case_id[len("validation_"):].rsplit("_demand", 1)[0]
        rows.append({
            "case_id": case_id, "scenario": scenario,
            "baseline_queue": 100.0, "candidate_queue": 100.0 + regret,
            "baseline_completion": 1.0, "candidate_completion": 1.0,
            "baseline_insertion": 1.0, "candidate_insertion": 1.0,
        })
    return rows


def _baseline():
    rows = [{
        "case_id": row["case_id"], "scenario": row["scenario"],
        "queue_integral_vehicle_seconds": row["baseline_queue"],
        "completion_rate": row["baseline_completion"],
        "insertion_rate": row["baseline_insertion"],
    } for row in _rows()]
    value = {
        "schema_version": 1, "method": "validation_grid_search",
        "binding": {"fixture": "validation-only"},
        "search_space": {"fixed_green_duration": [30]},
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "mean_queue_integral_vehicle_seconds": 100.0,
            "rows": rows,
        }],
    }
    value["tuning_sha256"] = canonical_json_sha256(value)
    return value


def _config(decay):
    return {
        "schema_version": 2,
        "model": {"feature_dim": 12},
        "exploration": {"epsilon_start": 1.0, "epsilon_end": 0.05,
                        "epsilon_decay_decisions": decay},
        "tiers": {"pilot": {"episodes": 12, "horizon_seconds": 3600,
                              "eval_every": 4}},
    }


def _run(root, name, config, baseline_path, commit, regrets):
    run_dir = root / "results/haichau_network_v2/training" / name
    manifest_hash = canonical_json_sha256(json.loads((root / "manifest.json").read_text()))
    source_baseline = json.loads(baseline_path.read_text())
    resolved = copy.deepcopy(config)
    resolved.update({"mode": "pilot", "learning_seed": 11,
                     "manifest_sha256": manifest_hash,
                     "baseline_tuning_sha256": source_baseline["tuning_sha256"],
                     "run": copy.deepcopy(config["tiers"]["pilot"])})
    _write(run_dir / "resolved-config.json", resolved)
    baseline = source_baseline
    _write(run_dir / "baseline-tuning.json", baseline)
    copied_hash = _sha256(run_dir / "baseline-tuning.json")
    _write(run_dir / "baseline-tuning-provenance.json", {
        "source_artifact_sha256": _sha256(baseline_path),
        "copied_artifact_sha256": copied_hash,
        "tuning_sha256": baseline["tuning_sha256"],
    })
    validation = {}
    for step, regret in zip((4, 8, 12), regrets):
        score = score_validation(_rows(regret))
        score["training_step"] = step
        validation["step-%d" % step] = {"rows": _rows(regret), "score": score}
    _write(run_dir / "validation.json", validation)
    scores = {key: value["score"] for key, value in validation.items()}
    try:
        selected = choose_checkpoint(scores)
        eligible = True
    except ValueError:
        selected = choose_reporting_checkpoint(scores)
        eligible = False
    score = validation[selected]["score"]
    _write(run_dir / "selection.json", {
        "status": "eligible" if eligible else "ineligible_negative_result",
        "selected_checkpoint": selected,
        "eligible_for_test_evaluation": eligible,
        "eligibility_policy": score["eligibility_policy"], "score": score,
    })
    _write(run_dir / "run-manifest.json", {
        "code_commit": commit, "manifest_sha256": manifest_hash,
        "controller_id": "neighbor_phase_ddqn", "mode": "pilot",
        "learning_seed": 11,
    })
    artifacts = {}
    for artifact in ("run-manifest.json", "resolved-config.json",
                     "baseline-tuning.json", "baseline-tuning-provenance.json",
                     "validation.json", "selection.json"):
        artifacts[artifact] = _sha256(run_dir / artifact)
    _write(run_dir / "status.json", {
        "status": "complete" if eligible else "ineligible",
        "eligible_for_test_evaluation": eligible,
        "artifact_sha256": artifacts,
    })
    return run_dir


def _fixture(tmp_path, canonical_regrets=(0.0, 0.0, 0.0),
             fast_regrets=(0.0, 0.0, 0.0)):
    root = tmp_path
    _write(root / "manifest.json", {
        "only_identity_is_read": True,
        "test_flow_that_must_not_be_opened": "does-not-exist-test.json",
    })
    canonical_config = root / "configs/canonical.yaml"
    fast_config = root / "configs/fast.yaml"
    canonical = _config(10000)
    fast = _config(2160)
    canonical_config.parent.mkdir(parents=True, exist_ok=True)
    canonical_config.write_text(yaml.safe_dump(canonical, sort_keys=True))
    fast_config.write_text(yaml.safe_dump(fast, sort_keys=True))
    baseline_path = root / "baseline.json"
    baseline = _baseline()
    baseline["binding"]["manifest_sha256"] = canonical_json_sha256(
        json.loads((root / "manifest.json").read_text()))
    baseline["tuning_sha256"] = canonical_json_sha256({
        key: value for key, value in baseline.items() if key != "tuning_sha256"})
    _write(baseline_path, baseline)
    subprocess.check_call(["git", "init", "-q", str(root)])
    subprocess.check_call(["git", "-C", str(root), "config", "user.email", "fixture@example.test"])
    subprocess.check_call(["git", "-C", str(root), "config", "user.name", "Fixture"])
    subprocess.check_call(["git", "-C", str(root), "add", "."])
    subprocess.check_call(["git", "-C", str(root), "commit", "-qm", "inputs"])
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    canonical_dir = _run(root, "pilot-seed11", canonical, baseline_path, commit,
                         canonical_regrets)
    fast_dir = _run(root, "pilot-epsilon2160-seed11", fast, baseline_path, commit,
                    fast_regrets)
    spec = {
        "schema_version": 1,
        "decision_type": "haichau_pilot_epsilon_schedule_selection",
        "learning_seed": 11, "mode": "pilot",
        "manifest": "manifest.json", "baseline_tuning_artifact": "baseline.json",
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "schedules": {
            "canonical": {"config": "configs/canonical.yaml",
                          "run_dir": str(canonical_dir.relative_to(root)),
                          "epsilon_decay_decisions": 10000},
            "epsilon2160": {"config": "configs/fast.yaml",
                            "run_dir": str(fast_dir.relative_to(root)),
                            "epsilon_decay_decisions": 2160},
        },
        "decision_output": "out/decision.json",
        "selected_config_output": "out/selected.yaml",
    }
    _write(root / "spec.yaml", yaml.safe_dump(spec, sort_keys=True))
    return root, spec


def test_selects_fast_only_when_its_eligible_validation_tuple_is_strictly_better(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, spec = _fixture(tmp_path, canonical_regrets=(0.0, -1.0, -2.0),
                          fast_regrets=(-2.0, -3.0, -4.0))
    decision = select_from_spec(root, root / "spec.yaml")

    assert decision["winner"]["schedule"] == "epsilon2160"
    assert decision["winner"]["selected_checkpoint"] == "step-12"
    assert decision["schedules"]["canonical"]["rank_tuple"] == [-0.02, -0.02, 12]
    assert (root / spec["decision_output"]).is_file()
    assert json.loads((root / spec["decision_output"]).read_text()) == decision
    selected_bytes = (root / spec["selected_config_output"]).read_bytes()
    assert yaml.safe_load(selected_bytes) == _config(2160)
    assert decision["selected_config"]["sha256"] == hashlib.sha256(selected_bytes).hexdigest()
    assert decision["decision_identity_sha256"]
    assert "test" not in json.dumps(decision).lower()


def test_final_selection_binding_rechecks_decision_identity_and_selected_config(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import (
        select_from_spec, validate_final_selection)

    root, spec = _fixture(tmp_path, canonical_regrets=(-1.0, -2.0, -3.0),
                          fast_regrets=(-2.0, -3.0, -4.0))
    decision = select_from_spec(root, root / "spec.yaml")

    binding = validate_final_selection(root, root / spec["decision_output"])

    assert binding["decision_identity_sha256"] == decision["decision_identity_sha256"]
    assert binding["selected_config"]["path"] == spec["selected_config_output"]
    assert binding["selected_config"]["config"] == _config(2160)


def test_final_selection_binding_rejects_tampered_selected_config(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import (
        select_from_spec, validate_final_selection)

    root, spec = _fixture(tmp_path, canonical_regrets=(-1.0, -2.0, -3.0),
                          fast_regrets=(-2.0, -3.0, -4.0))
    select_from_spec(root, root / "spec.yaml")
    selected = root / spec["selected_config_output"]
    selected.write_text(yaml.safe_dump(_config(10000), sort_keys=True))

    with pytest.raises(ValueError, match="selected config hash drift"):
        validate_final_selection(root, root / spec["decision_output"])


def test_tie_retains_canonical_schedule(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path, canonical_regrets=(-1.0, -2.0, -3.0),
                       fast_regrets=(-1.0, -2.0, -3.0))

    assert select_from_spec(root, root / "spec.yaml")["winner"]["schedule"] == "canonical"


def test_valid_ineligible_fast_pilot_retains_eligible_canonical(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path, canonical_regrets=(-1.0, -2.0, -3.0),
                       fast_regrets=(1.0, 2.0, 3.0))
    decision = select_from_spec(root, root / "spec.yaml")

    assert decision["winner"]["schedule"] == "canonical"
    assert decision["schedules"]["epsilon2160"]["eligible"] is False


def test_eligible_fast_pilot_wins_when_canonical_is_ineligible(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path, canonical_regrets=(1.0, 2.0, 3.0),
                       fast_regrets=(-1.0, -2.0, -3.0))

    assert select_from_spec(root, root / "spec.yaml")["winner"]["schedule"] == "epsilon2160"


def test_neither_eligible_pilot_fails_closed(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path, canonical_regrets=(1.0, 2.0, 3.0),
                       fast_regrets=(1.0, 2.0, 3.0))

    with pytest.raises(ValueError, match="neither pilot is validation-eligible"):
        select_from_spec(root, root / "spec.yaml")


def test_rejects_manifest_identity_drift_and_wrong_pilot_controller(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    (root / "manifest.json").write_text('{"different": true}\n')
    with pytest.raises(ValueError, match="manifest identity"):
        select_from_spec(root, root / "spec.yaml")

    root, _ = _fixture(tmp_path / "controller")
    run_manifest_path = root / "results/haichau_network_v2/training/pilot-seed11/run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["controller_id"] = "shared_ddqn_legacy"
    run_manifest_path.write_text(json.dumps(run_manifest))
    _refresh_status_hashes(run_manifest_path.parent)
    with pytest.raises(ValueError, match="pilot provenance"):
        select_from_spec(root, root / "spec.yaml")


def test_rejects_status_artifact_hash_drift(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    run_dir = root / "results/haichau_network_v2/training/pilot-seed11"
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["validation.json"] = "0" * 64
    status_path.write_text(json.dumps(status))

    with pytest.raises(ValueError, match="status artifact hash drift"):
        select_from_spec(root, root / "spec.yaml")


def test_rejects_ineligible_fast_evidence_when_its_baseline_row_drifts(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, _ = _fixture(tmp_path, canonical_regrets=(-1.0, -2.0, -3.0),
                       fast_regrets=(1.0, 2.0, 3.0))
    validation_path = root / "results/haichau_network_v2/training/pilot-epsilon2160-seed11/validation.json"
    validation = json.loads(validation_path.read_text())
    validation["step-4"]["rows"][0]["baseline_queue"] = 999.0
    score = score_validation(validation["step-4"]["rows"])
    score["training_step"] = 4
    validation["step-4"]["score"] = score
    validation_path.write_text(json.dumps(validation))
    selection_path = validation_path.with_name("selection.json")
    selection = json.loads(selection_path.read_text())
    selection["score"] = score
    selection_path.write_text(json.dumps(selection))
    _refresh_status_hashes(validation_path.parent)

    with pytest.raises(ValueError, match="fixed baseline evidence drift"):
        select_from_spec(root, root / "spec.yaml")


def test_rejects_non_epsilon_semantic_config_drift_and_existing_output(tmp_path):
    from traffic_rl.research.pilot_epsilon_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    fast = yaml.safe_load((root / "configs/fast.yaml").read_text())
    fast["model"]["feature_dim"] = 13
    (root / "configs/fast.yaml").write_text(yaml.safe_dump(fast, sort_keys=True))
    with pytest.raises(ValueError, match="only epsilon_decay_decisions"):
        select_from_spec(root, root / "spec.yaml")

    (root / "configs/fast.yaml").write_text(yaml.safe_dump(_config(2160), sort_keys=True))
    (root / spec["decision_output"]).parent.mkdir()
    (root / spec["decision_output"]).write_text("occupied\n")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        select_from_spec(root, root / "spec.yaml")


def test_cli_delegates_to_the_hash_bound_selector(monkeypatch, tmp_path, capsys):
    from scripts import select_haichau_pilot_epsilon as cli

    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "select_from_spec", lambda root, spec: {
        "winner": {"schedule": "canonical"}, "root": str(root), "spec": str(spec)})

    assert cli.main(["--spec", "configs/selector.yaml"]) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["winner"]["schedule"] == "canonical"
    assert written["root"] == str(tmp_path)
