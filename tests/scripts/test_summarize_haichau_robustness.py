import hashlib
import json

import scripts.summarize_haichau_robustness as summarizer


def test_summarizer_verifies_all_runs_then_writes_exploratory_output(
        tmp_path, monkeypatch):
    campaign = tmp_path / "results/haichau_network_v2/robustness"
    campaign.mkdir(parents=True)
    protocol_path = campaign / "frozen-robustness-protocol.json"
    protocol_path.write_text("{}")
    expected_runs = [{"run_id": "r%d" % i} for i in range(420)]
    (campaign / "campaign-manifest.json").write_text(json.dumps({
        "episode_count": 420, "runs": expected_runs}))
    rows = [{"row": i} for i in range(420)]
    calls = []
    monkeypatch.setattr(summarizer, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(summarizer, "expand_robustness_runs",
                        lambda root, protocol: expected_runs)
    monkeypatch.setattr(
        summarizer, "verify_campaign",
        lambda path, **kwargs: calls.append(("verify", path, kwargs)) or {
            "complete": 420, "total": 420})
    monkeypatch.setattr(summarizer, "load_rows",
                        lambda path, runs: rows)
    monkeypatch.setattr(
        summarizer, "summarize_robustness",
        lambda value: calls.append(("summarize", value)) or {
            "study_role": "exploratory_appendix"})
    monkeypatch.setattr(
        summarizer, "write_robustness_summary",
        lambda path, value: calls.append(("write", path, value)))

    assert summarizer.main([
        "--campaign-dir", str(campaign), "--protocol", str(protocol_path),
    ]) == 0
    assert calls[0] == ("verify", campaign, {
        "require_release_provenance": True, "project_root": tmp_path})
    assert calls[1] == ("summarize", rows)
    assert calls[2][0:2] == ("write", campaign)
    written = calls[2][2]
    assert written["study_role"] == "exploratory_appendix"
    assert written["provenance"] == {
        "frozen_robustness_protocol_sha256": hashlib.sha256(
            protocol_path.read_bytes()).hexdigest(),
        "campaign_manifest_sha256": hashlib.sha256(
            (campaign / "campaign-manifest.json").read_bytes()).hexdigest(),
        "verified_fresh_episodes": 420,
    }
