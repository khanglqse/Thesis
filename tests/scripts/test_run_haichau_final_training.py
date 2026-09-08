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


def _training_config(root):
    path = root / "selected.yaml"
    path.write_text(yaml.safe_dump({
        "schema_version": 2,
        "exploration": {"epsilon_decay_decisions": 2160},
    }, sort_keys=True))
    return path


def _complete_run(directory, controller, seed, baseline, training_config):
    artifacts = {}
    for relative in launcher.REQUIRED_ARTIFACTS:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(relative + "\n")
        artifacts[relative] = _sha256(target)
    resolved = yaml.safe_load(training_config.read_text())
    resolved.update({"mode": "final", "learning_seed": seed})
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


def test_build_jobs_covers_both_families_and_uses_pinned_runtime(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}\n")

    jobs = launcher.build_jobs(
        tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
        _training_config(tmp_path))

    assert [(job.controller, job.seed) for job in jobs] == [
        (controller, seed)
        for controller in launcher.CONTROLLERS
        for seed in range(11, 16)
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
    directory = tmp_path / "training" / "final-seed11"
    _complete_run(directory, "neighbor_phase_ddqn", 11, baseline, training_config)
    job = launcher.Job("neighbor_phase_ddqn", 11, directory, ("docker",))

    assert launcher.inspect_existing_job(job, baseline, training_config) == "skipped"

    (directory / "checkpoint" / "weights.npz").write_text("tampered\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        launcher.inspect_existing_job(job, baseline, training_config)

    _complete_run(directory, "neighbor_phase_ddqn", 11, baseline, training_config)
    changed = yaml.safe_load(training_config.read_text())
    changed["exploration"]["epsilon_decay_decisions"] = 10000
    training_config.write_text(yaml.safe_dump(changed, sort_keys=True))
    with pytest.raises(ValueError, match="selected training config"):
        launcher.inspect_existing_job(job, baseline, training_config)


def test_partial_existing_output_refuses_to_launch(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)
    output = tmp_path / "training" / "final-seed11"
    output.mkdir(parents=True)
    _write_json(output / "status.json", {"status": "partial"})

    with pytest.raises(ValueError, match="not a fully verified completed run"):
        launcher.run_campaign(
            tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
            tmp_path / "campaign-status.json", training_config,
            max_concurrency=2,
            runner=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("partial output must prevent launch")),
        )


def test_campaign_records_logs_and_resumes_completed_jobs(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    manifest = _manifest(tmp_path)
    training_config = _training_config(tmp_path)
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
        runner=runner,
    )

    assert len(calls) == 10
    assert first["status"] == "complete"
    assert {item["state"] for item in first["jobs"]} == {"completed"}
    assert all((tmp_path / item["stdout_log"]).read_text() == "trained\n"
               for item in first["jobs"])

    second = launcher.run_campaign(
        tmp_path, manifest, baseline, training, status, training_config,
        max_concurrency=2,
        runner=runner,
    )

    assert len(calls) == 10
    assert {item["state"] for item in second["jobs"]} == {"skipped"}


def test_successful_process_without_verified_output_marks_campaign_failed(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("baseline\n")
    training_config = _training_config(tmp_path)

    result = launcher.run_campaign(
        tmp_path, _manifest(tmp_path), baseline, tmp_path / "training",
        tmp_path / "campaign-status.json", training_config, max_concurrency=1,
        runner=lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    assert result["status"] == "failed"
    assert result["jobs"][0]["state"] == "failed"
    assert "fully verified" in result["jobs"][0]["error"]
