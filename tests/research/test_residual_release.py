import hashlib
from pathlib import Path

import pytest
import yaml


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _selected_config():
    return {
        "schema_version": 1,
        "controller_family": "schedule_residual_ddqn",
        "mode": "pilot",
        "learning_seed": 11,
        "macro": {"duration_seconds": 300, "shift_seconds": 10,
                  "baseline_green_seconds": 25},
        "pilot_selection": {
            "decision_type": "haichau_residual_pilot_selection",
            "selected_checkpoint": "step-4",
            "training_step": 4,
            "test_split_accessed": False,
        },
    }


def _decision(path, root=None):
    return {
        "schema_version": 1,
        "decision_type": "haichau_residual_pilot_selection",
        "status": "selected",
        "winner": {"checkpoint": "step-4", "training_step": 4,
                   "checkpoint_artifacts": {"weights_sha256": "a" * 64}},
        "selected_config": {"path": str(path.relative_to(root)) if root else str(path), "sha256": _sha(path)},
        "test_split_accessed": False,
    }


def _write_selected(tmp_path):
    selected = tmp_path / "selected.yaml"
    selected.write_text(yaml.safe_dump(_selected_config(), sort_keys=True))
    return selected


def test_final_config_binds_revalidated_selected_output(tmp_path, monkeypatch):
    from traffic_rl.research import residual_release

    selected = _write_selected(tmp_path)
    decision = _decision(selected, tmp_path)
    monkeypatch.setattr(residual_release, "validate_selected_outputs",
                        lambda root, spec, validation_runner=None: decision)

    config, binding = residual_release.resolve_final_residual_config(
        tmp_path, "selector.yaml", selected, 12)

    assert config["mode"] == "final"
    assert config["learning_seed"] == 12
    assert config["run"] == {"episodes": 12, "horizon_seconds": 3600,
                              "eval_every": 4}
    assert config["final_release"]["selection"] == binding
    assert binding["selected_checkpoint"] == "step-4"
    assert binding["selected_config"]["sha256"] == _sha(selected)
    assert binding["test_split_accessed"] is False


@pytest.mark.parametrize("seed", [11, 17, 0])
def test_final_config_rejects_nonconfirmatory_seed(tmp_path, monkeypatch, seed):
    from traffic_rl.research import residual_release

    selected = _write_selected(tmp_path)
    monkeypatch.setattr(residual_release, "validate_selected_outputs",
                        lambda *args, **kwargs: _decision(selected, tmp_path))
    with pytest.raises(ValueError, match="final residual seed"):
        residual_release.resolve_final_residual_config(
            tmp_path, "selector.yaml", selected, seed)


def test_final_config_rejects_selected_yaml_hash_drift(tmp_path, monkeypatch):
    from traffic_rl.research import residual_release

    selected = _write_selected(tmp_path)
    decision = _decision(selected, tmp_path)
    decision["selected_config"]["sha256"] = "0" * 64
    monkeypatch.setattr(residual_release, "validate_selected_outputs",
                        lambda *args, **kwargs: decision)
    with pytest.raises(ValueError, match="selected config hash"):
        residual_release.resolve_final_residual_config(
            tmp_path, "selector.yaml", selected, 12)


def test_final_config_rejects_pilot_or_test_tainted_selection(tmp_path, monkeypatch):
    from traffic_rl.research import residual_release

    selected = _write_selected(tmp_path)
    decision = _decision(selected, tmp_path)
    decision["test_split_accessed"] = True
    monkeypatch.setattr(residual_release, "validate_selected_outputs",
                        lambda *args, **kwargs: decision)
    with pytest.raises(ValueError, match="test split"):
        residual_release.resolve_final_residual_config(
            tmp_path, "selector.yaml", selected, 12)
