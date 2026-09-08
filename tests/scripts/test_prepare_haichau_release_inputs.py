import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


CONTROLLERS = ("shared_ddqn_legacy", "neighbor_phase_ddqn")
ALL_CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "prepare_haichau_release_inputs.py"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=True))


def _manifest(root):
    network = root / "network.json"
    phase_contract = root / "phase-contract.json"
    _write(network, {"network": "fixture"})
    _write(phase_contract, {"phase": "fixture"})
    manifest = {
        "protocol_version": 2,
        "network": {
            "path": str(network.relative_to(root)), "sha256": _sha256(network),
        },
        "phase_contract": {
            "path": str(phase_contract.relative_to(root)),
            "sha256": _sha256(phase_contract),
        },
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
        "simulation": {
            "action_interval": 10, "yellow_time": 3,
            "min_green": 20, "maximum_red": 180,
        },
    }
    path = root / "experiment-manifest.json"
    _write(path, manifest)
    return path, manifest


def _training_run(root, controller, seed, manifest, selected_config, duration=35):
    name = ("final-seed%d" % seed if controller == "neighbor_phase_ddqn"
            else "legacy-final-seed%d" % seed)
    run_dir = root / "training" / name
    resolved = json.loads(json.dumps(selected_config))
    resolved.update({
        "mode": "final", "learning_seed": seed,
        "run": selected_config["tiers"]["final"],
    })
    tuning = {
        "selected": {"fixed_green_duration": duration},
        "binding": {"manifest_sha256": _canonical_hash(manifest)},
    }
    tuning["tuning_sha256"] = _canonical_hash(tuning)
    run_manifest = {
        "controller_id": controller, "learning_seed": seed, "mode": "final",
    }
    _write(run_dir / "resolved-config.json", resolved)
    _write(run_dir / "baseline-tuning.json", tuning)
    _write(run_dir / "run-manifest.json", run_manifest)
    artifacts = {
        name: _sha256(run_dir / name)
        for name in ("resolved-config.json", "baseline-tuning.json", "run-manifest.json")
    }
    _write(run_dir / "status.json", {
        "status": "complete", "eligible_for_test_evaluation": True,
        "artifact_sha256": artifacts,
    })
    return run_dir


def _pilot_selection(root, manifest):
    canonical = {
        "schema_version": 2,
        "exploration": {"epsilon_decay_decisions": 10000},
        "reward": {
            "queue_weight": 1.0, "downstream_block_weight": 0.2,
            "switch_penalty": 0.05,
        },
        "tiers": {"final": {"episodes": 80, "horizon_seconds": 3600}},
    }
    fast = json.loads(json.dumps(canonical))
    fast["exploration"]["epsilon_decay_decisions"] = 2160
    paths = {}
    for name, config in (("canonical", canonical), ("epsilon2160", fast)):
        path = root / "configs" / (name + ".yaml")
        _write_yaml(path, config)
        paths[name] = path
    selected_path = root / "configs" / "haichau_training_v2_final_selected.yaml"
    _write_yaml(selected_path, fast)
    source_baseline = root / "training" / "pilot-baseline.json"
    _write(source_baseline, {"baseline": "fixture"})
    schedules = {}
    required = (
        "status.json", "run-manifest.json", "resolved-config.json",
        "baseline-tuning.json", "baseline-tuning-provenance.json",
        "validation.json", "selection.json",
    )
    for name in ("canonical", "epsilon2160"):
        run_dir = root / "training" / ("pilot-" + name)
        artifacts = {}
        for artifact in required:
            _write(run_dir / artifact, {"fixture": artifact})
            artifacts[artifact] = _sha256(run_dir / artifact)
        schedules[name] = {"run_dir": str(run_dir.relative_to(root)),
                           "artifacts": artifacts}
    config_records = {
        name: {
            "path": str(path.relative_to(root)), "sha256": _sha256(path),
            "epsilon_decay_decisions": config["exploration"]["epsilon_decay_decisions"],
        }
        for name, path, config in (("canonical", paths["canonical"], canonical),
                                   ("epsilon2160", paths["epsilon2160"], fast))
    }
    decision = {
        "schema_version": 1,
        "decision_type": "haichau_pilot_epsilon_schedule_selection",
        "inputs": {
            "code_commit": "a" * 40,
            "manifest": {"path": str((root / "experiment-manifest.json").relative_to(root)),
                         "sha256": _sha256(root / "experiment-manifest.json")},
            "baseline_tuning": {"path": str(source_baseline.relative_to(root)),
                               "sha256": _sha256(source_baseline)},
            "configs": config_records,
        },
        "schedules": schedules,
        "winner": {"schedule": "epsilon2160", "config": config_records["epsilon2160"]},
        "selected_config": {"path": str(selected_path.relative_to(root)),
                            "sha256": _sha256(selected_path)},
    }
    decision["decision_identity_sha256"] = _canonical_hash(decision)
    decision_path = root / "results" / "haichau_network_v2" / "training" / "pilot-epsilon-selection.json"
    _write(decision_path, decision)
    return fast, decision_path


def _ready_release(root):
    manifest_path, manifest = _manifest(root)
    selected_config, _ = _pilot_selection(root, manifest)
    runs = {}
    for controller in CONTROLLERS:
        for seed in range(11, 16):
            runs[(controller, seed)] = _training_run(
                root, controller, seed, manifest, selected_config)
    return manifest_path, manifest, runs


def _run_script(root):
    return subprocess.run([
        sys.executable, str(SCRIPT),
        "--project-root", str(root),
        "--manifest", "experiment-manifest.json",
        "--training-root", "training",
        "--output-dir", "release",
    ], cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
       universal_newlines=True)


