#!/usr/bin/env python3
"""C3: robustness of each controller under sensor noise (and demand shift).

mode=noise : sweep observation-noise levels; wrap the engine in PerturbedEngine so
             DQN + Max-Pressure see corrupted counts (Fixed-Time/Random are immune),
             eval all four, and record per-level rows. Expectation: the learned DQN
             degrades more gracefully than Max-Pressure, which needs exact pressure.
mode=shift : eval the DQN trained on <area> on a DIFFERENT scenario's flow (arg 3),
             measuring generalization.

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    COUNT_NORM=5 PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush noise"

Writes results/<area>/robustness/<mode>.json. COUNT_NORM must match the checkpoint.
"""
import json
import os
import sys
from pathlib import Path

import yaml

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.perturbations import PerturbedEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import MaxPressureController
from traffic_rl.agents.random_agent import RandomController
from traffic_rl.agents.dqn import SharedDQN, DQNController
from traffic_rl.eval.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent
EVAL_STEPS = int(os.environ.get("MAX_STEPS", "1000"))
_CFG = yaml.safe_load((ROOT / "configs" / "training.yaml").read_text())
COUNT_NORM = float(os.environ.get("COUNT_NORM", _CFG.get("count_norm", 10.0)))
FIXED_GREEN = float(os.environ.get("FIXED_GREEN", _CFG.get("fixed_green_duration", 40)))
NOISE_LEVELS = [0.0, 0.1, 0.2, 0.4, 0.8]


def _engine(area, flow_area, tag, out_dir, noise_std):
    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(flow_area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
    p = out_dir / "cfg_{}.json".format(tag)
    p.write_text(json.dumps(cfg))
    eng = CityFlowEngine(str(p))
    if noise_std > 0:
        eng = PerturbedEngine(eng, noise_std=noise_std, seed=0)
    return eng


def _dqn_meta(ckpt_dir, area):
    meta = {}
    tlog = ckpt_dir / "train_log_{}.json".format(area)
    if tlog.exists():
        meta = json.loads(tlog.read_text()).get("meta", {})
    return (meta.get("state_mode", "basic"),
            int(meta.get("hidden", _CFG.get("hidden", 64))),
            bool(meta.get("dueling", False)))


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau_rush"
    mode = sys.argv[2] if len(sys.argv) > 2 else "noise"
    base = ROOT / "results" / area
    out_dir = base / "robustness"
    out_dir.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(ROOT / "data" / "danang" / "roadnet_{}.json".format(area)))
    state_mode, hidden, dueling = _dqn_meta(base, area)

    def make_env(flow_area, noise_std, tag):
        eng = _engine(area, flow_area, tag, out_dir, noise_std)
        return MultiAgentTrafficEnv(rn, eng, action_interval=10, max_steps=EVAL_STEPS,
                                    yellow_time=3, min_green=10, count_norm=COUNT_NORM,
                                    state_mode=state_mode)

    def dqn_ctrl(env):
        net = SharedDQN(env.obs_dim, env.encoder.max_green, hidden=hidden, dueling=dueling)
        net.load(str(base / "dqn_{}.npz".format(area)))
        return DQNController(net, env.agent_ids)

    levels = NOISE_LEVELS if mode == "noise" else [0.0]
    flow_area = sys.argv[3] if (mode == "shift" and len(sys.argv) > 3) else area
    out = {"area": area, "mode": mode, "flow_area": flow_area, "levels": []}
    for lv in levels:
        rows = []
        for tag, mk in [
            ("fixed", lambda e: FixedTimeController(e.num_actions, green_duration=FIXED_GREEN, action_interval=10)),
            ("mp", lambda e: MaxPressureController(rn)),
            ("rand", lambda e: RandomController(e.num_actions, seed=0)),
            ("dqn", dqn_ctrl)]:
            env = make_env(flow_area, lv, "{}_{}".format(tag, lv))
            rows.append(run_episode(env, mk(env)))
        out["levels"].append({"noise_std": lv,
                              "rows": [{k: r[k] for k in ("controller", "mean_total_queue",
                                        "final_average_travel_time", "queue_series")} for r in rows]})
        print("noise=%.2f: " % lv + " ".join("%s=%.0f" % (r["controller"], r["mean_total_queue"]) for r in rows))
    (out_dir / "{}.json".format(mode)).write_text(json.dumps(out))
    print("wrote", out_dir / "{}.json".format(mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
