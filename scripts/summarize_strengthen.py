#!/usr/bin/env python3
"""Summarize the strengthened-study outputs (agreement / incident / demand-shift)
into copy-pasteable numbers for Chapter 4. Host-side; reads only JSON on disk, so
it is safe to run repeatedly. Missing outputs are reported as pending.

  PYTHONPATH=src python3 scripts/summarize_strengthen.py            # rush + calib
  PYTHONPATH=src python3 scripts/summarize_strengthen.py haichau_rush
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CTRLS = ["FixedTime", "MaxPressure", "Random", "DQN"]


def _load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else None


def _native_dqn_queue(area):
    """DQN queue on its OWN flow (multi-seed mean) — the reference for shift."""
    d = _load(ROOT / "results" / "multiseed" / (area + ".json"))
    if not d:
        return None
    return d["aggregate"]["DQN"]["mean_total_queue"]["mean"]


def agreement(area):
    d = _load(ROOT / "results" / area / "agreement" / "agreement.json")
    print("\n## agreement  [%s]" % area)
    if not d:
        print("   (pending — no agreement.json)"); return
    per = list(d.get("per_agent", {}).values())
    hi = sum(1 for v in per if v >= 0.7)
    print("   overall DQN<->MP agree_rate = %.1f%%  (%d decisions, %d agent-pairs)"
          % (100 * d["agree_rate"], d["n_decisions"], d["n_pairs"]))
    if per:
        print("   per-intersection: mean %.1f%%, min %.1f%%, max %.1f%%; %d/%d agents >=70%%"
              % (100 * (sum(per) / len(per)), 100 * min(per), 100 * max(per), hi, len(per)))


def incident(area):
    d = _load(ROOT / "results" / area / "robustness" / "incident.json")
    print("\n## incident  [%s]" % area)
    if not d:
        print("   (pending — no incident.json)"); return
    inc = d["incident"]
    print("   blocked %s at phase %d for steps [%d,%d)"
          % (inc["inter_id"], inc["block_phase"], inc["t0"], inc["t1"]))
    q = {}
    for lvl in d["levels"]:
        q[lvl["condition"]] = {r["controller"]: r["mean_total_queue"] for r in lvl["rows"]}
    none, wi = q.get("none", {}), q.get("incident", {})
    print("   %-12s %10s %10s %10s" % ("controller", "clean", "incident", "degrade"))
    for c in CTRLS:
        if c in none and c in wi:
            b, a = none[c], wi[c]
            deg = 100 * (a - b) / b if b else 0.0
            print("   %-12s %10.1f %10.1f %9.1f%%" % (c, b, a, deg))


def shift(area):
    d = _load(ROOT / "results" / area / "robustness" / "shift.json")
    print("\n## demand-shift  [DQN trained on %s]" % area)
    if not d:
        print("   (pending — no shift.json)"); return
    flow = d.get("flow_area")
    rows = {r["controller"]: r["mean_total_queue"] for r in d["levels"][0]["rows"]}
    native = _native_dqn_queue(flow)
    print("   evaluated on flow=%s  (queue, lower better)" % flow)
    for c in CTRLS:
        if c in rows:
            print("   %-12s %10.1f" % (c, rows[c]))
    if native is not None and "DQN" in rows:
        gap = 100 * (rows["DQN"] - native) / native
        print("   -> transferred DQN queue %.1f vs %s-native DQN %.1f  (%+.1f%% shift cost)"
              % (rows["DQN"], flow, native, gap))


def main():
    areas = sys.argv[1:] or ["haichau_rush", "haichau_calib"]
    for a in areas:
        agreement(a)
        incident(a)
        shift(a)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
