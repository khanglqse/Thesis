#!/usr/bin/env python3
"""Sweep demand level to find the saturation regime with the largest control gap.

The current flow oversaturates (queues grow unbounded -> every controller is
throughput-limited -> small % differences). Adaptive control shows its biggest
advantage near v/c ~ 0.85-0.95, where Fixed-Time blows up but Max-Pressure keeps
queues stable. This scales the base flow's injection interval by several factors
and, for each, evaluates Fixed-Time and Max-Pressure, reporting the queue gap so
we can pick the demand that maximises control leverage.

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    MAX_STEPS=1000 PYTHONPATH=src python3 scripts/sweep_demand.py haichau"
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
from traffic_rl.eval.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent
EVAL_STEPS = int(os.environ.get("MAX_STEPS", "1000"))
# interval multipliers: 1.0 = current (oversaturated); higher = less demand.
FACTORS = [float(x) for x in os.environ.get("FACTORS", "1,2,3,4,6,8").split(",")]
FIXED_GREEN = float(os.environ.get("FIXED_GREEN", "25"))


def _scale_flow(base_path, factor, out_path):
    flows = json.loads(Path(base_path).read_text())
    for fl in flows:
        fl["interval"] = round(fl.get("interval", 1.5) * factor, 3)
    Path(out_path).write_text(json.dumps(flows))


def _steady(qs):
    """Mean queue over the last quartile (steady-state, past the fill-up)."""
    if not qs:
        return 0.0
    tail = qs[int(0.75 * len(qs)):] or qs
    return sum(tail) / len(tail)


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "haichau"
    data = ROOT / "data" / "danang"
    out = ROOT / "results" / area / "demand_sweep"
    out.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(data / "roadnet_{}.json".format(area)))
    base_flow = data / "flow_{}.json".format(area)

    results = []
    print("factor demand%  Fixed_mean  MP_mean  gap_mean%  Fixed_steady MP_steady gap_steady%")
    for f in FACTORS:
        flow_path = data / "flow_{}_d{}.json".format(area, f)
        _scale_flow(str(base_flow), f, str(flow_path))
        rows = {}
        for tag, make in (("FixedTime", lambda e: FixedTimeController(e.num_actions, FIXED_GREEN, 10)),
                          ("MaxPressure", lambda e: MaxPressureController(rn))):
            cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
                   "roadnetFile": "roadnet_{}.json".format(area),
                   "flowFile": "flow_{}_d{}.json".format(area, f),
                   "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
            cp = out / "cfg_{}_{}.json".format(tag, f)
            cp.write_text(json.dumps(cfg))
            env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cp)), action_interval=10,
                                       max_steps=EVAL_STEPS, yellow_time=3, min_green=10)
            rows[tag] = run_episode(env, make(env))
        fm = rows["FixedTime"]["mean_total_queue"]; mm = rows["MaxPressure"]["mean_total_queue"]
        fs = _steady(rows["FixedTime"]["queue_series"]); ms = _steady(rows["MaxPressure"]["queue_series"])
        gm = (fm - mm) / fm * 100 if fm else 0
        gs = (fs - ms) / fs * 100 if fs else 0
        print("%5.1f  %5.0f   %9.1f %8.1f  %8.1f%%  %11.1f %9.1f %9.1f%%"
              % (f, 100.0 / f, fm, mm, gm, fs, ms, gs))
        results.append({"factor": f, "fixed_mean": fm, "mp_mean": mm, "gap_mean_pct": gm,
                        "fixed_steady": fs, "mp_steady": ms, "gap_steady_pct": gs})
    (out / "sweep.json").write_text(json.dumps(results, indent=2))
    best = max(results, key=lambda r: r["gap_steady_pct"])
    print("\nMax control gap (steady) at factor=%.1f (demand %.0f%%): Fixed vs MP = %.1f%%"
          % (best["factor"], 100.0 / best["factor"], best["gap_steady_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
