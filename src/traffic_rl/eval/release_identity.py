"""Verify release source and CityFlow runtime identities against local state."""

import hashlib
import json
import re
import subprocess
from pathlib import Path


_CODE_PATHS = (
    "src", "scripts", "frontend", "docker", "Makefile", "pyproject.toml",
)


def _run(argv, cwd=None, runner=subprocess.run):
    completed = runner(
        list(argv), cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if completed.returncode:
        raise ValueError("command failed (%s): %s" % (
            " ".join(argv), completed.stderr.strip()))
    return completed.stdout.strip()


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dirty_path(line):
    value = line[3:] if len(line) > 3 else ""
    if " -> " in value:
        value = value.rsplit(" -> ", 1)[-1]
    return value.strip('"')


def verify_git_checkout(root, code_commit, runner=subprocess.run,
                        allowed_dirty_prefixes=()):
    """Require a clean checkout descended from unchanged frozen code paths."""
    root = Path(root).resolve()
    expected = str(code_commit or "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("frozen code_commit must be a full 40-character Git commit")
    head = _run(("git", "rev-parse", "HEAD"), cwd=root, runner=runner)
    _run(("git", "cat-file", "-e", expected + "^{commit}"),
         cwd=root, runner=runner)
    _run(("git", "merge-base", "--is-ancestor", expected, head),
         cwd=root, runner=runner)
    dirty = _run(
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=root, runner=runner)
    dirty_paths = [_dirty_path(line) for line in dirty.splitlines() if line]
    allowed = tuple(str(Path(value)).rstrip("/") for value in allowed_dirty_prefixes)
    unexpected = [path for path in dirty_paths if not any(
        path == prefix or path.startswith(prefix + "/") for prefix in allowed)]
    if unexpected:
        raise ValueError("release checkout is dirty: %s" % unexpected[0])
    command = ("git", "diff", "--quiet", expected, head, "--") + _CODE_PATHS
    completed = runner(
        list(command), cwd=str(root), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, universal_newlines=True)
    if completed.returncode == 1:
        raise ValueError("release code paths changed after frozen code_commit")
    if completed.returncode:
        raise ValueError("unable to compare frozen code paths: %s" %
                         completed.stderr.strip())
    return {
        "code_commit": expected,
        "head_commit": head,
        "dirty": bool(dirty_paths),
        "allowed_dirty_paths": dirty_paths,
    }


def inspect_runtime_image(image, runner=subprocess.run):
    """Inspect a locally available immutable Docker image reference."""
    image = str(image or "")
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("runtime_image must be an immutable repo@sha256 reference")
    output = _run(("docker", "image", "inspect", image), runner=runner)
    try:
        records = json.loads(output)
        record = records[0]
        image_id = record["Id"]
        repo_digests = record["RepoDigests"]
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("Docker image inspection returned invalid metadata")
    if image not in repo_digests:
        raise ValueError("runtime_image is absent from inspected Docker RepoDigests")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(image_id)):
        raise ValueError("inspected Docker image ID is invalid")
    return {
        "runtime_image": image,
        "runtime_image_id": image_id,
        "repo_digests": sorted(repo_digests),
    }


def verify_runtime(root, protocol, inspector=None):
    """Bind the frozen digest to an actual Docker image and tracked Dockerfile."""
    root = Path(root).resolve()
    inspector = inspector or inspect_runtime_image
    digest = str((protocol or {}).get("runtime_digest", ""))
    image = str((protocol or {}).get("runtime_image", ""))
    expected_image_id = str((protocol or {}).get("runtime_image_id", ""))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("runtime_digest must be a full sha256 digest")
    if image.rsplit("@", 1)[-1] != digest:
        raise ValueError("runtime_image does not contain runtime_digest")
    inspected = inspector(image)
    if inspected.get("runtime_image") != image \
            or inspected.get("runtime_image_id") != expected_image_id:
        raise ValueError("actual Docker image identity differs from frozen protocol")
    dockerfile_value = (protocol or {}).get("runtime_dockerfile_path")
    dockerfile = (root / str(dockerfile_value or "")).resolve()
    try:
        dockerfile.relative_to(root)
    except ValueError:
        raise ValueError("runtime Dockerfile must remain inside the project")
    expected_hash = (protocol or {}).get("runtime_dockerfile_sha256")
    if not dockerfile.is_file() or _sha256(dockerfile) != expected_hash:
        raise ValueError("runtime Dockerfile hash differs from frozen protocol")
    from_lines = [line.strip() for line in dockerfile.read_text().splitlines()
                  if line.strip().upper().startswith("FROM ")]
    if not from_lines or from_lines[0].split()[1] != image:
        raise ValueError("runtime Dockerfile FROM does not use frozen runtime_image")
    result = dict(inspected)
    result.update({
        "runtime_digest": digest,
        "runtime_dockerfile_path": str(dockerfile.relative_to(root)),
        "runtime_dockerfile_sha256": expected_hash,
    })
    return result
