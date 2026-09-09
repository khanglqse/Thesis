import json

import scripts.evaluate_haichau_robustness as evaluator


def test_evaluator_routes_only_frozen_manifest_to_robustness_runtime(
        tmp_path, monkeypatch, capsys):
    run = {"run_id": "frozen"}
    manifest = tmp_path / "run.json"
    manifest.write_text(json.dumps(run))
    calls = []
    monkeypatch.setattr(
        evaluator, "evaluate_robustness_run",
        lambda root, received, runtime: calls.append(
            (root, received, runtime)) or {"metrics": {"completed_steps": 3600}})

    assert evaluator.main([
        "--run-manifest", str(manifest),
        "--runtime-dir", str(tmp_path / "runtime"),
        "--project-root", str(tmp_path),
    ]) == 0
    assert calls == [(tmp_path, run, tmp_path / "runtime")]
    assert json.loads(capsys.readouterr().out)["metrics"]["completed_steps"] == 3600
