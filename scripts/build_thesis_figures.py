#!/usr/bin/env python3
"""Build publication figures that are derived from versioned experiment data."""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "figures"


def camera_profile():
    path = ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv"
    totals = {}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            total = sum(float(row[key]) for key in (
                "car_veh_per_h", "motorcycle_veh_per_h", "truck_veh_per_h",
                "bus_veh_per_h"))
            totals[row["hour_start"]] = totals.get(row["hour_start"], 0) + total
    hours = sorted(totals)
    values = [totals[hour] for hour in hours]
    fig, ax = plt.subplots(figsize=(9, 4.3))
    ax.plot(hours, values, color="#1d3557", marker="o", linewidth=2)
    for hour, label, color in (("08:00", "AM test", "#e76f51"),
                               ("13:00", "Normal test", "#2a9d8f"),
                               ("17:00", "PM test", "#e9c46a")):
        idx = hours.index(hour)
        ax.scatter(hour, values[idx], color=color, s=75, zorder=3,
                   label=f"{label}: {int(values[idx]):,} veh/h")
    ax.set_xlabel("Hour on 1 April 2025")
    ax.set_ylabel("Digitized total over four camera movement lines (veh/h)")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "camera-profile.pdf")
    fig.savefig(OUT / "camera-profile.png", dpi=180)
    plt.close(fig)


def junction_schematic():
    fig, ax = plt.subplots(figsize=(7.4, 6.3))
    ax.set_aspect("equal")
    ax.set_xlim(-4.7, 4.7); ax.set_ylim(-4.7, 4.7); ax.axis("off")
    road = "#59636e"; lane = "#f4f1de"
    ax.fill_between([-4.7, 4.7], -1.25, 1.25, color=road)
    ax.fill_betweenx([-4.7, 4.7], -1.25, 1.25, color=road)
    for offset in (-0.42, 0.42):
        ax.plot([-4.7, -1.3], [offset, offset], color=lane, ls="--", lw=1)
        ax.plot([1.3, 4.7], [offset, offset], color=lane, ls="--", lw=1)
        ax.plot([offset, offset], [-4.7, -1.3], color=lane, ls="--", lw=1)
        ax.plot([offset, offset], [1.3, 4.7], color=lane, ls="--", lw=1)
    labels = [(0, 4.35, "NW approach\n2/9 Street\n3 lanes"),
              (4.05, 0, "NE approach\nLe Thanh Nghi\n2 lanes"),
              (0, -4.35, "SE approach\nCMT8\n3 lanes"),
              (-4.05, 0, "SW approach\nHoa Xuan\n2 lanes")]
    for x, y, label in labels:
        ax.text(x, y, label, ha="center", va="center", fontsize=10,
                bbox=dict(boxstyle="round,pad=.35", fc="white", ec="#1d3557"))
    arrows = [((-3.3, -0.65), (3.3, -0.65)),
              ((-3.3, 0.65), (-0.65, 3.3)),
              ((0.65, 3.3), (0.65, -3.3)),
              ((-0.65, 3.3), (3.3, 0.65))]
    for start, end in arrows:
        ax.annotate("", end, start, arrowprops=dict(arrowstyle="->", lw=3,
                    color="#e76f51", connectionstyle="arc3,rad=.08"))
    ax.text(0, 0, "Isolated audited\nsignalized junction", ha="center", va="center",
            color="white", weight="bold", fontsize=11)
    ax.text(0, -4.8, "Four movement lines observed by two cameras; 300 m modelled approaches",
            ha="center", va="top", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "junction-schematic.pdf", bbox_inches="tight")
    fig.savefig(OUT / "junction-schematic.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    camera_profile()
    junction_schematic()
    print(OUT)


if __name__ == "__main__":
    main()
