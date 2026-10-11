#!/usr/bin/env python3
"""Draw the camera-derived Markov chain on an OpenStreetMap base map.

Turning probabilities P(exit leg | entry leg) per junction, with each leg's
state placed where that street leaves the junction; arrows bend through the
junction they belong to (J1 blue, J2 orange) and their width follows P.

Base map: datasets/camera_caurong/ (OSM extract, ODbL). Leg placement:
the "map" block of the camera config.

    python3 scripts/plot_camera_markov_map.py \
        results/camera_counts/caurong_20260711_1716/only_car [--lang vi] [--bare]
"""

import argparse
import csv
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from matplotlib.patches import FancyArrowPatch, PathPatch
from matplotlib.path import Path as MPath
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "datasets/camera_caurong"
CRS = "EPSG:32649"                       # UTM 49N
INK, MUTED = "#0b0b0b", "#52514e"
JCOL = {"J1": "#2a78d6", "J2": "#eb6834"}
ROAD_W = {"primary": 5, "primary_link": 3, "secondary": 4, "tertiary": 3, "residential": 1.4}


def to_xy(lat, lon):
    return np.array(gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(CRS)[0].coords[0])


def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def base_map(ax, bbox):
    west, south, east, north = bbox
    G = ox.project_graph(ox.load_graphml(BASE / "caurong_drive.graphml"), to_crs=CRS)
    edges = ox.graph_to_gdfs(G, nodes=False)
    water = gpd.read_file(BASE / "caurong_water.geojson").to_crs(CRS)
    water[water.geom_type.isin(["Polygon", "MultiPolygon"])].plot(ax=ax, color="#d6e6f2", zorder=0)
    bpath = BASE / "caurong_buildings.geojson"
    if bpath.exists():
        b = gpd.read_file(bpath).to_crs(CRS)
        b[b.geom_type.isin(["Polygon", "MultiPolygon"])].plot(ax=ax, color="#ebebe8", zorder=1)
    hw = edges["highway"].astype(str)
    for cls, w in ROAD_W.items():
        sub = edges[hw.str.contains(cls)]
        sub.plot(ax=ax, color="#c9c9c4", linewidth=w + 1.2, zorder=2)
        sub.plot(ax=ax, color="white", linewidth=w, zorder=3)
    lo, hi = to_xy(south, west), to_xy(north, east)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor("#c9c9c4")


def bezier(ax, a, ctrl, b, width, color, z=5):
    verts = [a, ctrl, b]
    path = MPath(verts, [MPath.MOVETO, MPath.CURVE3, MPath.CURVE3])
    ax.add_patch(PathPatch(path, fc="none", ec="white", lw=width + 2.5, zorder=z, capstyle="round"))
    ax.add_patch(PathPatch(path, fc="none", ec=color, lw=width, zorder=z + 0.1, capstyle="round",
                           alpha=0.9))
    # arrowhead along the last part of the curve
    t0, t1 = 0.86, 0.99
    p0 = (1 - t0) ** 2 * a + 2 * (1 - t0) * t0 * ctrl + t0 ** 2 * b
    p1 = (1 - t1) ** 2 * a + 2 * (1 - t1) * t1 * ctrl + t1 ** 2 * b
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=9 + 2.2 * width,
                                 color=color, lw=0, zorder=z + 0.2))


def label(ax, xy, text, size=7.5, **kw):
    return ax.text(*xy, text, fontsize=size, color=INK, ha="center", va="center", zorder=9,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.92), **kw)


