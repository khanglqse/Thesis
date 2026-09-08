import pytest


def test_server_requires_a_complete_project_verification(tmp_path, monkeypatch):
    from scripts import serve_haichau_demo
    from scripts import verify_haichau_thesis

    (tmp_path / "results/haichau_network_v2/demo").mkdir(parents=True)
    monkeypatch.setattr(verify_haichau_thesis, "audit_demo", lambda root: {
        "passed": True, "detail": "demo only"})
    monkeypatch.setattr(verify_haichau_thesis, "verify_project", lambda root: {
        "complete": False, "failed_gates": ["fresh_matched_runs"]})

    with pytest.raises(ValueError, match="complete project verification"):
        serve_haichau_demo.validate_demo_bundle(tmp_path)


def test_server_binds_loopback_only(monkeypatch):
    from scripts import serve_haichau_demo

    bound = {}

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            bound["address"] = address

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(serve_haichau_demo, "validate_demo_bundle", lambda root: {})
    monkeypatch.setattr(serve_haichau_demo.socketserver, "TCPServer", FakeServer)

    assert serve_haichau_demo.main(["--port", "8765", "--no-browser"]) == 0
    assert bound["address"] == ("127.0.0.1", 8765)
