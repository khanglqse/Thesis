"""Generate and validate the clean-checkout release attestation."""

import datetime
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path

from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime


RELEASE_ARTIFACTS = (
    "results/haichau_network_v2/final/frozen-protocol.json",
    "results/haichau_network_v2/final/campaign-manifest.json",
    "results/haichau_network_v2/final/summary.json",
    "paper/generated/haichau_network/artifact-manifest.json",
    "paper/generated/haichau_network/thesis-release.json",
    "paper/thesis_danang.pdf",
    "results/haichau_network_v2/demo/manifest.json",
)

REQUIRED_COMMANDS = (
    ("host_tests", ("make", "test"), {}),
    ("cityflow_tests", ("make", "cf-test"), {}),
    ("replay_tests", ("npm", "run", "test:replay"), {}),
    ("paper_build", ("tectonic", "paper/thesis_danang.tex"), {}),
    ("release_audit", (
        "python3", "scripts/verify_haichau_thesis.py",
        "--skip-clean-checkout", "--no-write",
    ), {"PYTHONPATH": "src"}),
)

TOOL_VERSION_COMMANDS = (
    ("git", ("git", "--version")),
    ("python", ("python3", "--version")),
    ("docker", ("docker", "--version")),
    ("make", ("make", "--version")),
    ("node", ("node", "--version")),
    ("npm", ("npm", "--version")),
    ("tectonic", ("tectonic", "--version")),
    ("ffmpeg", ("ffmpeg", "-version")),
    ("ffprobe", ("ffprobe", "-version")),
    ("pdfinfo", ("pdfinfo", "-v")),
    ("pdftoppm", ("pdftoppm", "-v")),
)


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _campaign_run_hashes(root):
    run_root = root / "results/haichau_network_v2/final/runs"
    if not run_root.is_dir():
        return {}
    return dict(
        (str(path.relative_to(root)), _sha256(path))
        for path in sorted(run_root.rglob("*")) if path.is_file())


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _run_capture(root, argv, environment, runner):
    merged = os.environ.copy()
    merged.update(environment)
    started = time.monotonic()
    try:
        completed = runner(
            list(argv), cwd=str(root), env=merged, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        returncode = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except OSError as exc:
        returncode = 127
        stdout = ""
        stderr = str(exc)
    return returncode, stdout, stderr, max(0.0, time.monotonic() - started)


def _record_capture(root, log_dir, prefix, identifier, argv, environment, runner):
    code, stdout, stderr, elapsed = _run_capture(root, argv, environment, runner)
    stdout_relative = str(log_dir / (prefix + "-" + identifier + ".stdout.log"))
    stderr_relative = str(log_dir / (prefix + "-" + identifier + ".stderr.log"))
    return {
        "id": identifier,
        "argv": list(argv),
        "environment": dict(environment),
        "exit_code": code,
        "wall_time_seconds": elapsed,
        "stdout_path": stdout_relative,
        "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
        "stderr_path": stderr_relative,
        "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        "_stdout": stdout,
        "_stderr": stderr,
    }


def create_attestation(root, protocol, record_path=None, runner=subprocess.run,
                       command_specs=REQUIRED_COMMANDS,
                       tool_specs=TOOL_VERSION_COMMANDS):
    """Execute the canonical release checks and write their complete evidence."""
    root = Path(root).resolve()
    record_path = Path(record_path or (
        root / "results/haichau_network_v2/verification/clean-checkout.json"))
    if record_path.exists():
        raise ValueError("refusing to overwrite an existing clean-checkout attestation")
    source = verify_git_checkout(root, protocol.get("code_commit"), runner=runner)
    runtime = verify_runtime(root, protocol)
    started_at = _utc_now()
    started = time.monotonic()
    log_dir = Path("results/haichau_network_v2/verification/attestation-logs")
    tools = [
        _record_capture(root, log_dir, "tool", identifier, argv, {}, runner)
        for identifier, argv in tool_specs
    ]
    commands = [
        _record_capture(root, log_dir, "command", identifier, argv, environment, runner)
        for identifier, argv, environment in command_specs
    ]
    artifacts = {}
    for relative in RELEASE_ARTIFACTS:
        path = root / relative
        if path.is_file():
            artifacts[relative] = _sha256(path)
    generator = root / "scripts/attest_haichau_release.py"
    record = {
        "verification_version": 3,
        "attestation_type": "traffic_rl.clean_checkout.v1",
        "generator_path": "scripts/attest_haichau_release.py",
        "generator_sha256": _sha256(generator) if generator.is_file() else None,
        "verified_commit": source["head_commit"],
        "source_identity": source,
        "runtime_identity": runtime,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "wall_time_seconds": max(0.0, time.monotonic() - started),
        "command_contract_sha256": _canonical_hash([
            [identifier, list(argv), environment]
            for identifier, argv, environment in command_specs
        ]),
        "commands": commands,
        "tool_versions": tools,
        "artifact_sha256": artifacts,
        "campaign_run_artifact_sha256": _campaign_run_hashes(root),
    }
    record["passed"] = bool(
        set(artifacts) == set(RELEASE_ARTIFACTS)
        and record["campaign_run_artifact_sha256"]
        and all(item["exit_code"] == 0 for item in commands)
        and all(item["exit_code"] == 0 and (
            item["_stdout"].strip() or item["_stderr"].strip()) for item in tools))
    for item in tools + commands:
        stdout = item.pop("_stdout")
        stderr = item.pop("_stderr")
        stdout_path = root / item["stdout_path"]
        stderr_path = root / item["stderr_path"]
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(stdout)
        stderr_path.write_text(stderr)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def _validate_capture(root, actual, identifier, argv, environment):
    if actual.get("id") != identifier or actual.get("argv") != list(argv) \
            or actual.get("environment") != dict(environment):
        raise ValueError("attestation command contract differs for %s" % identifier)
    if actual.get("exit_code") != 0:
        raise ValueError("attestation command failed: %s" % identifier)
    elapsed = actual.get("wall_time_seconds")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("attestation command duration is invalid: %s" % identifier)
    for stream in ("stdout", "stderr"):
        relative = actual.get(stream + "_path")
        expected_prefix = "results/haichau_network_v2/verification/attestation-logs/"
        if not isinstance(relative, str) or not relative.startswith(expected_prefix):
            raise ValueError("attestation %s log path is invalid" % identifier)
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise ValueError("attestation log leaves the checkout")
        if not path.is_file() or _sha256(path) != actual.get(stream + "_sha256"):
            raise ValueError("attestation %s log hash mismatch" % identifier)


def validate_attestation(root, protocol, record,
                         command_specs=REQUIRED_COMMANDS,
                         tool_specs=TOOL_VERSION_COMMANDS):
    """Validate command logs and bind the attestation to current Git/runtime state."""
    root = Path(root).resolve()
    if record.get("verification_version") != 3 \
            or record.get("attestation_type") != "traffic_rl.clean_checkout.v1" \
            or record.get("passed") is not True:
        raise ValueError("clean-checkout attestation header is invalid")
    generator = root / str(record.get("generator_path", ""))
    if generator != root / "scripts/attest_haichau_release.py" \
            or not generator.is_file() \
            or record.get("generator_sha256") != _sha256(generator):
        raise ValueError("clean-checkout attestation generator is not verified")
    expected_contract = _canonical_hash([
        [identifier, list(argv), environment]
        for identifier, argv, environment in command_specs
    ])
    if record.get("command_contract_sha256") != expected_contract:
        raise ValueError("clean-checkout attestation command contract is invalid")
    commands = record.get("commands")
    versions = record.get("tool_versions")
    if not isinstance(commands, list) or len(commands) != len(command_specs):
        raise ValueError("clean-checkout attestation requires exact commands")
    if not isinstance(versions, list) or len(versions) != len(tool_specs):
        raise ValueError("clean-checkout attestation requires tool versions")
    for actual, expected in zip(commands, command_specs):
        _validate_capture(root, actual, expected[0], expected[1], expected[2])
    for actual, expected in zip(versions, tool_specs):
        _validate_capture(root, actual, expected[0], expected[1], {})
        stdout = (root / actual["stdout_path"]).read_text().strip()
        stderr = (root / actual["stderr_path"]).read_text().strip()
        if not stdout and not stderr:
            raise ValueError("attestation tool version output is empty: %s" % expected[0])
        code, current_stdout, current_stderr, _ = _run_capture(
            root, expected[1], {}, subprocess.run)
        if code != 0 \
                or _sha256_bytes(current_stdout.encode("utf-8")) \
                != actual["stdout_sha256"] \
                or _sha256_bytes(current_stderr.encode("utf-8")) \
                != actual["stderr_sha256"]:
            raise ValueError("current tool version differs from attestation: %s" % expected[0])
    if record.get("source_identity", {}).get("head_commit") != record.get("verified_commit"):
        raise ValueError("attestation source identity differs from verified commit")
    identity = verify_git_checkout(root, protocol.get("code_commit"))
    runtime = verify_runtime(root, protocol)
    if record.get("runtime_identity") != runtime:
        raise ValueError("attestation runtime identity differs from actual Docker image")
    verified_commit = str(record.get("verified_commit", ""))
    for argv in (
            ("git", "cat-file", "-e", verified_commit + "^{commit}"),
            ("git", "merge-base", "--is-ancestor", verified_commit,
             identity["head_commit"])):
        completed = subprocess.run(
            list(argv), cwd=str(root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        if completed.returncode:
            raise ValueError("attestation commit is not an ancestor of current HEAD")
    changed = subprocess.check_output([
        "git", "-C", str(root), "diff", "--name-only",
        verified_commit, identity["head_commit"], "--",
    ], universal_newlines=True).splitlines()
    allowed_prefix = "results/haichau_network_v2/verification/"
    if any(not name.startswith(allowed_prefix) for name in changed):
        raise ValueError("files outside attestation evidence changed after verification")
    hashes = record.get("artifact_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(RELEASE_ARTIFACTS):
        raise ValueError("clean-checkout attestation artifact hash set is incomplete")
    for relative in RELEASE_ARTIFACTS:
        path = root / relative
        if not path.is_file() or _sha256(path) != hashes[relative]:
            raise ValueError("clean-checkout artifact hash mismatch: %s" % relative)
    run_hashes = record.get("campaign_run_artifact_sha256")
    actual_run_hashes = _campaign_run_hashes(root)
    if not isinstance(run_hashes, dict) or not run_hashes \
            or run_hashes != actual_run_hashes:
        raise ValueError("clean-checkout campaign run evidence hash set differs")
    wall = record.get("wall_time_seconds")
    if not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall <= 0:
        raise ValueError("clean-checkout attestation wall time is invalid")
    return {
        "verified_commit": verified_commit,
        "actual_head_commit": identity["head_commit"],
        "runtime_image_id": runtime["runtime_image_id"],
        "generator_sha256": record["generator_sha256"],
        "command_contract_sha256": record["command_contract_sha256"],
        "command_results": commands,
        "tool_version_results": versions,
        "artifact_sha256": hashes,
        "campaign_run_artifact_count": len(run_hashes),
    }
