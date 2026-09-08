import json

from scripts import diagnose_haichau_pressure as cli


def test_cli_uses_training_env_and_final_horizon_without_training(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"simulation": {"action_interval": 10}}))
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: 2\ntiers:\n  final: {horizon_seconds: 3600}\n")
    captured = {}

    def make_factory(loaded, resolved, output, family):
        captured["resolved"] = resolved
        captured["family"] = family
        return "training-env-factory"

    def diagnostic(factory, loaded, resolved, artifact, output, root):
        captured["factory"] = factory
        captured["artifact"] = artifact
        captured["output"] = str(output)
        return {"status": "diagnostic_complete", "rows": []}

    monkeypatch.setattr(cli, "_make_env_factory", make_factory, raising=False)
    monkeypatch.setattr(cli, "evaluate_pressure_validation", diagnostic, raising=False)
    assert cli.main(["--manifest", str(manifest), "--config", str(config),
                     "--baseline-tuning-artifact", "baseline.json",
                     "--output", str(tmp_path / "diagnostic")]) == 0
    assert captured["factory"] == "training-env-factory"
    assert captured["family"] == "neighbor_phase_ddqn"
    assert captured["resolved"]["run"]["horizon_seconds"] == 3600
    assert captured["artifact"].endswith("baseline.json")
    assert captured["output"] == str(tmp_path / "diagnostic")
