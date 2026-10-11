#!/usr/bin/env python3
"""Box-and-whisker plot + paired summary for run_danang_baseline_mc.py output.

  python3 scripts/plot_danang_baseline_mc.py [runs.jsonl]
Writes baseline-mc-boxplot.{png,pdf} and summary.json next to the input.
"""

import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = (("normal", "Normal"), ("am_peak", "AM peak"), ("pm_peak", "PM peak"))
CONTROLLERS = (("published_fixed", "Fixed-time\n(published)", "#2a78d6"),
               ("max_pressure", "Max-Pressure", "#eb6834"),
               ("hysteretic_mp", "Hysteretic\nMax-Pressure", "#1baf7a"))
METRIC = "queue_integral_vehicle_hours"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
# Defense-deck signal colours: grey = fixed, blue = pressure, light blue = hysteretic.
DECK_COLORS = ("#8B97A1", "#3A74C9", "#8FB1E3")


def load(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    # Keep only realizations where all three controllers finished (paired).
    by_key = {}
    for row in rows:
        by_key.setdefault((row["scenario"], row["k"]), {})[row["controller"]] = row
    complete = dict((key, v) for key, v in by_key.items()
                    if len(v) == len(CONTROLLERS))
    return complete


def summarize(complete):
    summary = {}
    for scenario, _ in SCENARIOS:
        cases = [v for (s, _), v in complete.items() if s == scenario]
        entry = {"n_realizations": len(cases), "controllers": {}, "paired": {}}
        for cid, _, _ in CONTROLLERS:
            values = np.array([c[cid][METRIC] for c in cases])
            q1, med, q3 = np.percentile(values, [25, 50, 75])
            entry["controllers"][cid] = {
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "median": float(med), "q1": float(q1), "q3": float(q3),
                "p2_5": float(np.percentile(values, 2.5)),
                "p97_5": float(np.percentile(values, 97.5)),
                "min": float(values.min()), "max": float(values.max()),
                # None when the runs did not record collisions (early batches
                # stored null), so a missing count is never reported as zero.
                "collisions_total": (
                    None if any(c[cid].get("collisions") is None for c in cases)
                    else int(sum(c[cid]["collisions"] for c in cases))),
            }
        for a, b in (("published_fixed", "max_pressure"),
                     ("published_fixed", "hysteretic_mp"),
                     ("hysteretic_mp", "max_pressure")):
            wins = sum(1 for c in cases if c[a][METRIC] < c[b][METRIC])
            entry["paired"]["%s_lower_than_%s" % (a, b)] = {
                "wins": wins, "n": len(cases),
                "rate": wins / float(len(cases)) if cases else None}
        summary[scenario] = entry
    return summary


def plot(complete, summary, out_stem, colors=None):
    controllers = [(cid, label, (colors[i] if colors else color))
                   for i, (cid, label, color) in enumerate(CONTROLLERS)]
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2,
                         "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2})
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    rng = np.random.default_rng(0)
    for ax, (scenario, title) in zip(axes, SCENARIOS):
        cases = [v for (s, _), v in complete.items() if s == scenario]
        data = [[c[cid][METRIC] for c in cases] for cid, _, _ in controllers]
        for i, (values, (_, _, color)) in enumerate(zip(data, controllers)):
            x = i + 1 + rng.uniform(-0.18, 0.18, len(values))
            ax.scatter(x, values, s=4, color=color, alpha=0.25,
                       linewidths=0, zorder=1)
        bp = ax.boxplot(data, widths=0.5, whis=1.5, showfliers=False,
                        patch_artist=True, zorder=2)
        for patch, (_, _, color) in zip(bp["boxes"], controllers):
            patch.set(facecolor="none", edgecolor=color, linewidth=1.6)
        for key in ("whiskers", "caps"):
            for i, line in enumerate(bp[key]):
                line.set(color=controllers[i // 2][2], linewidth=1.2)
        for line, (_, _, color) in zip(bp["medians"], controllers):
            line.set(color=INK, linewidth=2)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels([label for _, label, _ in controllers])
        ax.set_title("%s  (n = %d)" % (title, summary[scenario]["n_realizations"]),
                     color=INK, fontsize=10)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel("Queue integral (vehicle-hours)")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (out_stem, ext), dpi=200)
    plt.close(fig)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else
                ROOT / "results/danang_baseline_mc/runs.jsonl")
    complete = load(path)
    summary = summarize(complete)
    (path.parent / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    plot(complete, summary, str(path.parent / "baseline-mc-boxplot"))
    plot(complete, summary, str(path.parent / "baseline-mc-boxplot-deck"), DECK_COLORS)
    for scenario, entry in summary.items():
        print(scenario, "n=%d" % entry["n_realizations"])
        for cid, s in entry["controllers"].items():
            print("  %-16s median %7.1f  IQR [%6.1f, %6.1f]"
                  % (cid, s["median"], s["q1"], s["q3"]))
        for name, p in entry["paired"].items():
            print("  %s: %d/%d" % (name, p["wins"], p["n"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
