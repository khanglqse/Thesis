#!/usr/bin/env python3
"""Produce browser-loadable demo replays by truncating the full replays.

  PYTHONPATH=src python3 scripts/truncate_replay.py [area] [n_steps]

Writes results/<area>/demo/replay_<controller>_demo.txt for each controller whose
full replay exists at data/danang/replay_<controller>_<area>.txt. Defaults:
area=full, n_steps=120 (~90 MB each, vs ~760 MB full).
"""
import os
import sys
from pathlib import Path

from traffic_rl.report.replay import truncate_replay

ROOT = Path(__file__).resolve().parent.parent
CONTROLLERS = ["fixed_time", "max_pressure", "random", "dqn"]


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    data_dir = ROOT / "data" / "danang"
    demo_dir = ROOT / "results" / area / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    for c in CONTROLLERS:
        src = data_dir / "replay_{}_{}.txt".format(c, area)
        if not src.exists():
            print("skip {} (no {})".format(c, src.name))
            continue
        dst = demo_dir / "replay_{}_demo.txt".format(c)
        written = truncate_replay(str(src), str(dst), n)
        print("{}: {} steps -> {}".format(c, written, dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
