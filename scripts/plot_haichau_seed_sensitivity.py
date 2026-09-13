#!/usr/bin/env python3
"""Plot aggregate and regime effects for completed learned seeds."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = json.loads(Path(args.summary).read_text())
    seeds = data["seed_results"]
    labels = ["seed %d" % item["learning_seed"] for item in seeds]
    regimes = ("am_peak", "pm_peak")
    colors = {"am_peak": "#e67e22", "pm_peak": "#2980b9"}
    x = list(range(len(seeds)))
    width = 0.32
    fig, ax = plt.subplots(figsize=(9.4, 5.4), dpi=150)
    for index, regime in enumerate(regimes):
        values = [item["by_regime"][regime] for item in seeds]
        offsets = [value + (index - 0.5) * width for value in x]
        bars = ax.bar(offsets, values, width, label=regime.replace("_", " ").title(),
                      color=colors[regime])
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    totals = [item["aggregate_improvement_pct"] for item in seeds]
    for index, value in enumerate(totals):
        ax.scatter([index], [value], color="#263238", marker="D", s=35,
                   zorder=4, label="aggregate" if index == 0 else None)
        ax.annotate("%.1f%%" % value, (index, value), xytext=(0, 9),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.axhline(0, color="#222", linewidth=0.8)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Queue integral reduction vs fixed-time (%)")
    ax.set_title("Hai Chau 53-signal network: learning-seed sensitivity")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(args.output, bbox_inches="tight")
    print(json.dumps({"output": args.output, "seeds": len(seeds)}, sort_keys=True))


if __name__ == "__main__":
    main()
