#!/usr/bin/env python3
"""Plot case-level residual-vs-fixed improvements from a summary JSON."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    data = json.loads(Path(args.summary).read_text())
    rows = data["rows"]
    colors = {"normal": "#7f8c8d", "am_peak": "#e67e22", "pm_peak": "#2980b9"}
    labels = [row["case_id"].replace("test_", "") for row in rows]
    values = [row["improvement_pct"] for row in rows]
    fig, ax = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.bar(range(len(rows)), values,
           color=[colors[row["regime"]] for row in rows])
    ax.set_xticks(range(len(rows)), labels, rotation=35, ha="right")
    ax.set_ylabel("Queue integral change vs fixed-time (%)")
    ax.set_title("Hai Chau 53-signal network: residual DDQN vs fixed-time")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=color, label=label)
                       for label, color in (("Normal", colors["normal"]),
                                             ("AM peak", colors["am_peak"]),
                                             ("PM peak", colors["pm_peak"]))],
              loc="upper left", frameon=False)
    fig.savefig(args.output, dpi=180)
    print(json.dumps({"output": args.output, "cases": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
