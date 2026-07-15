#!/usr/bin/env python3
"""Regenerate results/presentation/methods_<scen>.png from the MULTI-SEED aggregates
(results/multiseed/<scen>.json) so the figures match the multi-seed CI tables in
Chapter 4. Baselines are deterministic (no error bar); the DQN bar carries a 95%-CI
error bar. Host-side (matplotlib). Style matches scripts/build_presentation.py::chart_methods.

  python3 scripts/regen_methods_multiseed.py                 # all four
  python3 scripts/regen_methods_multiseed.py haichau_rush
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "presentation"
SCENS = ["haichau", "haichau_calib", "haichau_peak", "haichau_rush"]
LABEL = {"FixedTime": "FixedTime", "Random": "Random",
         "MaxPressure": "MaxPressure", "DQN": "DQN"}


def regen(scen):
    p = ROOT / "results" / "multiseed" / (scen + ".json")
    if not p.exists():
        print("skip (no aggregate):", scen); return None
    agg = json.loads(p.read_text())["aggregate"]
    fxw = agg["FixedTime"]["wait_hours"]["mean"]
    rows = []  # (label, reduction%, ci_pct, is_dqn)
    for c in ("FixedTime", "Random", "MaxPressure", "DQN"):
        if c not in agg:
            continue
        w = agg[c]["wait_hours"]["mean"]
        red = (fxw - w) / fxw * 100 if fxw else 0.0
        ci = (agg[c]["wait_hours"]["ci95"] / fxw * 100) if (fxw and c == "DQN") else 0.0
        rows.append((LABEL[c], red, ci, c == "DQN"))
    rows.sort(key=lambda x: x[1])
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]
    errs = [r[2] for r in rows]
    colors = ["#c0392b" if v < 0 else ("#27ae60" if "MaxPressure" in l else "#2980b9")
              for l, v, _, _ in rows]
    fig, ax = plt.subplots(figsize=(10, max(3, 0.5 * len(rows) + 1)))
    ax.barh(labels, vals, color=colors,
            xerr=[[e for e in errs], [e for e in errs]],
            error_kw=dict(ecolor="#333", capsize=4, lw=1.2))
    ax.axvline(0, color="k", lw=0.8)
    ax.axvline(25, color="orange", ls="--", lw=1.2, label="25% target")
    for i, (l, v, ci, is_dqn) in enumerate(rows):
        txt = "%+.1f%%" % v + (" $\\pm$%.1f" % ci if is_dqn and ci else "")
        # start the label past the error-bar cap so they don't collide
        x = (v + ci + 0.6) if v >= 0 else (v - ci - 0.6)
        ax.text(x, i, txt, va="center", ha="left" if v >= 0 else "right", fontsize=9)
    ax.set_xlabel("Waiting-time reduction vs Fixed-Time (%)  —  multi-seed mean $\\pm$ 95% CI (DQN)")
    ax.set_title("Method comparison — %s" % scen)
    ax.legend(loc="lower right")
    fig.tight_layout()
    out = OUT / ("methods_%s.png" % scen)
    fig.savefig(out, dpi=130); plt.close(fig)
    print("wrote", out, "| DQN %+.1f%% (+/-%.1f), MP %+.1f%%" % (
        rows[[r[3] for r in rows].index(True)][1] if any(r[3] for r in rows) else 0,
        next((r[2] for r in rows if r[3]), 0),
        next((r[1] for r in rows if r[0] == "MaxPressure"), 0)))
    return out


def main():
    for s in (sys.argv[1:] or SCENS):
        regen(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
