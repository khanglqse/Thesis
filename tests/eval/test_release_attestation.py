import hashlib
import inspect
import subprocess

import pytest

import traffic_rl.eval.release_attestation as release_attestation
from traffic_rl.eval.release_attestation import create_attestation, validate_attestation


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args), universal_newlines=True).strip()


def test_production_attestation_api_has_no_runner_or_command_injection():
    assert list(inspect.signature(create_attestation).parameters) == [
        "root", "protocol", "record_path"]


def test_fake_runner_can_only_create_synthetic_ineligible_attestation(tmp_path):
    class Completed(object):
        returncode = 0
        stdout = "fabricated success without running command\n"
        stderr = ""

    record = release_attestation.create_synthetic_attestation(
        tmp_path, {}, runner=lambda *args, **kwargs: Completed(),
        command_specs=(("fake", ("false",), {}),),
        tool_specs=(("fake", ("false",)),))

    assert record["attestation_mode"] == "synthetic_test"
    assert record["passed"] is False
    with pytest.raises(ValueError, match="direct subprocess"):
        validate_attestation(tmp_path, {}, record)


def test_attested_artifact_hash_is_read_from_committed_git_blob(tmp_path):
    subprocess.check_call(["git", "init", "-q", str(tmp_path)])
    _git(tmp_path, "config", "user.email", "fixture@example.test")
    _git(tmp_path, "config", "user.name", "Fixture")
    artifact = tmp_path / "result.json"
    artifact.write_text("committed evidence\n")
    _git(tmp_path, "add", "result.json")
    _git(tmp_path, "commit", "-qm", "evidence")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    expected = hashlib.sha256(b"committed evidence\n").hexdigest()
    artifact.write_text("working tree forgery\n")

    assert release_attestation._git_blob_sha256(
        tmp_path, commit, "result.json") == expected
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() != expected


def test_handwritten_sparse_record_is_not_an_attestation(tmp_path):
    record = {
        "verification_version": 2,
        "passed": True,
        "verified_commit": "a" * 40,
        "commands": ["make test"],
        "tool_versions": {"python": "fixture"},
        "artifact_sha256": {},
    }
    with pytest.raises(ValueError, match="direct subprocess"):
        validate_attestation(tmp_path, {"code_commit": "a" * 40}, record)
