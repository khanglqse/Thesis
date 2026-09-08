import json

import scripts.summarize_haichau_campaign as summarize


def test_summary_revalidates_v3_selector_and_uses_frozen_primary(
        monkeypatch, tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "selection": {"path": "selector.json"},
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": [12, 13, 14, 15, 16],
        "acceptance_rules": {
            "required_learning_seeds": [12, 13, 14, 15, 16],
            "required_regimes": ["normal", "am_peak", "pm_peak"],
        },
    }))
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    selections = []
    calls = []
    monkeypatch.setattr(summarize, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        summarize, "validate_frozen_schedule_selection",
        lambda root, binding: selections.append((root, binding)))
    monkeypatch.setattr(summarize, "_load_runs", lambda path: [])

    def aggregate(rows, **kwargs):
        calls.append((rows, kwargs))
        return {"_metadata": {
            "primary_learned_controller": kwargs[
                "primary_learned_controller"]}}

    monkeypatch.setattr(summarize, "aggregate_campaign", aggregate)
    monkeypatch.setattr(
        summarize, "evaluate_acceptance", lambda summary: {"accepted": False})

    assert summarize.main([
        "--campaign-dir", str(campaign_dir),
        "--protocol", str(protocol),
    ]) == 0
    assert selections == [(tmp_path, {"path": "selector.json"})]
    assert calls[0][1]["primary_learned_controller"] == "neighbor_phase_ddqn"
    assert calls[0][1]["required_learning_seeds"] == [12, 13, 14, 15, 16]
