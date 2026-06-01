#!/usr/bin/env python3
"""Run one baseline controller on a CityFlow scenario; save metrics + replay.

Inside Docker (via Colima):
  make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/run_baseline.py max_pressure full"
controller in {fixed_time, max_pressure, random}; area in {subarea, full}.
"""
import json
import os
import sys
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import MaxPressureController
from traffic_rl.agents.random_agent import RandomController
from traffic_rl.eval.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent


def main():
    os.chdir(str(ROOT))
    which = sys.argv[1] if len(sys.argv) > 1 else "max_pressure"
    area = sys.argv[2] if len(sys.argv) > 2 else "full"
    data_dir = ROOT / "data" / "danang"
    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
           "roadnetLogFile": "replay_roadnet_{}.json".format(area),
           "replayLogFile": "replay_{}_{}.txt".format(which, area)}
    cfg_path = results_dir / "config_{}.json".format(which)
    cfg_path.write_text(json.dumps(cfg, indent=2))

    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))
    env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                               action_interval=10, max_steps=1000,
                               yellow_time=3, min_green=10)
    ctrl = {"fixed_time": lambda: FixedTimeController(env.num_actions),
            "max_pressure": lambda: MaxPressureController(rn),
            "random": lambda: RandomController(env.num_actions, seed=0)}[which]()

    metrics = run_episode(env, ctrl)
    metrics["area"] = area
    (results_dir / "metrics_{}.json".format(which)).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
