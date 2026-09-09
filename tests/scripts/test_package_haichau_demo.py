import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("script", (
    "package_haichau_demo.py", "serve_haichau_demo.py",
))
def test_direct_cli_help_bootstraps_the_repository_root(script):
    completed = subprocess.run(
        ["sh", "-c", "PYTHONPATH=src python3 scripts/%s --help" % script],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout


def test_server_script_bootstrap_allows_canonical_verifier_import(tmp_path):
    script = PROJECT_ROOT / "scripts/serve_haichau_demo.py"
    source = PROJECT_ROOT / "src"
    code = """
import pathlib
import runpy
import tempfile

module = runpy.run_path(%r)
root = pathlib.Path(tempfile.mkdtemp())
(root / 'results/haichau_network_v2/demo').mkdir(parents=True)
try:
    module['validate_demo_bundle'](root)
except ValueError as exc:
    assert 'complete project verification' in str(exc), exc
else:
    raise AssertionError('fixture must not pass final verification')
""" % str(script)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source)

    completed = subprocess.run(
        ["python3", "-c", code], cwd=str(tmp_path), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    assert completed.returncode == 0, completed.stderr


def _write_bundle(path):
    path.mkdir(parents=True)
    index = path / "index.html"
    index.write_text("<!doctype html><title>offline</title>")
    manifest = {
        "bundle_version": 2,
        "controlled_signals": 53,
        "files": {
            "index.html": hashlib.sha256(index.read_bytes()).hexdigest(),
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest))


def test_package_copies_only_the_verified_canonical_bundle_and_launcher(
        tmp_path, monkeypatch):
    from scripts import package_haichau_demo
    from scripts import haichau_demo_launcher

    source = tmp_path / "results/haichau_network_v2/demo"
    _write_bundle(source)
    monkeypatch.setattr(package_haichau_demo, "validate_demo_bundle",
                        lambda root: {"complete": True})

    result = package_haichau_demo.package_demo(tmp_path, tmp_path / "portable")

    assert result["bundle"] == "portable"
    assert (tmp_path / "portable/index.html").read_text() == (
        "<!doctype html><title>offline</title>")
    assert (tmp_path / "portable/launch_demo.py").is_file()
    assert (tmp_path / "portable/launch_demo.command").is_file()
    assert haichau_demo_launcher.validate_bundle(tmp_path / "portable") == {
        "bundle_version": 2,
        "controlled_signals": 53,
        "files": {
            "index.html": hashlib.sha256(
                b"<!doctype html><title>offline</title>").hexdigest(),
        },
    }


def test_portable_launcher_rejects_changed_launcher_or_extra_payload(
        tmp_path, monkeypatch):
    from scripts import package_haichau_demo
    from scripts import haichau_demo_launcher

    source = tmp_path / "results/haichau_network_v2/demo"
    _write_bundle(source)
    monkeypatch.setattr(package_haichau_demo, "validate_demo_bundle",
                        lambda root: {"complete": True})
    portable = tmp_path / "portable"
    package_haichau_demo.package_demo(tmp_path, portable)

    launcher = portable / "launch_demo.py"
    launcher.write_text(launcher.read_text() + "\n# modified\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        haichau_demo_launcher.validate_bundle(portable)

    package_haichau_demo.package_demo(tmp_path, tmp_path / "portable-extra")
    (tmp_path / "portable-extra/unlisted.txt").write_text("surprise")
    with pytest.raises(ValueError, match="file set"):
        haichau_demo_launcher.validate_bundle(tmp_path / "portable-extra")


def test_portable_launcher_rejects_every_symlink(tmp_path, monkeypatch):
    from scripts import package_haichau_demo
    from scripts import haichau_demo_launcher

    source = tmp_path / "results/haichau_network_v2/demo"
    _write_bundle(source)
    monkeypatch.setattr(package_haichau_demo, "validate_demo_bundle",
                        lambda root: {"complete": True})
    portable = tmp_path / "portable"
    package_haichau_demo.package_demo(tmp_path, portable)
    os.symlink("index.html", portable / "linked-index.html")

    with pytest.raises(ValueError, match="symlink"):
        haichau_demo_launcher.validate_bundle(portable)


def test_packager_rejects_an_output_below_canonical_source(tmp_path, monkeypatch):
    from scripts import package_haichau_demo

    source = tmp_path / "results/haichau_network_v2/demo"
    _write_bundle(source)
    monkeypatch.setattr(package_haichau_demo, "validate_demo_bundle",
                        lambda root: {"complete": True})

    with pytest.raises(ValueError, match="inside the canonical demo"):
        package_haichau_demo.package_demo(tmp_path, source / "portable")


def test_portable_launcher_falls_back_to_next_loopback_port(tmp_path, monkeypatch):
    from scripts import haichau_demo_launcher

    bundle = tmp_path / "portable"
    _write_bundle(bundle)
    bound = []

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            if address[1] == 8080:
                raise OSError("occupied")
            bound.append(address)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(haichau_demo_launcher, "ReusableServer", FakeServer)

    assert haichau_demo_launcher.main([
        "--bundle", str(bundle), "--port", "8080",
        "--port-fallback-count", "2", "--no-browser",
    ]) == 0
    assert bound == [("127.0.0.1", 8081)]
