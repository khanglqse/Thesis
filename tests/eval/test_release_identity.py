import hashlib
import subprocess

import pytest

from traffic_rl.eval.release_identity import (
    inspect_runtime_image,
    verify_git_checkout,
    verify_runtime,
)


DIGEST = "sha256:" + "b" * 64
IMAGE = "cityflowproject/cityflow@" + DIGEST


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args),
        universal_newlines=True).strip()


def _repo(root):
    subprocess.check_call(["git", "init", "-q", str(root)])
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    path = root / "src/code.py"
    path.parent.mkdir(parents=True)
    path.write_text("VALUE = 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "code")
    return _git(root, "rev-parse", "HEAD")


def test_git_identity_requires_clean_tree_and_unchanged_code_since_frozen_commit(tmp_path):
    frozen = _repo(tmp_path)
    assert verify_git_checkout(tmp_path, frozen)["head_commit"] == frozen

    (tmp_path / "untracked.txt").write_text("dirty")
    with pytest.raises(ValueError, match="dirty"):
        verify_git_checkout(tmp_path, frozen)
    (tmp_path / "untracked.txt").unlink()

    (tmp_path / "src/code.py").write_text("VALUE = 2\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "changed code")
    with pytest.raises(ValueError, match="code paths changed"):
        verify_git_checkout(tmp_path, frozen)


def test_campaign_resume_may_only_leave_its_own_output_dirty(tmp_path):
    frozen = _repo(tmp_path)
    status = tmp_path / "results/haichau_network_v2/final/runs/r1/status.json"
    status.parent.mkdir(parents=True)
    status.write_text("{}")

    identity = verify_git_checkout(
        tmp_path, frozen,
        allowed_dirty_prefixes=("results/haichau_network_v2/final",))

    assert identity["dirty"] is True
    assert identity["allowed_dirty_paths"] == [
        "results/haichau_network_v2/final/runs/r1/status.json"]
    (tmp_path / "outside.txt").write_text("dirty")
    with pytest.raises(ValueError, match="outside.txt"):
        verify_git_checkout(
            tmp_path, frozen,
            allowed_dirty_prefixes=("results/haichau_network_v2/final",))


def test_runtime_verification_hashes_dockerfile_and_inspects_image(tmp_path):
    dockerfile = tmp_path / "docker/runtime.Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text("FROM %s\n" % IMAGE)
    protocol = {
        "runtime_digest": DIGEST,
        "runtime_image": IMAGE,
        "runtime_image_id": DIGEST,
        "runtime_dockerfile_path": "docker/runtime.Dockerfile",
        "runtime_dockerfile_sha256": hashlib.sha256(
            dockerfile.read_bytes()).hexdigest(),
    }

    result = verify_runtime(
        tmp_path, protocol,
        inspector=lambda image: {
            "runtime_image": image, "runtime_image_id": DIGEST,
            "repo_digests": [IMAGE],
        })

    assert result["runtime_image_id"] == DIGEST
    dockerfile.write_text("FROM python:latest\n")
    with pytest.raises(ValueError, match="Dockerfile hash"):
        verify_runtime(tmp_path, protocol, inspector=lambda image: result)


def test_image_inspection_rejects_self_declared_digest_not_present_in_docker():
    class Completed(object):
        returncode = 0
        stdout = '[{"Id":"%s","RepoDigests":["other/image@%s"]}]' % (DIGEST, DIGEST)
        stderr = ""

    with pytest.raises(ValueError, match="RepoDigests"):
        inspect_runtime_image(IMAGE, runner=lambda *args, **kwargs: Completed())
