import hashlib
import json


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
