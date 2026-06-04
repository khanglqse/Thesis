#!/usr/bin/env python3
"""Evaluate ONE trained DQN variant and compare it against the frozen baselines.

The baselines (Fixed-Time, Max-Pressure, Random) are deterministic for a fixed
seed, so we reuse their rows from the area's reference comparison.json instead of
re-running them in the (slow, emulated) CityFlow container. Only the DQN variant
is evaluated here, then merged into a fresh comparison for the experiment.

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    EXP_TAG=queue PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau"

Reads results/<area>/exp_<tag>/dqn_<area>.npz and its train_log meta (for the
dueling flag), writes results/<area>/exp_<tag>/comparison.json.
"""
import json
import os
import sys
from pathlib import Path

import yaml

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.dqn import SharedDQN, DQNController
from traffic_rl.eval.runner import run_episode
from traffic_rl.eval import compare

ROOT = Path(__file__).resolve().parent.parent

EVAL_STEPS = int(os.environ.get("MAX_STEPS", "1000"))
_TRAIN_CFG = yaml.safe_load((ROOT / "configs" / "training.yaml").read_text())
COUNT_NORM = float(os.environ.get("COUNT_NORM", _TRAIN_CFG.get("count_norm", 10.0)))


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau"
    exp_tag = os.environ.get("EXP_TAG")
    if not exp_tag:
        print("ERROR: set EXP_TAG (e.g. EXP_TAG=queue) to name the experiment.")
        return 2

    data_dir = ROOT / "data" / "danang"
    base_dir = ROOT / "results" / area
    exp_dir = base_dir / ("exp_" + exp_tag)
    exp_dir.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    # Reuse the deterministic baseline rows from the reference comparison.
    base_cmp = json.loads((base_dir / "comparison.json").read_text())
    rows = [r for r in base_cmp["table"] if r["controller"] != "DQN"]

    # Construct the net with the architecture this checkpoint was trained with.
    meta = {}
    tlog = exp_dir / "train_log_{}.json".format(area)
    if tlog.exists():
        meta = json.loads(tlog.read_text()).get("meta", {})
    dueling = bool(meta.get("dueling", False))
    hidden = int(meta.get("hidden", _TRAIN_CFG.get("hidden", 64)))
    state_mode = meta.get("state_mode", "basic")

    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
    cfg_path = exp_dir / "config_cmp_dqn.json"
    cfg_path.write_text(json.dumps(cfg))
    # Eval reward stays 'pressure' (the baselines' reward) so mean_reward is
    # comparable across controllers; queue/travel time are reward-independent.
    env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                               action_interval=10, max_steps=EVAL_STEPS,
                               yellow_time=3, min_green=10, count_norm=COUNT_NORM,
                               state_mode=state_mode)
    net = SharedDQN(env.obs_dim, env.encoder.max_green, hidden=hidden, dueling=dueling)
    net.load(str(exp_dir / "dqn_{}.npz".format(area)))
    rows.append(run_episode(env, DQNController(net, env.agent_ids)))

    report = compare.write_report(rows, str(exp_dir / "comparison.json"))
    print("variant: reward_type=%s state_mode=%s dueling=%s hidden=%s"
          % (meta.get("reward_type", "?"), state_mode, dueling, hidden))
    print(json.dumps({k: v for k, v in report.items() if k != "table"}, indent=2))
    for r in report["table"]:
        print("  %-12s queue=%.1f tt=%.1f reward=%.2f"
              % (r["controller"], r.get("mean_total_queue", 0),
                 r["final_average_travel_time"], r.get("mean_reward", 0) or 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
