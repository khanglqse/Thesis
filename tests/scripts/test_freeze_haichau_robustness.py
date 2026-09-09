from pathlib import Path

import pytest

import scripts.freeze_haichau_robustness as freezer


def test_freeze_cli_uses_only_canonical_primary_protocol(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(freezer, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        freezer, "freeze_robustness_protocol",
        lambda root, primary, config, output: calls.append(
            (root, primary, config, output)) or {
                "episode_count": 420,
                "study_role": "exploratory_appendix",
            })

    assert freezer.main([]) == 0

    assert calls == [(
        tmp_path,
        tmp_path / "results/haichau_network_v2/final/frozen-protocol.json",
        "configs/haichau_robustness_v3.yaml",
        "results/haichau_network_v2/robustness",
    )]


def test_freeze_cli_has_no_alternate_primary_protocol_option():
    with pytest.raises(SystemExit):
        freezer.main(["--primary-protocol", str(Path("copied/frozen-protocol.json"))])
