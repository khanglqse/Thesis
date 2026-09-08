import json

import scripts.evaluate_haichau_network as evaluation_script


def test_cli_reads_run_manifest_and_prints_single_json_result(
        tmp_path, monkeypatch, capsys):
    run = {"run_id": "tuned_fixed__case", "resolved_config": {"x": 1}}
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(json.dumps(run))
    expected = {"resolved_config": {"x": 1}, "metrics": {"completed_steps": 1}}
    calls = []

    def fake_evaluate(root, loaded, runtime_dir):
        calls.append((root, loaded, runtime_dir))
        return expected

    monkeypatch.setattr(evaluation_script, "evaluate_run", fake_evaluate)

    assert evaluation_script.main([
        "--run-manifest", str(manifest),
        "--runtime-dir", str(tmp_path / "runtime"),
        "--project-root", str(tmp_path),
    ]) == 0

    assert json.loads(capsys.readouterr().out.strip()) == expected
    assert calls[0][1] == run
