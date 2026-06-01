"""Run CityFlow's SUMO->CityFlow converter inside the CityFlow Docker image."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List

CONVERTER = "/home/cityflow/tools/converter/converter.py"
# converter.py imports sympy + traci/sumolib, which are not in the image.
DEPS = "sympy traci sumolib"

# Patch applied to converter.py for compatibility with modern sumolib:
# Old sumolib stored _phases as list of (state_str, duration) tuples.
# New sumolib (>=1.6) stores Phase objects with .state and .duration attributes.
# Strategy: wrap _phases in a generator that normalises each element to a tuple.
_PHASE_OLD = "for phase,duration in tls_dict[nodeid]._programs['0']._phases:"
_PHASE_NEW = (
    "for phase,duration in "
    "[(p.state,p.duration) if hasattr(p,'state') else p "
    "for p in tls_dict[nodeid]._programs['0']._phases]:"
)


def build_converter_docker_command(
    sumo_net: str,
    cityflow_net: str,
    image: str = "cityflowproject/cityflow:latest",
    workdir: str = "/work",
    host_root: str | None = None,
) -> List[str]:
    """Build the `docker run` argv that converts a SUMO net to CityFlow roadnet."""
    host_root = host_root or os.getcwd()
    inner = (
        f"pip install {DEPS} >/dev/null 2>&1; "
        f"python3 {CONVERTER} --sumonet {sumo_net} --cityflownet {cityflow_net}"
    )
    return [
        "docker", "run", "--rm",
        "-v", f"{host_root}:{workdir}",
        "-w", workdir,
        image,
        "sh", "-lc", inner,
    ]


# Second patch: tls_dict is indexed by TLS ID, but node ID may differ (e.g. GS_ prefix).
# Re-index tls_dict so every node whose connections belong to a TLS is also reachable
# by node ID.
_TLS_DICT_OLD = (
    "    tls_dict = {}\n"
    "    for tls in net.getTrafficLights():\n"
    "        tls_dict[tls.getID()] = tls"
)
_TLS_DICT_NEW = (
    "    tls_dict = {}\n"
    "    for tls in net.getTrafficLights():\n"
    "        tls_dict[tls.getID()] = tls\n"
    "    # Also index by node ID for nets where TLS id != node id (GS_ prefix, clusters)\n"
    "    for tls in net.getTrafficLights():\n"
    "        for conn in tls._connections:\n"
    "            node_id = conn[0].getEdge().getToNode().getID()\n"
    "            if node_id not in tls_dict:\n"
    "                tls_dict[node_id] = tls"
)


def _write_patch_script(host_root: str) -> str:
    """Write a patch helper script inside the repo (which is already mounted).

    Returns the path relative to host_root (i.e. the in-container path under /work).
    """
    script_dir = Path(host_root) / "data" / ".converter_patch"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "patch_converter.py"
    script = (
        "import sys\n"
        f"src = open({repr(CONVERTER)}).read()\n"
        # patch 1: Phase object iteration
        f"old1 = {repr(_PHASE_OLD)}\n"
        f"new1 = {repr(_PHASE_NEW)}\n"
        "patched = src.replace(old1, new1)\n"
        "assert patched != src, 'patch1 did not apply: Phase pattern not found'\n"
        # patch 2: tls_dict node-ID re-indexing
        f"old2 = {repr(_TLS_DICT_OLD)}\n"
        f"new2 = {repr(_TLS_DICT_NEW)}\n"
        "patched2 = patched.replace(old2, new2)\n"
        "assert patched2 != patched, 'patch2 did not apply: tls_dict pattern not found'\n"
        "open(sys.argv[1], 'w').write(patched2)\n"
    )
    script_path.write_text(script)
    # Return container-side path (repo is mounted at /work)
    return "data/.converter_patch/patch_converter.py"


def run_converter(sumo_net: str, cityflow_net: str, image: str = "cityflowproject/cityflow:latest") -> Path:
    """Run the converter in Docker; return the roadnet path. Raises on failure."""
    out = Path(cityflow_net)
    out.parent.mkdir(parents=True, exist_ok=True)
    host_root = os.getcwd()

    patch_script_container = _write_patch_script(host_root)
    inner = (
        f"pip install {DEPS} >/dev/null 2>&1; "
        f"python3 {patch_script_container} /tmp/converter_patched.py; "
        f"python3 /tmp/converter_patched.py "
        f"--sumonet {sumo_net} --cityflownet {cityflow_net}"
    )
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{host_root}:/work",
        "-w", "/work",
        image,
        "sh", "-lc", inner,
    ]
    subprocess.run(cmd, check=True)

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"converter did not produce non-empty {out}")
    return out
