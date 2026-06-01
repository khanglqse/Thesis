#!/usr/bin/env python3
"""Build the full-central-Da-Nang CityFlow roadnet from a Geofabrik PBF.

Overpass is blocked from this machine and the OSM export API caps at ~50k nodes,
so we download the Vietnam extract once and clip the Da Nang bbox locally with
osmium-tool (`brew install osmium-tool`).

Run locally (needs SUMO netconvert + osmium on PATH; the converter step uses Docker):
  python3 scripts/build_full_network.py
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

from traffic_rl.network.osm_to_sumo import run_netconvert
from traffic_rl.network.sumo_to_cityflow import run_converter

ROOT = Path(__file__).resolve().parent.parent
OSM_DIR = ROOT / "data" / "osm"
OUT_DIR = ROOT / "data" / "danang"
PBF_URL = "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"


def sh(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    # run_converter mounts os.getcwd() at /work inside the container and passes
    # the net/roadnet paths verbatim, so they MUST be relative to repo root.
    os.chdir(str(ROOT))
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bbox = yaml.safe_load((ROOT / "configs" / "network.yaml").read_text())["bbox"]["full"]
    left, bottom, right, top = bbox  # [minlon, minlat, maxlon, maxlat]

    pbf = OSM_DIR / "vietnam-latest.osm.pbf"
    if not pbf.exists():
        sh(["curl", "-L", "--fail", "-o", str(pbf), PBF_URL])

    clipped_pbf = OSM_DIR / "danang_full.osm.pbf"
    if not clipped_pbf.exists():
        sh(["osmium", "extract", "--overwrite",
            "-b", "{},{},{},{}".format(left, bottom, right, top),
            str(pbf), "-o", str(clipped_pbf)])

    osm_xml = OSM_DIR / "danang_full.osm"
    if not osm_xml.exists():
        sh(["osmium", "cat", "--overwrite", str(clipped_pbf), "-o", str(osm_xml)])

    sumo_net = OSM_DIR / "danang_full.net.xml"
    if not sumo_net.exists():
        run_netconvert(str(osm_xml), str(sumo_net))

    # paths relative to repo root (== mount point /work inside the container)
    sumo_net_rel = "data/osm/danang_full.net.xml"
    roadnet_rel = "data/danang/roadnet_full.json"
    run_converter(sumo_net_rel, roadnet_rel)
    print("Wrote", ROOT / roadnet_rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
