#!/usr/bin/env python3
"""Download raw OSM XML for a Da Nang bbox using SUMO's osmGet.py.

netconvert needs raw .osm XML (osmnx graphml is only for inspection).
Usage: python3 scripts/download_osm.py [subarea|full]
"""
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUMO_HOME = os.environ.get("SUMO_HOME", "/opt/homebrew/share/sumo")

# OSM direct export API — used as fallback when Overpass is unavailable.
OSM_EXPORT_URL = "https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}"


def _download_via_osm_export(w, s, e, n, out_path: Path) -> None:
    url = OSM_EXPORT_URL.format(w=w, s=s, e=e, n=n)
    print(f"Falling back to OSM export API: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "traffic-rl/thesis osmGet-fallback"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        out_path.write_bytes(resp.read())


def main() -> int:
    area = sys.argv[1] if len(sys.argv) > 1 else "subarea"
    cfg = yaml.safe_load((ROOT / "configs" / "network.yaml").read_text())
    w, s, e, n = cfg["bbox"][area]

    out_dir = ROOT / "data" / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"danang_{area}"

    osm_get = Path(SUMO_HOME) / "tools" / "osmGet.py"
    cmd = [
        sys.executable, str(osm_get),
        "--bbox", f"{w},{s},{e},{n}",
        "--output-dir", str(out_dir),
        "--prefix", prefix,
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, env={**os.environ, "SUMO_HOME": SUMO_HOME})

    produced = out_dir / f"{prefix}_bbox.osm.xml"
    if result.returncode != 0 or not produced.exists():
        print("osmGet.py unavailable (Overpass API blocked); using OSM export API fallback.")
        _download_via_osm_export(w, s, e, n, produced)

    if not produced.exists():
        print(f"ERROR: expected {produced} not found", file=sys.stderr)
        return 1
    print(f"Saved: {produced} ({produced.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
