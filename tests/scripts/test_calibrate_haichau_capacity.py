import json

from scripts import calibrate_haichau_capacity as cli


def test_cli_defaults_to_immutable_preparation_without_execution(monkeypatch, tmp_path):
    calls = []

    def prepare(*args, **kwargs):
        calls.append(("prepare", args, kwargs))
        return {"runs": [{"run_id": "one"}],
                "campaign_identity_sha256": "a" * 64}

    monkeypatch.setattr(cli, "prepare_campaign", prepare)
    monkeypatch.setattr(
        cli, "execute_campaign",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("default command must not execute CityFlow")))

    assert cli.main(["--stage", "ladder", "--output", str(tmp_path)]) == 0
    assert calls[0][0] == "prepare"
    assert calls[0][2]["stage"] == "ladder"
    assert calls[0][2]["chosen_scales"] is None


def test_cli_execution_is_explicit_and_parses_registered_scales(monkeypatch, tmp_path,
                                                                capsys):
    captured = {}

    def prepare(*args, **kwargs):
        captured["chosen"] = kwargs["chosen_scales"]
        return {"runs": [], "campaign_identity_sha256": "b" * 64}

    def execute(root, output):
        captured["execute"] = (root, output)
        return {"status": "diagnostic_complete", "completed": 24,
                "failed": 0, "total": 24}

    monkeypatch.setattr(cli, "prepare_campaign", prepare)
    monkeypatch.setattr(cli, "execute_campaign", execute)

    assert cli.main(["--stage", "stage-d", "--chosen-scales", "0.25,0.30",
                     "--output", str(tmp_path), "--execute"]) == 0
    assert captured["chosen"] == [0.25, 0.3]
    assert captured["execute"][1] == tmp_path
    assert json.loads(capsys.readouterr().out)["eligible_for_release"] is False


def test_cli_returns_nonzero_when_any_diagnostic_run_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli, "prepare_campaign",
        lambda *args, **kwargs: {"runs": [], "campaign_identity_sha256": "c" * 64})
    monkeypatch.setattr(
        cli, "execute_campaign",
        lambda *args, **kwargs: {"status": "diagnostic_partial", "completed": 2,
                                 "failed": 1, "total": 3})

    assert cli.main(["--stage", "scale1", "--output", str(tmp_path),
                     "--execute"]) == 1
