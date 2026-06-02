"""Convert raw OSM XML to a SUMO .net.xml using netconvert."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List


def build_netconvert_command(
    osm_file: str, output_file: str, tls_default_type: str = "actuated",
    drop_road_types: List[str] = None,
) -> List[str]:
    """Build the netconvert argv for a clean, signal-aware urban network.

    drop_road_types: OSM edge types to remove (e.g. ["highway.residential"]). Used
    to scope the network to its arterial grid so demand is forced through the
    signal-controlled intersections — see docs/network_demand_analysis.md. When
    set, only the largest connected component is kept so the grid stays routable.
    """
    cmd = [
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
    if drop_road_types:
        cmd += ["--remove-edges.by-type", ",".join(drop_road_types),
                "--keep-edges.components", "1"]
    return cmd


def run_netconvert(osm_file: str, output_file: str, tls_default_type: str = "actuated",
                   drop_road_types: List[str] = None) -> Path:
    """Run netconvert; return the output path. Raises on failure."""
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_netconvert_command(osm_file, output_file, tls_default_type, drop_road_types)
    sumo_home = os.environ.get("SUMO_HOME", "/opt/homebrew/share/sumo")
    subprocess.run(cmd, check=True, env={**os.environ, "SUMO_HOME": sumo_home})
    if not out.exists():
        raise RuntimeError(f"netconvert did not produce {out}")
    return out
