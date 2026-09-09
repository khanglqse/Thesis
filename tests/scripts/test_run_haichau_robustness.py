import json

import scripts.run_haichau_robustness as runner


def test_prepare_derives_exact_frozen_matrix_without_seed_or_controller_override(
        tmp_path, monkeypatch):
    campaign = tmp_path / "results/haichau_network_v2/robustness"
    campaign.mkdir(parents=True)
    protocol_path = campaign / "frozen-robustness-protocol.json"
    protocol_path.write_text(json.dumps({"episode_count": 420}))
    runs = [{"run_id": "r%d" % i} for i in range(420)]
    calls = []
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "expand_robustness_runs",
        lambda root, protocol: calls.append((root, protocol)) or runs)
    monkeypatch.setattr(
        runner, "write_campaign_manifest",
        lambda path, value: calls.append((path, value)) or {"runs": value})

    assert runner.main([
        "--campaign-dir", str(campaign), "--protocol", str(protocol_path),
        "--prepare-only",
    ]) == 0
    assert calls == [(tmp_path, {"episode_count": 420}), (campaign, runs)]


def test_execution_uses_shared_trusted_runner_and_rejects_manifest_drift(
        tmp_path, monkeypatch):
    campaign = tmp_path / "results/haichau_network_v2/robustness"
    campaign.mkdir(parents=True)
    protocol_path = campaign / "frozen-robustness-protocol.json"
    protocol_path.write_text("{}")
    expected = [{"run_id": "r%d" % i} for i in range(420)]
    (campaign / "campaign-manifest.json").write_text(json.dumps({
        "campaign_version": 3, "evidence_namespace": "haichau_network_v2",
        "appendix_evidence_namespace": "haichau_network_v2/robustness",
        "study_role": "exploratory_appendix", "episode_count": 420,
        "runs": expected,
    }))
    calls = []
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "expand_robustness_runs",
                        lambda root, protocol: expected)
    monkeypatch.setattr(
        runner, "run_pending",
        lambda path, project_root: calls.append((path, project_root)) or {
            "completed": 420, "failed": 0, "skipped": 0, "total": 420})

    assert runner.main([
        "--campaign-dir", str(campaign), "--protocol", str(protocol_path),
    ]) == 0
    assert calls == [(campaign, tmp_path)]

    document = json.loads((campaign / "campaign-manifest.json").read_text())
    document["runs"][0]["run_id"] = "drift"
    (campaign / "campaign-manifest.json").write_text(json.dumps(document))
    try:
        runner.main([
            "--campaign-dir", str(campaign), "--protocol", str(protocol_path),
        ])
    except ValueError as exc:
        assert "differs from frozen" in str(exc)
    else:
        raise AssertionError("campaign drift was accepted")
