#!/usr/bin/env python3
"""Run all four controllers on the same scenario and produce the comparison.

  make cf-run CMD="pip install dataclasses numpy pyyaml matplotlib >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/run_comparison.py full"
Loads the trained DQN checkpoint from results/<area>/dqn_<area>.npz.
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
from traffic_rl.agents.dqn import SharedDQN, DQNController
from traffic_rl.eval.runner import run_episode
from traffic_rl.eval import compare

ROOT = Path(__file__).resolve().parent.parent


# Evaluation horizon (engine steps). Longer horizons let congestion build so the
# controllers separate more sharply; override with MAX_STEPS=<n>.
EVAL_STEPS = int(os.environ.get("MAX_STEPS", "1000"))


def _env(rn, area, tag, results_dir):
    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
           "roadnetLogFile": "replay_roadnet_{}.json".format(area),
           "replayLogFile": "replay_{}_{}.txt".format(tag, area)}
    cfg_path = results_dir / "config_cmp_{}.json".format(tag)
    cfg_path.write_text(json.dumps(cfg))
    return MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                                action_interval=10, max_steps=EVAL_STEPS,
                                yellow_time=3, min_green=10)


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    data_dir = ROOT / "data" / "danang"
    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    rows = []
    for tag, make in [
        ("fixed_time", lambda e: FixedTimeController(e.num_actions)),
        ("max_pressure", lambda e: MaxPressureController(rn)),
        ("random", lambda e: RandomController(e.num_actions, seed=0))]:
        env = _env(rn, area, tag, results_dir)
        rows.append(run_episode(env, make(env)))

    ckpt = results_dir / "dqn_{}.npz".format(area)
    if ckpt.exists():
        env = _env(rn, area, "dqn", results_dir)
        net = SharedDQN(env.obs_dim, env.encoder.max_green)
        net.load(str(ckpt))
        rows.append(run_episode(env, DQNController(net, env.agent_ids)))
    else:
        print("NOTE: {} missing -> skipping DQN (baselines only). "
              "Train it, then re-run this for the full comparison.".format(ckpt))

    report = compare.write_report(rows, str(results_dir / "comparison.json"))
    # matplotlib has no Python-3.6 wheel, so plotting may be unavailable in the
    # CityFlow container. The metrics JSON is already written above; if plotting
    # fails here, regenerate the PNGs on the host:
    #   PYTHONPATH=src python3 -c "import json; from traffic_rl.eval import compare; \
    #     rows=json.load(open('results/full/comparison.json'))['table']; \
    #     compare.plot_metrics(rows,'results/full/comparison_metrics.png')"
    try:
        compare.plot_metrics(rows, str(results_dir / "comparison_metrics.png"))
        train_log = results_dir / "train_log_{}.json".format(area)
        if train_log.exists():
            compare.plot_training_curve(json.loads(train_log.read_text()),
                                        str(results_dir / "training_curve.png"))
    except ImportError as exc:
        print("WARNING: plotting skipped (%s); run the plot step on the host." % exc)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
