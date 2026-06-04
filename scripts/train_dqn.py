#!/usr/bin/env python3
"""Train the shared DQN on a CityFlow scenario (run inside Docker via Colima).

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/train_dqn.py full"

Optional env-var overrides (handy for a quick smoke without editing the config):
  EPISODES=2 MAX_STEPS=200 ... python3 scripts/train_dqn.py full
"""
import json
import os
import sys
from pathlib import Path

import yaml

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.train.trainer import train

ROOT = Path(__file__).resolve().parent.parent


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    cfg = yaml.safe_load((ROOT / "configs" / "training.yaml").read_text())
    if os.environ.get("EPISODES"):
        cfg["episodes"] = int(os.environ["EPISODES"])
    if os.environ.get("MAX_STEPS"):
        cfg["max_steps"] = int(os.environ["MAX_STEPS"])
    # Experiment overrides (keep references intact): pick a reward, toggle dueling,
    # and route outputs into results/<area>/exp_<tag>/ so nothing overwrites the
    # frozen baseline checkpoint in results/<area>/.
    if os.environ.get("REWARD_TYPE"):
        cfg["reward_type"] = os.environ["REWARD_TYPE"]
    if os.environ.get("STATE_MODE"):
        cfg["state_mode"] = os.environ["STATE_MODE"]
    if os.environ.get("DUELING"):
        cfg["dueling"] = os.environ["DUELING"] not in ("0", "", "false", "False")
    if os.environ.get("COUNT_NORM"):
        cfg["count_norm"] = float(os.environ["COUNT_NORM"])
    if os.environ.get("N_STEP"):
        cfg["n_step"] = int(os.environ["N_STEP"])
    if os.environ.get("WARMSTART_STEPS"):
        cfg["warmstart_steps"] = int(os.environ["WARMSTART_STEPS"])

    data_dir = ROOT / "data" / "danang"
    exp_tag = os.environ.get("EXP_TAG")
    results_dir = ROOT / "results" / area / ("exp_" + exp_tag) if exp_tag \
        else ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    def env_factory():
        run_cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
                   "roadnetFile": "roadnet_{}.json".format(area),
                   "flowFile": "flow_{}.json".format(area),
                   "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
        cfg_path = results_dir / "config_train.json"
        cfg_path.write_text(json.dumps(run_cfg))
        return MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                                    action_interval=cfg["action_interval"],
                                    max_steps=cfg["max_steps"],
                                    yellow_time=cfg["yellow_time"],
                                    min_green=cfg["min_green"],
                                    count_norm=cfg.get("count_norm", 10.0),
                                    reward_type=cfg.get("reward_type", "pressure"),
                                    state_mode=cfg.get("state_mode", "basic"))

    train(env_factory, cfg,
          ckpt_path=str(results_dir / "dqn_{}.npz".format(area)),
          log_path=str(results_dir / "train_log_{}.json".format(area)))
    print("Saved checkpoint + log to", results_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
