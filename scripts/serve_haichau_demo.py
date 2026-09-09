#!/usr/bin/env python3
"""Validate and serve the final, offline Hai Chau v2 defense bundle."""

import argparse
import functools
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEMO_RELATIVE = Path("results/haichau_network_v2/demo")


def validate_demo_bundle(project_root, bundle_dir=None):
    """Only allow the canonical v2 bundle after the release audit accepts it."""
    root = Path(project_root).resolve()
    expected = (root / DEMO_RELATIVE).resolve()
    bundle = Path(bundle_dir).resolve() if bundle_dir else expected
    if bundle != expected:
        raise ValueError("demo bundle must be results/haichau_network_v2/demo")
    if not bundle.is_dir():
        raise ValueError("final Hai Chau v2 demo bundle is missing")
    from scripts.verify_haichau_thesis import verify_project
    report = verify_project(root)
    if not report.get("complete"):
        raise ValueError(
            "refusing to serve without complete project verification: %s" %
            ", ".join(report.get("failed_gates", ())))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--port-fallback-count", type=int, default=10)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        raise ValueError("port must be in 1..65535")
    if (args.port_fallback_count < 0
            or args.port + args.port_fallback_count > 65535):
        raise ValueError("port fallback range must remain in 1..65535")
    validate_demo_bundle(ROOT)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT / DEMO_RELATIVE))

    class ReusableServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = None
    port = None
    for candidate in range(args.port, args.port + args.port_fallback_count + 1):
        try:
            server = ReusableServer(("127.0.0.1", candidate), handler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise OSError("no free loopback port in %d..%d" % (
            args.port, args.port + args.port_fallback_count))
    with server:
        url = "http://127.0.0.1:%d/index.html" % port
        print("Verified Hai Chau v2 demo: %s" % url)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
