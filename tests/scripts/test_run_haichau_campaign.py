import json

import scripts.run_haichau_campaign as campaign_script


def test_release_cli_uses_library_owned_docker_executor(monkeypatch, tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "code_commit": "a" * 40,
        "runtime_digest": "sha256:" + "b" * 64,
    }))
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    calls = []
    monkeypatch.setattr(campaign_script, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        campaign_script, "verify_git_checkout",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("run manifests must precede release verification")))
    monkeypatch.setattr(
        campaign_script, "verify_runtime",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("run_pending owns runtime verification")))

    def run_pending(campaign, **kwargs):
        calls.append((campaign, kwargs))
        return {"completed": 1, "failed": 0, "skipped": 0, "total": 1}

    monkeypatch.setattr(campaign_script, "run_pending", run_pending)

    assert campaign_script.main([
        "--campaign-dir", str(campaign_dir),
        "--protocol", str(protocol),
    ]) == 0
    assert calls == [(campaign_dir, {"project_root": tmp_path})]
