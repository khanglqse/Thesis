import pytest
import json
import hashlib

import scripts.run_haichau_campaign as campaign_script


def test_release_cli_uses_library_owned_docker_executor(monkeypatch, tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "code_commit": "a" * 40,
        "runtime_digest": "sha256:" + "b" * 64,
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": [12, 13, 14, 15, 16],
        "acceptance_rules": {
            "required_learning_seeds": [12, 13, 14, 15, 16]},
        "selection": {"path": "selector.json"},
    }))
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    calls = []
    monkeypatch.setattr(campaign_script, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        campaign_script, "validate_frozen_schedule_selection",
        lambda root, binding: calls.append(("selection", root, binding)))
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
    assert calls == [
        ("selection", tmp_path, {"path": "selector.json"}),
        (campaign_dir, {"project_root": tmp_path}),
    ]


def test_prepare_derives_exact_v3_matrix_from_frozen_protocol(monkeypatch, tmp_path):
    case_manifest = tmp_path / "case-manifest.json"
    case_manifest.write_text("{}")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "case_manifest_sha256": hashlib.sha256(
            case_manifest.read_bytes()).hexdigest(),
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": [12, 13, 14, 15, 16],
        "acceptance_rules": {
            "required_learning_seeds": [12, 13, 14, 15, 16]},
        "selection": {"path": "selector.json"},
    }))
    observed = []
    monkeypatch.setattr(campaign_script, "PROJECT_ROOT", tmp_path)
    selection_calls = []
    monkeypatch.setattr(
        campaign_script, "validate_frozen_schedule_selection",
        lambda root, binding: selection_calls.append((root, binding)))
    monkeypatch.setattr(campaign_script, "bind_frozen_manifest",
                        lambda manifest, frozen: {"bound": True})

    def expand(manifest, seeds, controllers):
        observed.append((manifest, seeds, tuple(controllers)))
        return []

    monkeypatch.setattr(campaign_script, "expand_runs", expand)

    assert campaign_script.main([
        "--campaign-dir", str(tmp_path / "campaign"),
        "--protocol", str(protocol),
        "--manifest", str(case_manifest),
        "--prepare-only",
    ]) == 0
    assert observed == [(
        {"bound": True}, [12, 13, 14, 15, 16],
        ("tuned_fixed", "max_pressure", "hysteretic_mp",
         "neighbor_phase_ddqn"))]
    assert selection_calls == [(tmp_path, {"path": "selector.json"})]


def test_residual_protocol_requires_all_five_frozen_selector_records():
    from scripts.run_haichau_campaign import _validate_protocol_selection

    protocol = {
        "primary_learned_controller": "schedule_residual_ddqn",
        "selection": {"test_split_accessed": False,
                      "decisions": dict((str(seed), {"path": "x"})
                                        for seed in (12, 13, 14, 15, 16))},
    }
    assert _validate_protocol_selection(None, protocol) == (12, 13, 14, 15, 16)
    del protocol["selection"]["decisions"]["16"]
    with pytest.raises(ValueError, match="residual selector"):
        _validate_protocol_selection(None, protocol)
