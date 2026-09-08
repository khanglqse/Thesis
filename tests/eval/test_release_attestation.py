import json
import subprocess

import pytest

import traffic_rl.eval.release_attestation as release_attestation
from traffic_rl.eval.release_attestation import (
    RELEASE_ARTIFACTS,
    create_attestation,
    validate_attestation,
)


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args),
        universal_newlines=True).strip()


def _commit(root, message):
    _git(root, "add", ".")
    _git(root, "commit", "-qm", message)
    return _git(root, "rev-parse", "HEAD")


def test_generator_executes_commands_and_validator_requires_hashed_logs(
        tmp_path, monkeypatch):
    subprocess.check_call(["git", "init", "-q", str(tmp_path)])
    _git(tmp_path, "config", "user.email", "fixture@example.test")
    _git(tmp_path, "config", "user.name", "Fixture")
    generator = tmp_path / "scripts/attest_haichau_release.py"
    generator.parent.mkdir(parents=True)
    generator.write_text("# fixture generator\n")
    for relative in RELEASE_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    run_status = tmp_path / "results/haichau_network_v2/final/runs/run-1/status.json"
    run_status.parent.mkdir(parents=True, exist_ok=True)
    run_status.write_text(json.dumps({"status": "complete"}))
    commit = _commit(tmp_path, "release inputs")
    protocol = {"code_commit": commit}
    runtime = {
        "runtime_image": "fixture@sha256:" + "a" * 64,
        "runtime_image_id": "sha256:" + "b" * 64,
        "runtime_digest": "sha256:" + "a" * 64,
    }
    monkeypatch.setattr(
        release_attestation, "verify_runtime", lambda root, value: runtime)
    command_specs = (("smoke", ("python3", "-c", "print('ok')"), {}),)
    tool_specs = (("python", ("python3", "--version")),)

    record = create_attestation(
        tmp_path, protocol, command_specs=command_specs, tool_specs=tool_specs)

    assert record["passed"] is True
    assert (tmp_path / record["commands"][0]["stdout_path"]).read_text() == "ok\n"
    _commit(tmp_path, "attestation")
    evidence = validate_attestation(
        tmp_path, protocol, record,
        command_specs=command_specs, tool_specs=tool_specs)
    assert evidence["command_results"][0]["argv"] == [
        "python3", "-c", "print('ok')"]

    log = tmp_path / record["commands"][0]["stdout_path"]
    log.write_text("forged\n")
    with pytest.raises(ValueError, match="log hash mismatch"):
        validate_attestation(
            tmp_path, protocol, record,
            command_specs=command_specs, tool_specs=tool_specs)


def test_handwritten_sparse_record_is_not_an_attestation(tmp_path):
    record = {
        "verification_version": 2,
        "passed": True,
        "verified_commit": "a" * 40,
        "commands": ["make test"],
        "tool_versions": {"python": "fixture"},
        "artifact_sha256": {},
    }
    with pytest.raises(ValueError, match="attestation header"):
        validate_attestation(tmp_path, {"code_commit": "a" * 40}, record)
