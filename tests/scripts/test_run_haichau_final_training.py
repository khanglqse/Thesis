import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import run_haichau_final_training as launcher


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _manifest(root):
    path = root / "manifest.json"
    _write_json(path, {
        "runtime": {
            "derived_image_tag": "traffic-rl-cityflow-research:v2",
            "platform": "linux/amd64",
        },
    })
    return path


def _training_config(root, name="selected.yaml", behavior_prior=True):
    path = root / name
    config = {
        "schema_version": 3,
        "exploration": {"epsilon_decay_decisions": 2160},
        "tiers": {"final": {
            "episodes": 12, "horizon_seconds": 3600, "eval_every": 4}},
    }
    if behavior_prior:
        config["behavior_prior"] = {
            "type": "fixed_time_behavior_cloning", "bc_epochs": 1,
        }
    path.write_text(yaml.safe_dump(config, sort_keys=True))
    return path


def _complete_run(directory, controller, seed, baseline, training_config):
    artifacts = {}
    for relative in launcher.REQUIRED_ARTIFACTS:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(relative + "\n")
        artifacts[relative] = _sha256(target)
    resolved = yaml.safe_load(training_config.read_text())
    resolved.update({
        "mode": "final", "learning_seed": seed,
        "run": resolved["tiers"]["final"],
    })
    _write_json(directory / "resolved-config.json", resolved)
    artifacts["resolved-config.json"] = _sha256(directory / "resolved-config.json")
    _write_json(directory / "run-manifest.json", {
        "controller_id": controller,
        "learning_seed": seed,
        "baseline_tuning": {
            "mode": "precomputed",
            "source_artifact_sha256": _sha256(baseline),
        },
    })
    artifacts["run-manifest.json"] = _sha256(directory / "run-manifest.json")
    _write_json(directory / "baseline-tuning-provenance.json", {
        "source_artifact_sha256": _sha256(baseline),
    })
    artifacts["baseline-tuning-provenance.json"] = _sha256(
        directory / "baseline-tuning-provenance.json")
    _write_json(directory / "status.json", {
        "status": "complete",
        "eligible_for_test_evaluation": True,
        "artifact_sha256": artifacts,
    })


def _validated_selection_stub(monkeypatch, root, selected):
    decision = root / "pilot-v3-schedule-selection.json"
    decision.write_text("{}\n")
    binding = {"path": str(selected.relative_to(root)),
               "sha256": _sha256(selected)}
    monkeypatch.setattr(
        launcher, "validate_schedule_training_config",
        lambda *args: ({
            "path": str(decision.relative_to(root)), "sha256": "a" * 64,
            "decision_identity_sha256": "b" * 64,
            "primary_learned_controller": "neighbor_phase_ddqn",
            "pilot_learning_seed": 11,
            "winner": {"arm": "schedule_bc_rehearsal",
                       "selected_checkpoint": "step-12"},
            "selected_config": {
                "path": str(selected.relative_to(root)),
                "sha256": _sha256(selected),
                "config": yaml.safe_load(selected.read_text())},
        }, binding))
    return decision


def test_build_jobs_covers_selected_family_and_confirmatory_seeds(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}\n")

    selected = _training_config(tmp_path)
    jobs = launcher.build_jobs(
        tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
        selected)

    assert [(job.controller, job.seed) for job in jobs] == [
        ("neighbor_phase_ddqn", seed) for seed in (12, 13, 14, 15, 16)
    ]
    command = jobs[0].command
    assert list(command[:5]) == ["docker", "run", "--rm", "--platform", "linux/amd64"]
    assert "traffic-rl-cityflow-research:v2" in command
    assert "--baseline-tuning-artifact" in command
    assert "/work/baseline.json" in command
    assert command[command.index("--config") + 1] == "/work/selected.yaml"


