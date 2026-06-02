#!/usr/bin/env python3
"""Build the peak-hour scenario for the Hai Chau arterial network.

  PYTHONPATH=src python3 scripts/build_peak_flow.py

Creates a separate scenario `haichau_peak` (sharing the same arterial roadnet)
so the normal `haichau` scenario is kept intact for side-by-side comparison.
Models a rush-hour surge: a light background flow over the whole horizon plus a
dense burst concentrated in a peak window — where adaptive control (DQN /
Max-Pressure) is expected to beat Fixed-Time the most, because Fixed-Time cannot
re-time its phases for the surge.

Writes data/danang/flow_haichau_peak.json and copies roadnet_haichau.json ->
roadnet_haichau_peak.json. The peak window (engine steps = sim-seconds) is
printed so the eval can shade it.
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

    # Separate scenario sharing the arterial roadnet.
    shutil.copy(str(DATA / "roadnet_haichau.json"), str(DATA / "roadnet_haichau_peak.json"))
    out = DATA / "flow_haichau_peak.json"
    out.write_text(json.dumps(flows, indent=2))
    print("copied roadnet_haichau.json -> roadnet_haichau_peak.json")
    print("wrote {} ({} flows: {} background + {} peak)".format(
        out.name, len(flows), BASE_NUM, PEAK_NUM))
    print("peak window (decisions @interval 10): {}-{}".format(
        PEAK_START // 10, PEAK_END // 10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
