#!/usr/bin/env python3
"""C2: measure DQN <-> Max-Pressure phase agreement on a scenario.

Loads the frozen DQN checkpoint, drives it through one eval episode, and at each
decision also computes Max-Pressure's choice on the same state (not applied),
recording agreement per intersection. Writes results/<area>/agreement/agreement.json.

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    COUNT_NORM=5 PYTHONPATH=src python3 scripts/run_agreement.py haichau_rush"

COUNT_NORM must match the checkpoint's training (rush=5, calib=10, others=40).
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
from traffic_rl.agents.max_pressure import MaxPressureController
from traffic_rl.eval.agreement import run_agreement

ROOT = Path(__file__).resolve().parent.parent
EVAL_STEPS = int(os.environ.get("MAX_STEPS", "1000"))
_TRAIN_CFG = yaml.safe_load((ROOT / "configs" / "training.yaml").read_text())
COUNT_NORM = float(os.environ.get("COUNT_NORM", _TRAIN_CFG.get("count_norm", 10.0)))


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau_rush"
    exp_tag = os.environ.get("EXP_TAG")           # optional: eval an exp_<tag> ckpt
    base = ROOT / "results" / area
    ckpt_dir = base / ("exp_" + exp_tag) if exp_tag else base
    out_dir = base / "agreement"
    out_dir.mkdir(parents=True, exist_ok=True)

    rn = RoadNet.load(str(ROOT / "data" / "danang" / "roadnet_{}.json".format(area)))
    # reconstruct the net with the checkpoint's architecture from its train log
    meta = {}
    tlog = ckpt_dir / "train_log_{}.json".format(area)
    if tlog.exists():
        meta = json.loads(tlog.read_text()).get("meta", {})
    state_mode = meta.get("state_mode", "basic")
    hidden = int(meta.get("hidden", _TRAIN_CFG.get("hidden", 64)))
    dueling = bool(meta.get("dueling", False))

    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
    cfg_path = out_dir / "config_agreement.json"
    cfg_path.write_text(json.dumps(cfg))

    env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                               action_interval=10, max_steps=EVAL_STEPS,
                               yellow_time=3, min_green=10, count_norm=COUNT_NORM,
                               state_mode=state_mode)
    net = SharedDQN(env.obs_dim, env.encoder.max_green, hidden=hidden, dueling=dueling)
    net.load(str(ckpt_dir / "dqn_{}.npz".format(area)))

    summary = run_agreement(env, DQNController(net, env.agent_ids),
                            MaxPressureController(rn))
    (out_dir / "agreement.json").write_text(json.dumps(summary, indent=2))
    print("agreement %s: rate=%.3f over %d decisions, %d agent-pairs"
          % (area, summary["agree_rate"], summary["n_decisions"], summary["n_pairs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
