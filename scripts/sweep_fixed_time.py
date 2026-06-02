#!/usr/bin/env python3
"""Sweep the Fixed-Time green duration to pick the strongest fair baseline.

Evaluates Fixed-Time at several green-per-phase durations (default 10/25/30/40/50s)
on one scenario and reports mean queue for each, so we can adopt the best as the
strengthened baseline. 10s is the legacy switch-every-interval plan, for reference.

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    MAX_STEPS=800 PYTHONPATH=src python3 scripts/sweep_fixed_time.py haichau"
"""
import json
import os
import sys
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent
EVAL_STEPS = int(os.environ.get("MAX_STEPS", "800"))
DURATIONS = [int(x) for x in os.environ.get("GREENS", "10,25,30,40,50").split(",")]


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau"
    data_dir = ROOT / "data" / "danang"
    out_dir = ROOT / "results" / area / "fixed_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    results = []
    for g in DURATIONS:
        cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
               "roadnetFile": "roadnet_{}.json".format(area),
               "flowFile": "flow_{}.json".format(area),
               "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
        cfg_path = out_dir / "config_g{}.json".format(g)
        cfg_path.write_text(json.dumps(cfg))
        env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                                   action_interval=10, max_steps=EVAL_STEPS,
                                   yellow_time=3, min_green=10)
        row = run_episode(env, FixedTimeController(env.num_actions,
                                                   green_duration=g, action_interval=10))
        results.append({"green_duration": g,
                        "mean_total_queue": row["mean_total_queue"],
                        "final_average_travel_time": row["final_average_travel_time"]})
        print("green=%2ds  queue=%.1f  tt=%.1f"
              % (g, row["mean_total_queue"], row["final_average_travel_time"]))

    best = min(results, key=lambda r: r["mean_total_queue"])
    (out_dir / "sweep.json").write_text(json.dumps(
        {"area": area, "eval_steps": EVAL_STEPS, "results": results, "best": best}, indent=2))
    print("BEST green=%ds (queue=%.1f) -> set fixed_green_duration in training.yaml"
          % (best["green_duration"], best["mean_total_queue"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
