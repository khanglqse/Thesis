#!/usr/bin/env python3
"""Plot sensor-noise robustness: mean total queue vs observation-noise level, one line per
controller, from results/<area>/robustness/noise.json (GROUND-TRUTH metric — the controller
reads perturbed counts but performance is measured on the true queue, so Fixed-Time/Random are
flat by construction). Host-side (matplotlib).

  python3 scripts/plot_robustness.py haichau_rush
  python3 scripts/plot_robustness.py                 # all areas with a noise.json

Writes results/presentation/robustness_<area>.png and prints the degradation table.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
CTRLS = ["MaxPressure", "DQN", "FixedTime", "Random"]
STYLE = {"MaxPressure": ("#27ae60", "o-"), "DQN": ("#2980b9", "s-"),
         "FixedTime": ("#7f8c8d", "^--"), "Random": ("#c0392b", "x:")}


def plot(area):
    p = ROOT / "results" / area / "robustness" / "noise.json"
    if not p.exists():
        print("skip (no noise.json):", area); return None
    d = json.loads(p.read_text())
    levels = d["levels"]
    xs = [lv["noise_std"] for lv in levels]
    series = {c: [] for c in CTRLS}
    for lv in levels:
        row = {r["controller"]: r["mean_total_queue"] for r in lv["rows"]}
        for c in CTRLS:
            series[c].append(row.get(c))

    fig, ax = plt.subplots(figsize=(8, 5))
    for c in CTRLS:
        if any(v is not None for v in series[c]):
            col, mk = STYLE[c]
            ax.plot(xs, series[c], mk, color=col, label=c, linewidth=2, markersize=7)
    ax.set_xlabel("Observation noise level (Gaussian std, relative to lane count)")
    ax.set_ylabel("Mean total queue (ground-truth; lower is better)")
    ax.set_title("Robustness to sensor noise — %s" % area)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = ROOT / "results" / "presentation" / ("robustness_%s.png" % area)
    fig.savefig(out, dpi=130); plt.close(fig)

    # degradation table (% vs noise=0), and DQN-vs-MP gap at each level
    base = {c: series[c][0] for c in CTRLS if series[c][0] is not None}
    print("=== %s (ground-truth queue; %% = vs noise 0) ===" % area)
    print("noise  " + "  ".join("%-16s" % c for c in CTRLS))
    for i, x in enumerate(xs):
        cells = []
        for c in CTRLS:
            v = series[c][i]
            if v is None:
                cells.append("%-16s" % "-"); continue
            deg = 100 * (v - base[c]) / base[c] if base.get(c) else 0
            cells.append("%-16s" % ("%.0f (%+.0f%%)" % (v, deg)))
        print("%.2f   " % x + "  ".join(cells))
    print("wrote", out)
    return out


def main():
    areas = sys.argv[1:] or ["haichau_rush", "haichau_calib"]
    for a in areas:
        plot(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