def test_build_release_inputs_writes_evaluator_ready_index_and_configs(tmp_path):
    manifest_path, manifest, runs = _ready_release(tmp_path)

    result = _run_script(tmp_path)

    index = json.loads((tmp_path / "release" / "training-index.json").read_text())
    config = json.loads(
        (tmp_path / "release" / "final-controller-configs.json").read_text())
    assert index == {
        controller: dict(
            (str(seed), str(runs[(controller, seed)].relative_to(tmp_path)))
            for seed in range(11, 16))
        for controller in CONTROLLERS
    }
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["training_index"] == "release/training-index.json"
    assert config["resolved_config"] == {
        "network_path": manifest["network"]["path"],
        "phase_contract_path": manifest["phase_contract"]["path"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "simulation": manifest["simulation"],
        "reward": {
            "queue_weight": 1.0, "downstream_block_weight": 0.2,
            "switch_penalty": 0.05,
        },
        "step_seconds": 1.0,
        "spillback_queue_threshold": 40.0,
    }
    assert config["controller_configs"] == {
        "tuned_fixed": {"controller_version": 2, "green_duration": 35.0},
        "max_pressure": {"controller_version": 2},
        "hysteretic_mp": {
            "controller_version": 2, "min_hold_decisions": 3,
            "switch_threshold": 2.5,
        },
        "shared_ddqn_legacy": {"controller_version": 2},
        "neighbor_phase_ddqn": {"controller_version": 2},
    }
    assert config["controller_commands"] == dict(
        (controller, ["python3", "scripts/evaluate_haichau_network.py"])
        for controller in ALL_CONTROLLERS)
    assert config["pilot_epsilon_selection"]["winner"]["schedule"] == "epsilon2160"
    assert config["pilot_epsilon_selection"]["selected_config"] == {
        "path": "configs/haichau_training_v2_final_selected.yaml",
        "sha256": _sha256(tmp_path / "configs/haichau_training_v2_final_selected.yaml"),
    }


def test_build_release_inputs_requires_pilot_epsilon_selection(tmp_path):
    manifest_path, manifest = _manifest(tmp_path)
    selected_config = {
        "schema_version": 2, "exploration": {"epsilon_decay_decisions": 2160},
        "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.2,
                   "switch_penalty": 0.05},
        "tiers": {"final": {"episodes": 80, "horizon_seconds": 3600}},
    }
    for controller in CONTROLLERS:
        for seed in range(11, 16):
            _training_run(tmp_path, controller, seed, manifest, selected_config)

    result = _run_script(tmp_path)

    assert result.returncode != 0
    assert "pilot epsilon selection" in result.stderr


def test_build_release_inputs_rejects_a_final_resolved_config_that_drifts_from_selection(tmp_path):
    _, _, runs = _ready_release(tmp_path)
    target = runs[("neighbor_phase_ddqn", 11)]
    resolved_path = target / "resolved-config.json"
    resolved = json.loads(resolved_path.read_text())
    resolved["exploration"]["epsilon_decay_decisions"] = 10000
    _write(resolved_path, resolved)
    status_path = target / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["resolved-config.json"] = _sha256(resolved_path)
    _write(status_path, status)

    result = _run_script(tmp_path)

    assert result.returncode != 0
    assert "differs from selected config" in result.stderr


@pytest.mark.parametrize("mutation, error", [
    ("ineligible", "not complete and eligible"),
    ("hash_drift", "hash drift"),
    ("tuning_hash_drift", "baseline tuning hash drift"),
    ("missing_tuning_binding", "baseline tuning manifest hash drift"),
    ("mixed_duration", "fixed green duration differs"),
    ("missing", "final training directory is missing"),
])
def test_build_release_inputs_refuses_untrustworthy_final_training(
        tmp_path, mutation, error):
    manifest_path, manifest, runs = _ready_release(tmp_path)
    target = runs[("neighbor_phase_ddqn", 11)]
    if mutation == "ineligible":
        status_path = target / "status.json"
        status = json.loads(status_path.read_text())
        status["eligible_for_test_evaluation"] = False
        _write(status_path, status)
    elif mutation == "hash_drift":
        (target / "baseline-tuning.json").write_text("{}\n")
    elif mutation == "tuning_hash_drift":
        tuning_path = target / "baseline-tuning.json"
        tuning = json.loads(tuning_path.read_text())
        tuning["tuning_sha256"] = "0" * 64
        _write(tuning_path, tuning)
        status_path = target / "status.json"
        status = json.loads(status_path.read_text())
        status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
        _write(status_path, status)
    elif mutation == "missing_tuning_binding":
        tuning_path = target / "baseline-tuning.json"
        tuning = json.loads(tuning_path.read_text())
        tuning["binding"] = {}
        tuning.pop("tuning_sha256")
        tuning["tuning_sha256"] = _canonical_hash(tuning)
        _write(tuning_path, tuning)
        status_path = target / "status.json"
        status = json.loads(status_path.read_text())
        status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
        _write(status_path, status)
    elif mutation == "mixed_duration":
        tuning_path = target / "baseline-tuning.json"
        tuning = {
            "selected": {"fixed_green_duration": 30},
            "binding": {"manifest_sha256": _canonical_hash(manifest)},
        }
        tuning["tuning_sha256"] = _canonical_hash(tuning)
        _write(tuning_path, tuning)
        status_path = target / "status.json"
        status = json.loads(status_path.read_text())
        status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
        _write(status_path, status)
    else:
        missing = runs[("shared_ddqn_legacy", 15)]
        for path in sorted(missing.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
        missing.rmdir()

    result = _run_script(tmp_path)
    assert result.returncode != 0
    assert error in result.stderr
