import hashlib
import json
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _spec():
    from traffic_rl.research.final_residual_selector import _DECISION_TYPE
    from traffic_rl.research.pilot_residual_selector import _GATES, _RANKING
    return {
        "schema_version": 1,
        "decision_type": _DECISION_TYPE,
        "controller_family": "schedule_residual_ddqn",
        "mode": "final",
        "learning_seeds": [12, 13, 14, 15, 16],
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "ranking": list(_RANKING),
        "no_eligible": "fail_closed",
        "gates": _GATES,
        "run_dir_template": "results/haichau_network_v2/training/final-seed{seed}",
        "selection_filename": "selection.json",
        "validation_rerun_filename": "validation-rerun.json",
        "manifest": "manifest.json",
        "baseline_tuning_artifact": "baseline.json",
        "pilot_selector_spec": "pilot-spec.yaml",
        "selected_config": "selected.yaml",
    }


def test_final_selector_records_validation_selection_before_enabling_test(tmp_path, monkeypatch):
    from traffic_rl.research import final_residual_selector as selector

    root = tmp_path
    run = root / "results/haichau_network_v2/training/final-seed12"
    source = run / "summary.json"
    _write(source, {"summary": "source"})
    status_path = run / "status.json"
    _write(status_path, {
        "status": "complete",
        "source_tree": {"git_commit": "a" * 40},
        "artifact_sha256": {"summary.json": _sha(source)},
        "eligible_for_test_evaluation": False,
        "reason": "final must pass preregistered per-seed selector",
    })
    spec_path = root / "spec.json"
    _write(spec_path, _spec())

    evaluated = {
        "schema_version": 1,
        "decision_type": "haichau_residual_final_per_seed_selection",
        "status": "selected",
        "learning_seed": 12,
        "test_split_accessed": False,
        "winner": {"checkpoint": "step-4", "training_step": 4},
        "checkpoints": {"step-4": {"eligible": True}},
    }
    rerun = {"schema_version": 1, "test_split_accessed": False}
    monkeypatch.setattr(selector, "_evaluate", lambda *args: (evaluated, rerun))

    decision = selector.select_seed_from_spec(root, spec_path, 12, None)

    assert decision["status"] == "selected"
    status = json.loads(status_path.read_text())
    assert status["eligible_for_test_evaluation"] is True
    assert status["selection"]["path"] == "results/haichau_network_v2/training/final-seed12/selection.json"
    assert status["validation_rerun"]["path"] == "results/haichau_network_v2/training/final-seed12/validation-rerun.json"
    assert (run / "selection.json").is_file()
    assert (run / "validation-rerun.json").is_file()
    assert status["artifact_sha256"]["selection.json"] == _sha(run / "selection.json")
    assert status["artifact_sha256"]["validation-rerun.json"] == _sha(run / "validation-rerun.json")


def test_final_selector_rejection_keeps_test_ineligible(tmp_path, monkeypatch):
    from traffic_rl.research import final_residual_selector as selector

    root = tmp_path
    run = root / "results/haichau_network_v2/training/final-seed12"
    source = run / "summary.json"
    _write(source, {"summary": "source"})
    status_path = run / "status.json"
    _write(status_path, {
        "status": "complete",
        "source_tree": {"git_commit": "a" * 40},
        "artifact_sha256": {"summary.json": _sha(source)},
        "eligible_for_test_evaluation": False,
        "reason": "final must pass preregistered per-seed selector",
    })
    spec_path = root / "spec.json"
    _write(spec_path, _spec())
    monkeypatch.setattr(selector, "_evaluate", lambda *args: ({
        "schema_version": 1,
        "decision_type": "haichau_residual_final_per_seed_selection",
        "status": "rejected",
        "learning_seed": 12,
        "test_split_accessed": False,
        "winner": None,
        "checkpoints": {"step-4": {"eligible": False}},
    }, {"schema_version": 1, "test_split_accessed": False}))

    decision = selector.select_seed_from_spec(root, spec_path, 12, None)

    assert decision["status"] == "rejected"
    status = json.loads(status_path.read_text())
    assert status["eligible_for_test_evaluation"] is False
    assert status["reason"] == "no validation checkpoint passed preregistered gates"
    assert (run / "selection.json").is_file()


def test_registered_final_selector_freezes_all_five_seeds_and_three_checkpoints():
    from traffic_rl.research.final_residual_selector import validate_registered_spec

    root = Path(__file__).resolve().parents[2]
    evidence = validate_registered_spec(
        root, root / "configs/haichau_residual_final_selection_v1.yaml")

    assert evidence == {
        "learning_seeds": [12, 13, 14, 15, 16],
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "test_split_accessed": False,
    }


def test_final_selector_failure_does_not_transition_status(tmp_path, monkeypatch):
    from traffic_rl.research import final_residual_selector as selector

    root = tmp_path
    run = root / "results/haichau_network_v2/training/final-seed12"
    source = run / "summary.json"
    _write(source, {"summary": "source"})
    status_path = run / "status.json"
    original = {
        "status": "complete",
        "source_tree": {"git_commit": "a" * 40},
        "artifact_sha256": {"summary.json": _sha(source)},
        "eligible_for_test_evaluation": False,
        "reason": "final must pass preregistered per-seed selector",
    }
    _write(status_path, original)
    spec_path = root / "spec.json"
    _write(spec_path, _spec())
    monkeypatch.setattr(selector, "_evaluate", lambda *args: (_ for _ in ()).throw(
        ValueError("validation replay failed")))

    import pytest
    with pytest.raises(ValueError, match="validation replay failed"):
        selector.select_seed_from_spec(root, spec_path, 12, None)

    assert json.loads(status_path.read_text()) == original
    assert not (run / "selection.json").exists()
