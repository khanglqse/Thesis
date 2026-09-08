#!/usr/bin/env python3
"""Validate and serve the final, offline Hai Chau v2 defense bundle."""

import argparse
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
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
    from scripts.verify_haichau_thesis import audit_demo
    report = audit_demo(root)
    if not report.get("passed"):
        raise ValueError("refusing to serve unverified final demo bundle: %s" %
                         report.get("detail", "unknown verification failure"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        raise ValueError("port must be in 1..65535")
    validate_demo_bundle(ROOT)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT / DEMO_RELATIVE))

    class ReusableServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableServer(("", args.port), handler) as server:
        url = "http://localhost:%d/index.html" % args.port
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
