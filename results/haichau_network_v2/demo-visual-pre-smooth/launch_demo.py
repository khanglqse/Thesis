#!/usr/bin/env python3
"""Serve a copied Hai Chau demo bundle using only Python's standard library."""

import argparse
import functools
import hashlib
import http.server
import json
import socketserver
import webbrowser
from pathlib import Path


PORTABLE_MANIFEST = "portable-manifest.json"


class ReusableServer(socketserver.TCPServer):
    allow_reuse_address = True


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(directory, relative):
    candidate = (directory / relative).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        raise ValueError("bundle manifest references a path outside the bundle")
    return candidate


def _regular_files(bundle):
    files = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError("portable demo must not contain symlinks: %s" %
                             path.relative_to(bundle))
        if path.is_file():
            files.add(str(path.relative_to(bundle)))
    return files


def _validate_payload(bundle, manifest):
    files = manifest.get("files")
    if not isinstance(files, dict) or "index.html" not in files:
        raise ValueError("portable demo manifest does not authenticate index.html")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("portable demo manifest has invalid file evidence")
        asset = _inside(bundle, relative)
        if not asset.is_file() or _sha256(asset) != expected:
            raise ValueError("portable demo asset hash mismatch: %s" % relative)
    return files


def validate_bundle(bundle_dir):
    """Reject a copied bundle whose manifest cannot authenticate its assets."""
    bundle = Path(bundle_dir).resolve()
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("portable demo manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("bundle_version") != 2 or manifest.get("controlled_signals") != 53:
        raise ValueError("portable demo is not the 53-signal v2 bundle")
    files = _validate_payload(bundle, manifest)
    actual = _regular_files(bundle)
    portable_path = bundle / PORTABLE_MANIFEST
    if not portable_path.is_file():
        expected = set(files) | {"manifest.json"}
        if actual != expected:
            raise ValueError("portable demo file set differs from its manifest")
        return manifest
    portable = json.loads(portable_path.read_text())
    if (portable.get("portable_bundle_version") != 1
            or portable.get("canonical_manifest_sha256") != _sha256(manifest_path)
            or not isinstance(portable.get("files"), dict)):
        raise ValueError("portable demo manifest is invalid")
    expected = set(portable["files"]) | {PORTABLE_MANIFEST}
    if actual != expected:
        raise ValueError("portable demo file set differs from its manifest")
    for relative, expected_hash in portable["files"].items():
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError("portable demo manifest has invalid file evidence")
        asset = _inside(bundle, relative)
        if not asset.is_file() or _sha256(asset) != expected_hash:
            raise ValueError("portable demo asset hash mismatch: %s" % relative)
    return manifest


def bind_with_fallback(handler, first_port, fallback_count):
    """Bind only loopback, moving to the next port when a presenter has one in use."""
    for port in range(first_port, first_port + fallback_count + 1):
        try:
            return ReusableServer(("127.0.0.1", port), handler), port
        except OSError:
            continue
    raise OSError("no free loopback port in %d..%d" % (
        first_port, first_port + fallback_count))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--port-fallback-count", type=int, default=10)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be in 1..65535")
    if args.port_fallback_count < 0 or args.port + args.port_fallback_count > 65535:
        raise ValueError("port fallback range must remain in 1..65535")
    bundle = Path(args.bundle).resolve()
    validate_bundle(bundle)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(bundle))
    server, port = bind_with_fallback(handler, args.port, args.port_fallback_count)
    with server:
        url = "http://127.0.0.1:%d/index.html" % port
        print("Verified portable Hai Chau demo: %s" % url)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
