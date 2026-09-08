import subprocess
import json
from pathlib import Path

import pytest
import yaml

from traffic_rl.eval.checkpoint_selection import score_validation
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.sim.phase_encoder import SCHEDULE_CONTEXT_FEATURES
from traffic_rl.train.network_trainer import canonical_json_sha256
from tests.research.test_pilot_behavior_selector import (
    _fixture as _behavior_fixture, _git, _refresh_status, _sha256, _write)


ROOT = Path(__file__).resolve().parents[2]


def _fixture(tmp_path):
    root, old_spec = _behavior_fixture(tmp_path)
    mapping = {
        "schedule_bc_rehearsal": "bc_prior",
        "schedule_bc_no_rehearsal": "bc_only",
    }
    arms = {}
    for arm, old_arm in mapping.items():
        old_config_path = root / "configs" / (old_arm + ".yaml")
        config = yaml.safe_load(old_config_path.read_text())
        config["model"]["feature_dim"] = 15
        config["tiers"]["final"] = {
            "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
        config["observation"] = {
            "schema_version": 3,
            "type": "phase_rows_fixed_schedule_context",
            "phase_row_identity": "cycle_fraction",
            "global_cycle": {
                "encoding": "sin_cos", "green_duration_seconds": 25,
                "period": "green_duration_times_selectable_green_count"},
        }
        prior = config["behavior_prior"]
        prior["reference_probability_start"] = 0.0
        prior["reference_probability_end"] = 0.0
        prior["pre_rl_validation"] = True
        prior["rehearsal"] = {
            "enabled": arm == "schedule_bc_rehearsal",
            "type": "behavior_clone", "every_td_updates": 1,
            "batch_size": 4}
        config_path = root / "configs" / (arm + ".yaml")
        _write(config_path, yaml.safe_dump(config, sort_keys=True))
        run_dir = root / old_spec["arms"][old_arm]["run_dir"]
        resolved = json.loads((run_dir / "resolved-config.json").read_text())
        run_manifest = json.loads((run_dir / "run-manifest.json").read_text())
        source_tree = {
            "schema_version": 1, "git_commit": run_manifest["code_commit"],
            "tracked_worktree": "clean", "index": "clean",
            "untracked_files_policy": "allowed"}
        for key, value in config.items():
            resolved[key] = value
        execution_config = dict(config)
        execution_config.update({
            "mode": "pilot", "learning_seed": 11,
            "run": config["tiers"]["pilot"]})
        resolved["training_config_sha256"] = canonical_json_sha256(
            execution_config)
        resolved["source_tree"] = source_tree
        _write(run_dir / "resolved-config.json", resolved)
        behavior_path = run_dir / "behavior-prior.json"
        behavior = json.loads(behavior_path.read_text())
        behavior.update({
            "schema_version": 2,
            "loss_name": "conditional_cross_entropy",
            "labels": 10,
            "switch_eligible_labels": 10,
            "conditional_cross_entropy": 0.2,
            "top1_agreement": 0.8,
        })
        _write(behavior_path, behavior)
        validation_path = run_dir / "validation.json"
        validation = json.loads(validation_path.read_text())
        for evidence in validation.values():
            for row in evidence["rows"]:
                audit = row["policy_audit"]
                audit.update({
                    "switch_eligible_decisions": 20,
                    "switch_eligible_reference_disagreements": 2,
                    "switch_eligible_reference_disagreement_rate": 0.1,
                })
        step_zero_rows = json.loads(json.dumps(validation["step-4"]["rows"]))
        step_zero_score = score_validation(step_zero_rows)
        step_zero_score["training_step"] = 0
        validation["step-0"] = {
            "diagnostic_only": True, "selectable": False,
            "rows": step_zero_rows, "score": step_zero_score}
        _write(validation_path, validation)
        _write(run_dir / "summary.json", {"behavior_rehearsal": {
            "enabled": prior["rehearsal"]["enabled"],
            "source_split": "train",
            "updates": 1 if prior["rehearsal"]["enabled"] else 0}})
        manifest_hash = resolved["manifest_sha256"]
        for step in (4, 8, 12):
            checkpoint = run_dir / "checkpoints" / ("step-%d" % step)
            checkpoint_contract = {
                "controller_family": "neighbor_phase_ddqn",
                "obs_schema_version": 3,
                "training_step": step,
                "feature_dim": 15,
                "hidden_size": config["model"]["hidden"],
                "feature_order": list(SCHEDULE_CONTEXT_FEATURES),
                "observation": config["observation"],
                "behavior_prior": config["behavior_prior"],
                "manifest_sha256": manifest_hash,
                "baseline_tuning_sha256": resolved["baseline_tuning_sha256"],
                "training_config_sha256": resolved["training_config_sha256"],
                "source_tree": source_tree,
            }
            PhaseScoringDDQN(
                15, hidden=config["model"]["hidden"],
                lr=config["model"]["lr"], seed=step).save_bundle(
                    str(checkpoint), checkpoint_contract)
        status = json.loads((run_dir / "status.json").read_text())
        status["artifact_sha256"]["summary.json"] = _sha256(
            run_dir / "summary.json")
        for step in (4, 8, 12):
            for name in ("contract.json", "weights.npz"):
                relative = "checkpoints/step-%d/%s" % (step, name)
                status["artifact_sha256"][relative] = _sha256(
                    run_dir / relative)
        run_manifest["source_tree"] = source_tree
        _write(run_dir / "run-manifest.json", run_manifest)
        _write(run_dir / "status.json", status)
        _refresh_status(run_dir)
        arms[arm] = {"config": str(config_path.relative_to(root)),
                     "run_dir": str(run_dir.relative_to(root))}
    spec = dict(old_spec)
    spec.update({
        "decision_type": "haichau_pilot_schedule_rehearsal_selection",
        "diagnostic_checkpoint": "step-0",
        "arms": arms,
        "decision_output": "output/schedule-decision.json",
        "selected_config_output": "output/schedule-selected.yaml",
    })
    _write(root / "schedule-spec.yaml", yaml.safe_dump(spec, sort_keys=True))
    return root, spec


def test_registered_v3_schedule_configs_differ_only_by_rehearsal_enabled():
    from traffic_rl.research.pilot_schedule_selector import validate_registered_configs

    evidence = validate_registered_configs(
        ROOT, ROOT / "configs/haichau_pilot_schedule_selection_v1.yaml")

    assert set(evidence) == {
        "schedule_bc_rehearsal", "schedule_bc_no_rehearsal"}
    assert evidence["schedule_bc_rehearsal"]["rehearsal_enabled"] is True
    assert evidence["schedule_bc_no_rehearsal"]["rehearsal_enabled"] is False
    assert all(item["feature_dim"] == 15 for item in evidence.values())
    assert all(item["final_tier"] == {
        "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
        for item in evidence.values())
    smoke = yaml.safe_load((
        ROOT / "configs/haichau_training_v3_schedule_smoke.yaml").read_text())
    assert smoke["tiers"]["final"] == {
        "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}


def test_schedule_quality_uses_only_switch_eligible_disagreement():
    from traffic_rl.research.pilot_schedule_selector import validation_quality

    baseline = {}
    rows = []
    for index, scenario in enumerate(
            ("normal", "normal", "am_peak", "am_peak", "pm_peak", "pm_peak")):
        case_id = "case-%d" % index
        baseline[case_id] = {
            "case_id": case_id, "scenario": scenario,
            "queue_integral_vehicle_seconds": 100.0,
            "completion_rate": 1.0, "insertion_rate": 1.0}
        rows.append({
            "case_id": case_id, "scenario": scenario,
            "baseline_queue": 100.0, "candidate_queue": 99.0,
            "baseline_completion": 1.0, "candidate_completion": 0.99,
            "baseline_insertion": 1.0, "candidate_insertion": 0.99,
            "policy_audit": {
                "evaluation_policy": "raw_ddqn_greedy",
                "eligible_decisions": 1000,
                "reference_disagreements": 0,
                "reference_disagreement_rate": 0.0,
                "switch_eligible_decisions": 100,
                "switch_eligible_reference_disagreements": 10,
                "switch_eligible_reference_disagreement_rate": 0.1,
            }})

    quality = validation_quality(rows, baseline, 0.01)

    assert quality["switch_eligible_reference_disagreement_rate"] == 0.1
    assert quality["reference_disagreement_gate"] is True


def test_registered_selector_reaches_missing_pilot_gate_without_test_access(
        monkeypatch):
    import traffic_rl.research.pilot_schedule_selector as selector
    commit = _git(ROOT, "rev-parse", "HEAD")
    monkeypatch.setattr(selector, "_tracked_tree_attestation", lambda root: {
        "schema_version": 1, "git_commit": commit,
        "tracked_worktree": "clean", "index": "clean",
        "untracked_files_policy": "allowed"})

    with pytest.raises(ValueError, match="schedule_bc_rehearsal pilot run.*missing"):
        selector.select_from_spec(
            ROOT, ROOT / "configs/haichau_pilot_schedule_selection_v1.yaml")


def test_selects_v3_arm_and_keeps_step_zero_diagnostic_only(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, spec = _fixture(tmp_path)
    decision = select_from_spec(root, root / "schedule-spec.yaml")

    assert decision["winner"]["arm"] == "schedule_bc_no_rehearsal"
    assert decision["diagnostic_checkpoint"] == "step-0"
    assert decision["arms"]["schedule_bc_no_rehearsal"][
        "step_0_diagnostic"]["selectable"] is False
    assert yaml.safe_load((root / spec["selected_config_output"]).read_text())[
        "behavior_prior"]["rehearsal"]["enabled"] is False


def test_final_release_validator_binds_v3_decision_and_selected_config(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import (
        select_from_spec, validate_final_schedule_selection,
        validate_frozen_schedule_selection)

    root, spec = _fixture(tmp_path)
    decision = select_from_spec(root, root / "schedule-spec.yaml")

    validated = validate_final_schedule_selection(
        root, root / spec["decision_output"])

    assert validated["decision_identity_sha256"] == decision[
        "decision_identity_sha256"]
    assert validated["primary_learned_controller"] == "neighbor_phase_ddqn"
    assert validated["winner"]["selected_checkpoint"] in {
        "step-4", "step-8", "step-12"}
    assert validated["selected_config"]["config"]["tiers"]["final"] == {
        "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
    compact = dict((key, value) for key, value in validated.items()
                   if key != "selected_config")
    compact["selected_config"] = dict(
        (key, value) for key, value in validated["selected_config"].items()
        if key != "config")
    assert validate_frozen_schedule_selection(root, compact) == validated

    compact["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="binding drift"):
        validate_frozen_schedule_selection(root, compact)


def test_final_release_validator_rejects_selected_config_hash_drift(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import (
        select_from_spec, validate_final_schedule_selection)

    root, spec = _fixture(tmp_path)
    select_from_spec(root, root / "schedule-spec.yaml")
    selected = root / spec["selected_config_output"]
    config = yaml.safe_load(selected.read_text())
    config["tiers"]["final"]["episodes"] = 80
    selected.write_text(yaml.safe_dump(config, sort_keys=True))

    with pytest.raises(ValueError, match="selected config.*hash drift"):
        validate_final_schedule_selection(root, root / spec["decision_output"])


def test_final_release_validator_recomputes_winner_rank_from_source_rows(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import (
        select_from_spec, validate_final_schedule_selection)

    root, spec = _fixture(tmp_path)
    select_from_spec(root, root / "schedule-spec.yaml")
    decision_path = root / spec["decision_output"]
    decision = json.loads(decision_path.read_text())
    winner = decision["winner"]["arm"]
    forged_rank = [-999.0, -999.0, 4, winner]
    decision["arms"][winner]["rank_tuple"] = forged_rank
    decision["winner"]["rank_tuple"] = forged_rank
    decision.pop("decision_identity_sha256")
    decision["decision_identity_sha256"] = canonical_json_sha256(decision)
    _write(decision_path, decision)

    with pytest.raises(ValueError, match="differs from source evidence"):
        validate_final_schedule_selection(root, decision_path)


def test_final_resolved_config_requires_exact_v3_tier_and_confirmatory_seed():
    from traffic_rl.research.pilot_schedule_selector import (
        validate_final_resolved_config)

    selected = {
        "schema_version": 3,
        "tiers": {"final": {
            "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}},
    }
    resolved = dict(selected)
    resolved.update({
        "mode": "final", "learning_seed": 12,
        "run": selected["tiers"]["final"],
    })
    validate_final_resolved_config(resolved, selected, 12)

    pilot_seed = dict(resolved, learning_seed=11)
    with pytest.raises(ValueError, match="confirmatory seed"):
        validate_final_resolved_config(pilot_seed, selected, 11)

    wrong_tier = json.loads(json.dumps(resolved))
    wrong_tier["run"]["episodes"] = 80
    with pytest.raises(ValueError, match="tier"):
        validate_final_resolved_config(wrong_tier, selected, 12)


def test_schedule_selector_rejects_held_out_metric_before_freeze(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    run_dir = root / "training/pilot-bc_prior-seed11"
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    validation["step-4"]["rows"][0]["held_out_test_metric"] = 1.0
    _write(validation_path, validation)
    _refresh_status(run_dir)

    with pytest.raises(ValueError, match="held-out test evidence"):
        select_from_spec(root, root / "schedule-spec.yaml")


def test_rejects_selectable_step_zero_diagnostic(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    run_dir = root / "training/pilot-bc_prior-seed11"
    path = run_dir / "validation.json"
    validation = json.loads(path.read_text())
    validation["step-0"]["selectable"] = True
    _write(path, validation)
    _refresh_status(run_dir)

    with pytest.raises(ValueError, match="step-0 diagnostic"):
        select_from_spec(root, root / "schedule-spec.yaml")


def test_rejects_swapped_checkpoint_training_steps(tmp_path):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    run_dir = root / "training/pilot-bc_prior-seed11"
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    validation["step-4"]["score"]["training_step"] = 8
    validation["step-8"]["score"]["training_step"] = 4
    selection = json.loads((run_dir / "selection.json").read_text())
    selection["selected_checkpoint"] = "step-8"
    selection["score"] = validation["step-8"]["score"]
    _write(validation_path, validation)
    _write(run_dir / "selection.json", selection)
    _refresh_status(run_dir)

    with pytest.raises(ValueError, match="training_step.*checkpoint"):
        select_from_spec(root, root / "schedule-spec.yaml")


@pytest.mark.parametrize("kind, message", [
    ("tracked", "tracked worktree"), ("staged", "index")])
def test_selector_rejects_dirty_tracked_or_index_tree(
        tmp_path, kind, message):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    if kind == "tracked":
        path = root / "manifest.json"
        path.write_text(path.read_text() + "\n")
    else:
        _write(root / "staged.txt", "staged")
        _git(root, "add", "staged.txt")

    with pytest.raises(ValueError, match=message):
        select_from_spec(root, root / "schedule-spec.yaml")


@pytest.mark.parametrize("kind", ["deleted_contract", "tampered_weights"])
def test_selector_requires_hash_bound_intermediate_checkpoint_bundles(
        tmp_path, kind):
    from traffic_rl.research.pilot_schedule_selector import select_from_spec

    root, _ = _fixture(tmp_path)
    checkpoint = root / "training/pilot-bc_prior-seed11/checkpoints/step-8"
    if kind == "deleted_contract":
        (checkpoint / "contract.json").unlink()
    else:
        (checkpoint / "weights.npz").write_text("tampered")
        _refresh_status(root / "training/pilot-bc_prior-seed11")

    with pytest.raises(ValueError, match="checkpoint|artifact hash"):
        select_from_spec(root, root / "schedule-spec.yaml")


def test_schedule_selector_cli_is_directly_invocable():
    completed = subprocess.run(
        ["python3", "scripts/select_haichau_pilot_schedule.py", "--help"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)

    assert completed.returncode == 0, completed.stderr
    assert "schedule-rehearsal" in completed.stdout
