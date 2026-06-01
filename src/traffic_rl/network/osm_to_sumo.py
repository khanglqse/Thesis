"""Convert raw OSM XML to a SUMO .net.xml using netconvert."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List


def build_netconvert_command(
    osm_file: str, output_file: str, tls_default_type: str = "actuated"
) -> List[str]:
    """Build the netconvert argv for a clean, signal-aware urban network."""
    return [
        "netconvert",
        "--osm-files", osm_file,
        "--output-file", output_file,
        "--keep-edges.by-vclass", "passenger",
        "--remove-edges.isolated", "true",
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        "--junctions.join", "true",
        "--tls.guess-signals", "true",
        "--tls.join", "true",
        "--tls.discard-simple", "true",
        "--tls.default-type", tls_default_type,
        "--no-turnarounds", "true",
    ]


def run_netconvert(osm_file: str, output_file: str, tls_default_type: str = "actuated") -> Path:
    """Run netconvert; return the output path. Raises on failure."""
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_netconvert_command(osm_file, output_file, tls_default_type)
    sumo_home = os.environ.get("SUMO_HOME", "/opt/homebrew/share/sumo")
    subprocess.run(cmd, check=True, env={**os.environ, "SUMO_HOME": sumo_home})
    if not out.exists():
        raise RuntimeError(f"netconvert did not produce {out}")
    return out
