#!/usr/bin/env python3
"""Copy the verified canonical Hai Chau demo into a portable offline folder."""

import argparse
import json
import shutil
from pathlib import Path

from scripts.haichau_demo_launcher import PORTABLE_MANIFEST, _sha256, validate_bundle
from scripts.serve_haichau_demo import DEMO_RELATIVE, ROOT, validate_demo_bundle


def package_demo(project_root, output_dir):
    root = Path(project_root).resolve()
    source = (root / DEMO_RELATIVE).resolve()
    target = Path(output_dir).resolve()
    if target == source:
        raise ValueError("portable output must differ from the canonical demo directory")
    try:
        target.relative_to(source)
    except ValueError:
        pass
    else:
        raise ValueError("portable output must not be inside the canonical demo directory")
    if target.exists():
        raise ValueError("refusing to overwrite an existing portable demo directory")
    validate_demo_bundle(root)
    validate_bundle(source)
    shutil.copytree(source, target)
    launcher = Path(__file__).resolve().parent / "haichau_demo_launcher.py"
    shutil.copyfile(launcher, target / "launch_demo.py")
    command = target / "launch_demo.command"
    command.write_text(
        "#!/bin/sh\ncd \"$(dirname \"$0\")\"\nexec python3 launch_demo.py \"$@\"\n")
    command.chmod(0o755)
    files = {
        str(path.relative_to(target)): _sha256(path)
        for path in target.rglob("*") if path.is_file()
    }
    (target / PORTABLE_MANIFEST).write_text(json.dumps({
        "portable_bundle_version": 1,
        "canonical_manifest_sha256": _sha256(target / "manifest.json"),
        "files": files,
    }, indent=2, sort_keys=True) + "\n")
    try:
        relative = str(target.relative_to(root))
    except ValueError:
        relative = str(target)
    return {"bundle": relative, "launcher": "launch_demo.command"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/haichau_network_v2/demo-portable")
    args = parser.parse_args(argv)
    print(json.dumps(package_demo(ROOT, ROOT / args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