TEXT = {
    "en": dict(link="link J1-J2", exit_only="exit only", n_in="{n} in / 15 min",
               west="Nguyễn Văn Linh (west)", north="Bạch Đằng (north)", bridge="Cầu Rồng (Dragon Bridge)"),
    "vi": dict(link="đoạn nối J1-J2", exit_only="chỉ có xe ra", n_in="{n} xe vào / 15 phút",
               west="Nguyễn Văn Linh (phía tây)", north="Bạch Đằng (phía bắc)", bridge="Cầu Rồng"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", help="analysis dir, e.g. <run>/only_car")
    ap.add_argument("--lang", choices=TEXT, default="en")
    ap.add_argument("--bare", action="store_true", help="no titles (for slides that carry their own)")
    args = ap.parse_args()
    T = TEXT[args.lang]
    run = Path(args.run)
    top = run if (run / "meta.json").exists() else run.parent
    meta = json.loads((top / "meta.json").read_text())
    cfg = json.loads(Path(meta["config"]).read_text())
    m = cfg["map"]
    lines = {ln["name"]: ln for ln in cfg["lines"]}
    anchor = {k: to_xy(*v["anchor"]) for k, v in m["legs"].items()}
    jc = {j: to_xy(*v) for j, v in m["junctions"].items()}
    street = {k: v["street"] for k, v in m["legs"].items()}
    street.update(boulevard_south=T["west"], northwest_road=T["north"], bridge=T["bridge"])
    turns = read(run / "turning_movements.csv")
    ee = read(run / "entries_exits.csv")
    inflow = {(r["junction"], r["line"]): int(r["total"]) for r in ee if r["flow"] == "in"}
    who = "cars and vans" if run.name == "only_car" else "all vehicles"

    # the slide version is a wider, shorter crop with larger text so it stays legible
    fs = 9.5 if args.bare else 7.5
    fig, ax = plt.subplots(figsize=(9, 5.2) if args.bare else (11, 6.4))
    base_map(ax, m["slide_bbox"] if args.bare else m["bbox"])
    gap = 22 if args.bare else 14          # metres between a leg dot and its text
    # place text one item at a time and keep each item's real on-screen box, so later
    # % labels can be moved along their arrow until they overlap nothing
    renderer = fig.canvas.get_renderer()
    boxes = []

    def place(cands, text, **kw):
        for q in cands:
            t = label(ax, q, text, size=fs, **kw)
            bb = t.get_window_extent(renderer).expanded(1.15, 1.35)
            if not any(bb.overlaps(o) for o in boxes) or q is cands[-1]:
                boxes.append(bb)
                return
            t.remove()

    for leg, xy in anchor.items():
        ln = lines[leg]
        n_in = sum(v for (j, l), v in inflow.items() if l == leg)
        if not ln.get("cordon", True):
            txt = "" if args.bare else T["link"]
        elif n_in < 10:
            txt = f"{street[leg]}\n{T['exit_only']}"
        else:
            txt = f"{street[leg]}\n" + T["n_in"].format(n=n_in)
        ax.scatter(*xy, s=80, color=INK, zorder=8, edgecolor="white", linewidth=1.2)
        if txt:
            below = leg in ("riverside_east", "southeast_road")
            off = np.array([0, -(gap - 2) if below else gap - 2])
            off = off + np.array({"boulevard_south": [-25, 0], "west_road": [-30, 0],
                                  "northwest_road": [25, 0]}.get(leg, [0, 0]))
            place([xy + off], txt)
    for j, xy in jc.items():
        ax.scatter(*xy, s=90, facecolor="white", edgecolor=JCOL[j], linewidth=2.5, zorder=8)
        t = ax.text(*(xy + np.array([-12, 12])), j, fontsize=fs + 0.5, fontweight="bold",
                    color=JCOL[j], ha="center", va="center", zorder=10,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=JCOL[j], lw=1))
        boxes.append(t.get_window_extent(renderer).expanded(1.3, 1.3))

    drawn = [r for r in turns if float(r["p_to_given_from"] or 0) >= 0.05 and r["from"] != r["to"]]
    for r in sorted(drawn, key=lambda r: -float(r["p_to_given_from"])):
        p = float(r["p_to_given_from"])
        j, a, b = r["junction"], r["from"], r["to"]
        pa, pb, c = anchor[a], anchor[b], jc[j]
        # keep right, like a two-way road, so opposite movements on one axis separate
        d = (pb - pa) / np.linalg.norm(pb - pa)
        right = np.array([d[1], -d[0]]) * 5.0
        pa, pb, c = pa + right, pb + right, c + right
        bezier(ax, pa, c, pb, 0.8 + 6 * p, JCOL[j])
        # first point along the curve (entry side first) that is clear of earlier text
        start = 0.3 if lines[a].get("cordon", True) else 0.7
        ts = [start + dt for dt in (0, 0.08, -0.08, 0.16, -0.16, 0.24, -0.24, 0.32, 0.4)]
        pts = [(1 - t) ** 2 * pa + 2 * (1 - t) * t * c + t ** 2 * pb + right * 1.6
               for t in ts if 0.06 <= t <= 0.94]
        place(pts, f"{p:.0%}")
    if not args.bare:
        ax.set_title(f"Markov chain of {who}: P(exit leg | entry leg) at each junction "
                     f"(arrows < 5% hidden)", loc="left", fontsize=10.5, color=INK)
        fig.suptitle(f"Tay Cau Rong, Da Nang - YOLO + ByteTrack routes from a public camera, "
                     f"{cfg.get('recording_date', '')} {meta['start_clock']} "
                     f"+{meta['duration_s'] / 60:.0f} min. Base map © OpenStreetMap contributors",
                     x=0.01, ha="left", fontsize=9.5, color=MUTED)
    fig.tight_layout()
    name = "markov_map" + ("" if args.lang == "en" else f"_{args.lang}") + ("_bare" if args.bare else "")
    for ext in ("png", "pdf"):
        fig.savefig(run / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    print("wrote", run / f"{name}.png")


if __name__ == "__main__":
    main()
