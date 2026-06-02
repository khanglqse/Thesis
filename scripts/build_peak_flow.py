#!/usr/bin/env python3
"""Build a peak-hour demand profile for the Hai Chau arterial network.

  PYTHONPATH=src python3 scripts/build_peak_flow.py

Models a rush-hour surge: a light background flow over the whole horizon plus a
dense burst concentrated in a peak window. This is where adaptive control
(DQN / Max-Pressure) is expected to beat Fixed-Time the most, because Fixed-Time
cannot re-time its phases for the surge.

Writes data/danang/flow_haichau.json (the active scenario) and keeps the previous
uniform flow as flow_haichau_uniform.json for reference. The peak window (in
engine steps, = sim-seconds at interval 1.0) is printed so the eval can shade it.
"""
import json
import os
import shutil
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.network.flow_gen import generate_flow

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "danang"

# Profile (sim-seconds). Eval at MAX_STEPS=1000 covers it: light -> surge -> drain.
HORIZON = 1000
PEAK_START, PEAK_END = 250, 600
BASE_NUM, BASE_INTERVAL = 120, 4.0      # light background all hour
# CityFlow requires interval >= 1; create the surge with many concurrent peak
# flows at the minimum interval rather than a sub-second rate.
PEAK_NUM, PEAK_INTERVAL = 800, 1.0      # dense rush-hour burst
ROUTE_LEN, MOTORBIKE = 6, 0.92


def main():
    os.chdir(str(ROOT))
    rn = RoadNet.load(str(DATA / "roadnet_haichau.json"))
    base = generate_flow(rn, num_flows=BASE_NUM, route_length=ROUTE_LEN, seed=42,
                         motorbike_ratio=MOTORBIKE, start_time=0, end_time=HORIZON,
                         interval=BASE_INTERVAL)
    peak = generate_flow(rn, num_flows=PEAK_NUM, route_length=ROUTE_LEN, seed=99,
                         motorbike_ratio=MOTORBIKE, start_time=PEAK_START,
                         end_time=PEAK_END, interval=PEAK_INTERVAL)
    flows = base + peak

    out = DATA / "flow_haichau.json"
    uniform_backup = DATA / "flow_haichau_uniform.json"
    if out.exists() and not uniform_backup.exists():
        shutil.copy(str(out), str(uniform_backup))
        print("backed up uniform flow ->", uniform_backup.name)
    out.write_text(json.dumps(flows, indent=2))
    print("wrote {} ({} flows: {} background + {} peak)".format(
        out.name, len(flows), BASE_NUM, PEAK_NUM))
    print("peak window (decisions @interval 10): {}-{}".format(
        PEAK_START // 10, PEAK_END // 10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
