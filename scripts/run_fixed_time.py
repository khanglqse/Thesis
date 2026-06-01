#!/usr/bin/env python3
"""Run the Fixed-Time controller on a CityFlow scenario; save replay + metrics.

Must run inside the CityFlow Docker image (needs cityflow). Example:
  make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_fixed_time.py subarea"
"""
import json
import sys
from pathlib import Path

from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

ROOT = Path(__file__).resolve().parent.parent


def main():
    area = sys.argv[1] if len(sys.argv) > 1 else "subarea"
    data_dir = ROOT / "data" / "danang"
    roadnet_file = "roadnet_{}.json".format(area)
    flow_file = "flow_{}.json".format(area)

    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    # CityFlow resolves roadnetFile/flowFile/log files all relative to `dir`,
    # so the replay must be written alongside the roadnet (in data/danang/).
    cfg = {
        "interval": 1.0, "seed": 0, "dir": "data/danang/",
        "roadnetFile": roadnet_file, "flowFile": flow_file,
        "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
        "roadnetLogFile": "replay_roadnet_{}.json".format(area),
        "replayLogFile": "replay_{}.txt".format(area),
    }
    cfg_path = results_dir / "config_runtime.json"
    cfg_path.write_text(json.dumps(cfg, indent=2))

    rn = RoadNet.load(str(data_dir / roadnet_file))
    engine = CityFlowEngine(str(cfg_path))
    env = MultiAgentTrafficEnv(rn, engine, action_interval=10, max_steps=1000)
    controller = FixedTimeController(num_actions=env.num_actions)

    obs = env.reset()
    controller.reset()
    done = False
    info = {}
    while not done:
        ctx = {"observations": obs,
               "waiting_counts": env.current_waiting_counts(),
               "action_masks": env.action_masks()}
        actions = controller.act(ctx)
        obs, _, done, info = env.step(actions)

    metrics = {
        "controller": "FixedTime",
        "area": area,
        "agents": len(env.agent_ids),
        "final_average_travel_time": info.get("average_travel_time"),
        "final_vehicle_count": info.get("vehicle_count"),
        "steps": info.get("step"),
    }
    (results_dir / "metrics_fixed_time.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print("Replay:", data_dir / "replay_roadnet_{}.json".format(area), data_dir / "replay_{}.txt".format(area))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