def test_existing_completed_output_is_skipped_only_after_hash_and_baseline_checks(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)
    directory = tmp_path / "training" / "final-seed12"
    _complete_run(directory, "neighbor_phase_ddqn", 12, baseline, training_config)
    job = launcher.Job("neighbor_phase_ddqn", 12, directory, ("docker",))

    assert launcher.inspect_existing_job(job, baseline, training_config) == "skipped"

    (directory / "checkpoint" / "weights.npz").write_text("tampered\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        launcher.inspect_existing_job(job, baseline, training_config)

    _complete_run(directory, "neighbor_phase_ddqn", 12, baseline, training_config)
    changed = yaml.safe_load(training_config.read_text())
    changed["exploration"]["epsilon_decay_decisions"] = 10000
    training_config.write_text(yaml.safe_dump(changed, sort_keys=True))
    with pytest.raises(ValueError, match="selected config"):
        launcher.inspect_existing_job(job, baseline, training_config)


def test_existing_completed_output_requires_all_v3_checkpoint_bundles(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)
    directory = tmp_path / "training" / "final-seed12"
    _complete_run(directory, "neighbor_phase_ddqn", 12, baseline, training_config)
    missing = directory / "checkpoints/step-8/contract.json"
    if missing.exists():
        missing.unlink()
    status_path = directory / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"].pop(
        "checkpoints/step-8/contract.json", None)
    _write_json(status_path, status)
    job = launcher.Job("neighbor_phase_ddqn", 12, directory, ("docker",))

    with pytest.raises(ValueError, match="missing checkpoints/step-8/contract.json"):
        launcher.inspect_existing_job(job, baseline, training_config)


def test_partial_existing_output_refuses_to_launch(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)
    decision = _validated_selection_stub(monkeypatch, tmp_path, training_config)
    output = tmp_path / "training" / "final-seed12"
    output.mkdir(parents=True)
    _write_json(output / "status.json", {"status": "partial"})

    with pytest.raises(ValueError, match="not a fully verified completed run"):
        launcher.run_campaign(
            tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
            tmp_path / "campaign-status.json", training_config,
            max_concurrency=2,
            schedule_selection=decision,
            runner=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("partial output must prevent launch")),
        )


def test_campaign_records_logs_and_resumes_completed_jobs(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    manifest = _manifest(tmp_path)
    training_config = _training_config(tmp_path, behavior_prior=True)
    decision = _validated_selection_stub(monkeypatch, tmp_path, training_config)
    training = tmp_path / "training"
    status = tmp_path / "campaign-status.json"
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        output = tmp_path / command[command.index("--output") + 1].removeprefix("/work/")
        controller = command[command.index("--controller-family") + 1]
        seed = int(command[command.index("--learning-seed") + 1])
        _complete_run(output, controller, seed, baseline, training_config)
        kwargs["stdout"].write("trained\n")
        return SimpleNamespace(returncode=0)

    first = launcher.run_campaign(
        tmp_path, manifest, baseline, training, status, training_config,
        max_concurrency=2,
        schedule_selection=decision,
        runner=runner,
    )

    assert len(calls) == 5
    assert first["status"] == "complete"
    assert {item["state"] for item in first["jobs"]} == {"completed"}
    assert all((tmp_path / item["stdout_log"]).read_text() == "trained\n"
               for item in first["jobs"])
    assert first["training_config_binding"] == {
        "path": "selected.yaml", "sha256": _sha256(training_config)}
    assert first["confirmatory_learning_seeds"] == [12, 13, 14, 15, 16]

    second = launcher.run_campaign(
        tmp_path, manifest, baseline, training, status, training_config,
        max_concurrency=2,
        schedule_selection=decision,
        runner=runner,
    )

    assert len(calls) == 5
    assert {item["state"] for item in second["jobs"]} == {"skipped"}


def test_successful_process_without_verified_output_marks_campaign_failed(
        tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)
    decision = _validated_selection_stub(monkeypatch, tmp_path, training_config)

    result = launcher.run_campaign(
        tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
        tmp_path / "campaign-status.json", training_config, max_concurrency=1,
        runner=lambda *args, **kwargs: SimpleNamespace(returncode=0),
        schedule_selection=decision,
    )

    assert result["status"] == "failed"
    assert result["jobs"][0]["state"] == "failed"
    assert "fully verified" in result["jobs"][0]["error"]


def test_final_campaign_refuses_to_run_without_schedule_selection(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)

    with pytest.raises(ValueError, match="schedule selection is required"):
        launcher.run_campaign(
            tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
            tmp_path / "campaign-status.json", training_config)
