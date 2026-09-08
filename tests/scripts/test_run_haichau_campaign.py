import json

import scripts.run_haichau_campaign as campaign_script


def test_executor_runs_controller_inside_verified_offline_docker(monkeypatch, tmp_path):
    digest = "sha256:" + "b" * 64
    image = "cityflowproject/cityflow@" + digest
    run = {
        "command": ["python3", "scripts/evaluate.py", "--case", "case-1"],
        "runtime_digest": digest,
        "runtime_image": image,
        "runtime_image_id": digest,
    }
    calls = []

    monkeypatch.setattr(campaign_script, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(campaign_script, "verify_runtime", lambda root, value: {
        "runtime_image": image, "runtime_image_id": digest,
    })

    class Completed(object):
        returncode = 0
        stdout = "log line\n" + json.dumps({
            "resolved_config": {}, "metrics": {},
        }) + "\n"
        stderr = ""

    def execute(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()

    monkeypatch.setattr(campaign_script.subprocess, "run", execute)

    result = campaign_script._subprocess_executor(run, tmp_path / "run")

    assert calls[0][0][:5] == ["docker", "run", "--rm", "--network", "none"]
    assert image in calls[0][0]
    assert calls[0][0][-4:] == run["command"]
    assert result["stdout"].startswith("log line")
