#!/usr/bin/env python3
"""Build a CityFlow roadnet + synthetic flow for any configured bbox area.

  python3 scripts/build_network.py haichau

Reads the bbox from configs/network.yaml (key `bbox.<area>`), clips the cached
Vietnam PBF with osmium, converts to a SUMO net with netconvert, then to a
CityFlow roadnet via the converter (Docker/Colima), and finally generates a
motorbike-heavy synthetic flow with flow_gen. Outputs:
  data/danang/roadnet_<area>.json
  data/danang/flow_<area>.json

netconvert + osmium must be on PATH; the converter step uses Docker.
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

from traffic_rl.network.osm_to_sumo import run_netconvert
from traffic_rl.network.sumo_to_cityflow import run_converter
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.network.flow_gen import write_flow

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
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau"
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    net_cfg = yaml.safe_load((ROOT / "configs" / "network.yaml").read_text())
    bbox = net_cfg["bbox"][area]
    left, bottom, right, top = bbox  # [minlon, minlat, maxlon, maxlat]
    flow_cfg = net_cfg["flow"]

    pbf = OSM_DIR / "vietnam-latest.osm.pbf"
    if not pbf.exists():
        sh(["curl", "-L", "--fail", "-o", str(pbf), PBF_URL])

    clipped_pbf = OSM_DIR / "danang_{}.osm.pbf".format(area)
    if not clipped_pbf.exists():
        sh(["osmium", "extract", "--overwrite",
            "-b", "{},{},{},{}".format(left, bottom, right, top),
            str(pbf), "-o", str(clipped_pbf)])

    osm_xml = OSM_DIR / "danang_{}.osm".format(area)
    if not osm_xml.exists():
        sh(["osmium", "cat", "--overwrite", str(clipped_pbf), "-o", str(osm_xml)])

    sumo_net = OSM_DIR / "danang_{}.net.xml".format(area)
    if not sumo_net.exists():
        run_netconvert(str(osm_xml), str(sumo_net),
                       tls_default_type=net_cfg.get("netconvert", {}).get("tls_default_type", "actuated"),
                       drop_road_types=net_cfg.get("netconvert", {}).get("drop_road_types"))

    # paths relative to repo root (== mount point /work inside the container)
    sumo_net_rel = "data/osm/danang_{}.net.xml".format(area)
    roadnet_rel = "data/danang/roadnet_{}.json".format(area)
    run_converter(sumo_net_rel, roadnet_rel)
    print("Wrote", ROOT / roadnet_rel)

    # Flow generation is pure-python (host); reuse the network.yaml flow params.
    rn = RoadNet.load(roadnet_rel)
    flow_rel = "data/danang/flow_{}.json".format(area)
    write_flow(rn, flow_rel,
               num_flows=flow_cfg["num_flows"],
               route_length=flow_cfg["route_length"],
               seed=flow_cfg["seed"],
               motorbike_ratio=flow_cfg["motorbike_ratio"],
               start_time=flow_cfg["start_time"],
               end_time=flow_cfg["end_time"],
               interval=flow_cfg.get("interval", 2.0))
    print("Wrote", ROOT / flow_rel)
    print("Signalized intersections:", len(rn.signalized_ids()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
