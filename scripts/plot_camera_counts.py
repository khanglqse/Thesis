#!/usr/bin/env python3
"""Report figure for a scripts/count_camera_vehicles.py run.

Panels: (a) camera frame with the count lines and per-line totals, (b) vehicles per
line and direction stacked by class, (c) vehicles per minute stacked by class.

    python3 scripts/plot_camera_counts.py results/camera_counts/caurong_20260711_1716
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

CATEGORIES = ("motorcycle", "car", "truck", "bus")
LABELS = {"motorcycle": "Motorcycle", "car": "Car / van", "truck": "Truck", "bus": "Bus"}
COLORS = {"motorcycle": "#2a78d6", "car": "#eb6834", "truck": "#1baf7a", "bus": "#eda100"}
INK, MUTED = "#0b0b0b", "#52514e"


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def stacked_bars(ax, labels, rows, horizontal=False):
    base = np.zeros(len(rows))
    for cat in CATEGORIES:
        vals = np.array([float(r[cat]) for r in rows])
        kw = dict(color=COLORS[cat], label=LABELS[cat], edgecolor="white", linewidth=1)
        if horizontal:
            ax.barh(labels, vals, left=base, height=0.7, **kw)
        else:
            ax.bar(labels, vals, bottom=base, width=0.8, **kw)
        base += vals
    return base


def main():
    run = Path(sys.argv[1])
    meta = json.loads((run / "meta.json").read_text())
    by_line = read_csv(run / "counts_by_line.csv")
    per_min = read_csv(run / "per_minute.csv")
    labels = {ln["name"]: ln["label"] for ln in meta["lines"]}
    date = json.loads(Path(meta["config"]).read_text()).get("recording_date", "")

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED})
    fig = plt.figure(figsize=(12, 8.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], width_ratios=[1.25, 1])

    # (a) frame with lines
    ax = fig.add_subplot(gs[0, :])
    img = plt.imread(run / "lines_last_frame.jpg")
    ax.imshow(img)
    totals = {}
    for r in by_line:
        totals[r["line"]] = totals.get(r["line"], 0) + int(r["total_veh"])
    for ln in meta["lines"]:
        (ax_, ay), (bx, by) = ln["a"], ln["b"]
        ax.plot([ax_, bx], [ay, by], color="white", linewidth=2.5)
        ax.plot([ax_, bx], [ay, by], color=INK, linewidth=1, linestyle="--")
        ax.annotate(f"{labels[ln['name']]}\n{totals.get(ln['name'], 0):,} veh",
                    ((ax_ + bx) / 2, (ay + by) / 2), xytext=(6, -6), textcoords="offset points",
                    fontsize=8, color=INK, va="top",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85))
    ax.set_axis_off()
    ax.set_title("(a) Count lines on the Tay Cau Rong camera view", loc="left", color=INK)

    # (b) per line & direction
    ax = fig.add_subplot(gs[1, 0])
    rows = [r for r in by_line if int(r["total_veh"]) > 0] or by_line
    names = [f"{labels[r['line']]} - {r['direction']}" for r in rows]
    tot = stacked_bars(ax, names, rows, horizontal=True)
    for y, v, r in zip(range(len(rows)), tot, rows):
        ax.text(v, y, f"  {int(v):,}  ({int(r['veh_per_h']):,} veh/h)", va="center",
                fontsize=7.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, tot.max() * 1.45 if tot.max() else 1)
    ax.set_xlabel(f"Vehicles counted in {meta['duration_s'] / 60:.0f} min")
    ax.grid(axis="x", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("(b) Crossings by line and direction", loc="left", color=INK)

    # (c) per minute
    ax = fig.add_subplot(gs[1, 1])
    xs = [r["clock_start"] or r["minute"] for r in per_min]
    stacked_bars(ax, xs, per_min)
    ax.set_ylabel("Vehicles per minute (all lines)")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("(c) Vehicles per minute", loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")

    t = meta["crossings_by_class"]
    fig.suptitle(
        f"YOLO (VisDrone) + ByteTrack line counts, {meta['start_clock']} +{meta['duration_s'] / 60:.0f} min, "
        f"{date} - " + ", ".join(f"{LABELS[c]} {t[c]:,}" for c in CATEGORIES),
        x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(run / f"camera_counts.{ext}", dpi=200)
    print("wrote", run / "camera_counts.png")


if __name__ == "__main__":
    main()
