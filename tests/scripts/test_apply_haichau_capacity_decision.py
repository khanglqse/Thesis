import json
from pathlib import Path


def test_capacity_decision_cli_exists():
    path = Path(__file__).parents[2] / "scripts/apply_haichau_capacity_decision.py"
    assert path.is_file()


def test_cli_passes_explicit_validation_and_new_version_modes(monkeypatch, tmp_path, capsys):
    from scripts import apply_haichau_capacity_decision as cli

    calls = []

    def apply(*args, **kwargs):
        calls.append((args, kwargs))
        return {"selected_scale": "0.30", "decision_identity_sha256": "a" * 64}

    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "apply_capacity_decision", apply)
    assert cli.main(["--stage-d", "diagnostics/stage-d", "--validate-only"]) == 0
    assert calls[-1][1]["validate_only"] is True
    assert calls[-1][1]["new_version"] is False
    assert json.loads(capsys.readouterr().out)["selected_scale"] == "0.30"

    assert cli.main(["--stage-d", "diagnostics/stage-d", "--new-version"]) == 0
    assert calls[-1][1]["validate_only"] is False
    assert calls[-1][1]["new_version"] is True
