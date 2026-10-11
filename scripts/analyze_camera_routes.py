#!/usr/bin/env python3
"""Turn line crossings from count_camera_vehicles.py into routes and a Markov chain.

Each line bounds one or two junctions ("legs" in the camera config). Consecutive
crossings of one track give a movement at a junction: entering on leg X, then
leaving on leg Y. Those movements estimate turning probabilities P(Y | X) per
junction. Chaining the junctions through the internal link is the Markov
assumption, and gives network entry->exit probabilities without needing a track
to survive both junctions.

Volumes always come from the inbound line counts; completed routes only supply
proportions, because many tracks fragment before they leave the junction.

    python3 scripts/analyze_camera_routes.py results/camera_counts/caurong_20260711_1716 \
        [--video data/camera/caurong_20260711_pm_peak.mp4]
"""

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch

CATEGORIES = ("motorcycle", "car", "truck", "bus")
LABELS = {"motorcycle": "Motorcycle", "car": "Car / van", "truck": "Truck", "bus": "Bus"}
COLORS = {"motorcycle": "#2a78d6", "car": "#eb6834", "truck": "#1baf7a", "bus": "#eda100"}
INK, MUTED = "#0b0b0b", "#52514e"


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run")
    ap.add_argument("--video", help="source video, for the route-check contact sheet")
    ap.add_argument("--jitter-s", type=float, default=3.0,
                    help="drop a same-line reversal faster than this (box jitter)")
    ap.add_argument("--max-gap-s", type=float, default=180.0,
                    help="longest believable enter->exit time at one junction")
    ap.add_argument("--only", choices=CATEGORIES,
                    help="analyse one vehicle class; outputs go to <run>/only_<class>/")
    ap.add_argument("--sample", type=int, default=16, help="routes on the check sheet")
    return ap.parse_args()


def load(run):
    meta = json.loads((run / "meta.json").read_text())
    cfg = json.loads(Path(meta["config"]).read_text())
    with (run / "crossings.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["t_s"] = float(r["t_s"])
        r["track_id"] = int(r["track_id"])
    return meta, cfg, rows


def roles(line, direction):
    """[(junction, 'enter'|'exit')] for one crossing."""
    return [(j, "enter" if direction == d else "exit") for j, d in line["legs"].items()]


def main():
    args = parse_args()
    run = Path(args.run)
    meta, cfg, rows = load(run)
    frame = run / "lines_last_frame.jpg"
    if args.only:
        rows = [r for r in rows if r["category"] == args.only]
        run = run / f"only_{args.only}"
        run.mkdir(exist_ok=True)
    lines = {ln["name"]: ln for ln in cfg["lines"]}
    junctions = list(cfg["junctions"])
    legs = {j: [n for n, ln in lines.items() if j in ln["legs"]] for j in junctions}
    minutes = meta["duration_s"] / 60
    quality = Counter()

    # --- per-track sequences, cleaned -------------------------------------------------
    tracks = defaultdict(list)
    for r in rows:
        tracks[r["track_id"]].append(r)
    for seq in tracks.values():
        seq.sort(key=lambda r: r["t_s"])
        i = 0
        while i < len(seq) - 1:      # A then reverse-A within jitter-s: neither is real
            a, b = seq[i], seq[i + 1]
            if a["line"] == b["line"] and b["t_s"] - a["t_s"] < args.jitter_s:
                quality["jitter_pairs_dropped"] += 1
                del seq[i:i + 2]
                i = max(i - 1, 0)
            else:
                i += 1
    crossings = [r for seq in tracks.values() for r in seq]
    quality["crossings_raw"] = len(rows)
    quality["crossings_clean"] = len(crossings)

    # --- movements: enter J on X, next crossing exits J on Y --------------------------
    movements = []
    enter_outcome = Counter()          # (J, leg, class, outcome)
    for seq in tracks.values():
        for i, a in enumerate(seq):
            for j, role in roles(lines[a["line"]], a["direction"]):
                if role != "enter":
                    continue
                key = (j, a["line"], a["category"])
                if i + 1 == len(seq):
                    enter_outcome[key + ("lost",)] += 1
                    continue
                b = seq[i + 1]
                if (j, "exit") not in roles(lines[b["line"]], b["direction"]):
                    enter_outcome[key + ("inconsistent",)] += 1
                    continue
                if b["t_s"] - a["t_s"] > args.max_gap_s:
                    enter_outcome[key + ("too_slow",)] += 1
                    continue
                enter_outcome[key + ("completed",)] += 1
                movements.append({"junction": j, "from": a["line"], "to": b["line"],
                                  "category": a["category"], "track_id": a["track_id"],
                                  "t_in": a["t_s"], "t_out": b["t_s"],
                                  "clock_in": a.get("clock", ""), "clock_out": b.get("clock", "")})

    # --- line totals (volumes) --------------------------------------------------------
    vol = Counter()                    # (line, direction, class)
    for r in crossings:
        vol[(r["line"], r["direction"], r["category"])] += 1

    def inbound(j, leg, cat=None):
        d = lines[leg]["legs"][j]
        return sum(vol[(leg, d, c)] for c in CATEGORIES if cat in (None, c))

    def outbound(j, leg, cat=None):
        d = [x for x in (lines[leg]["pos"], lines[leg]["neg"]) if x != lines[leg]["legs"][j]][0]
        return sum(vol[(leg, d, c)] for c in CATEGORIES if cat in (None, c))

    # --- turning matrices and probabilities ------------------------------------------
    turn = {j: Counter() for j in junctions}
    for m in movements:
        turn[m["junction"]][(m["from"], m["to"])] += 1
    prob = {}
    for j in junctions:
        for x in legs[j]:
            n = sum(turn[j][(x, y)] for y in legs[j])
            for y in legs[j]:
                prob[(j, x, y)] = turn[j][(x, y)] / n if n else float("nan")

    # --- network chain: absorbing Markov chain over (junction, entry leg) -------------
    internal = {n: ln for n, ln in lines.items() if not ln.get("cordon", True)}
    states = [(j, x) for j in junctions for x in legs[j]]
    exits = [n for n, ln in lines.items() if ln.get("cordon", True)]
    si = {s: k for k, s in enumerate(states)}
    Q = np.zeros((len(states), len(states)))
    R = np.zeros((len(states), len(exits)))
    for (j, x) in states:
        for y in legs[j]:
            p = prob[(j, x, y)]
            if not p == p:             # nan: no completed routes from this leg
                continue
            if y in internal:          # leaving j on the internal link enters the other junction
                for j2 in internal[y]["legs"]:
                    if j2 != j:
                        Q[si[(j, x)], si[(j2, y)]] += p
            else:
                R[si[(j, x)], exits.index(y)] += p
    B = np.linalg.solve(np.eye(len(states)) - Q, R)
    entries = [(j, x) for j in junctions for x in legs[j] if x not in internal]
    od = {(x, y): B[si[(j, x)], exits.index(y)] for j, x in entries for y in exits}

    # --- write tables -----------------------------------------------------------------
    with (run / "entries_exits.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "junction", "flow", *CATEGORIES, "total", "veh_per_h"])
        for j in junctions:
            for x in legs[j]:
                for flow, fn in (("in", inbound), ("out", outbound)):
                    row = [fn(j, x, c) for c in CATEGORIES]
                    w.writerow([x, j, flow, *row, sum(row), round(sum(row) * 60 / minutes)])

    with (run / "turning_movements.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["junction", "from", "to", "completed_routes", *[f"routes_{c}" for c in CATEGORIES],
                    "p_to_given_from", "est_volume", "est_veh_per_h"])
        by_cat = Counter((m["junction"], m["from"], m["to"], m["category"]) for m in movements)
        for j in junctions:
            for x in legs[j]:
                for y in legs[j]:
                    p = prob[(j, x, y)]
                    est = inbound(j, x) * p if p == p else 0
                    w.writerow([j, x, y, turn[j][(x, y)],
                                *[by_cat[(j, x, y, c)] for c in CATEGORIES],
                                round(p, 4) if p == p else "", round(est, 1),
                                round(est * 60 / minutes)])

    with (run / "network_od.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry", "exit", "p_exit_given_entry", "est_volume", "est_veh_per_h"])
        for j, x in entries:
            for y in exits:
                p = od[(x, y)]
                w.writerow([x, y, round(p, 4), round(inbound(j, x) * p, 1),
                            round(inbound(j, x) * p * 60 / minutes)])

    with (run / "route_completion.csv").open("w", newline="") as f:
        w = csv.writer(f)
        outcomes = ("completed", "lost", "inconsistent", "too_slow")
        w.writerow(["junction", "entry_leg", "category", *outcomes, "completion_rate"])
        for j in junctions:
            for x in legs[j]:
                for c in CATEGORIES:
                    n = [enter_outcome[(j, x, c, o)] for o in outcomes]
                    if sum(n):
                        w.writerow([j, x, c, *n, round(n[0] / sum(n), 3)])

    with (run / "routes.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(movements[0]) if movements else ["junction"])
        w.writeheader()
        w.writerows(movements)

    # --- summary ----------------------------------------------------------------------
    entering = {c: sum(inbound(j, x, c) for j, x in entries) for c in CATEGORIES}
    leaving = {c: sum(outbound(j, x, c) for j, x in entries) for c in CATEGORIES}
    conservation = {j: {"in": sum(inbound(j, x) for x in legs[j]),
                        "out": sum(outbound(j, x) for x in legs[j])} for j in junctions}
    all_enter = sum(v for k, v in enter_outcome.items())
    summary = {
        "window": f"{meta['start_clock']} + {minutes:.1f} min",
        "vehicles_entering_cordon": {**entering, "total": sum(entering.values())},
        "vehicles_leaving_cordon": {**leaving, "total": sum(leaving.values())},
        "entering_veh_per_h": round(sum(entering.values()) * 60 / minutes),
        "junction_in_out": conservation,
        "completed_routes": len(movements),
        "route_completion_rate": round(len(movements) / all_enter, 3) if all_enter else None,
        "enter_outcomes": {o: sum(v for k, v in enter_outcome.items() if k[3] == o)
                           for o in ("completed", "lost", "inconsistent", "too_slow")},
        "quality": dict(quality),
        "cordon_lines": exits,
        "far_field_lines": [n for n, ln in lines.items() if ln.get("far_field")],
    }
    (run / "routes_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    plot_chain(run, frame, meta, cfg, lines, junctions, legs, turn, prob, inbound, args.only)
    plot_matrices(run, junctions, legs, turn, prob, lines)
    if args.video and movements and not args.only:
        check_sheet(run, args.video, movements, lines, args.sample)


def mid(line):
    return np.array([(line["a"][0] + line["b"][0]) / 2, (line["a"][1] + line["b"][1]) / 2])


def plot_chain(run, frame, meta, cfg, lines, junctions, legs, turn, prob, inbound, only):
    """Turning probabilities drawn on the camera frame, one panel per junction."""
    img = plt.imread(frame)
    fig, axes = plt.subplots(1, len(junctions), figsize=(7 * len(junctions), 4.6))
    for ax, j in zip(np.atleast_1d(axes), junctions):
        ax.imshow(img, alpha=0.55)
        centre = np.mean([mid(lines[x]) for x in legs[j]], axis=0)
        for x in legs[j]:
            n_from = sum(turn[j][(x, y)] for y in legs[j])
            ax.scatter(*mid(lines[x]), s=60, color=INK, zorder=4)
            ax.annotate(f"{lines[x]['label']}\nin {inbound(j, x):,} | routes {n_from}",
                        mid(lines[x]), xytext=(6, 6), textcoords="offset points", fontsize=7,
                        color=INK, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none",
                                             alpha=0.85), zorder=5)
            for y in legs[j]:
                p = prob[(j, x, y)]
                if not p == p or p < 0.05 or x == y:
                    continue
                a, b = mid(lines[x]), mid(lines[y])
                # bend each arrow through the junction centre so opposite movements separate
                d, e = b - a, centre - a
                rad = 0.25 if d[0] * e[1] - d[1] * e[0] > 0 else -0.25
                ax.add_patch(FancyArrowPatch(a, b, connectionstyle=f"arc3,rad={rad}",
                                             arrowstyle="-|>", mutation_scale=10,
                                             linewidth=0.8 + 6 * p, color="#2a78d6", alpha=0.85,
                                             zorder=3))
                lab = a + (b - a) * 0.5 + np.array([-(b - a)[1], (b - a)[0]]) * rad * 0.5
                ax.text(*lab, f"{p:.0%}", fontsize=7, color=INK, ha="center", va="center",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9),
                        zorder=6)
        ax.set_title(f"{j}: {cfg['junctions'][j]} - P(exit leg | entry leg)",
                     loc="left", fontsize=9, color=INK)
        ax.set_axis_off()
    who = LABELS[only] if only else "All vehicles"
    fig.suptitle(f"{who}: Markov turning probabilities from tracked routes, {meta['start_clock']} "
                 f"+{meta['duration_s'] / 60:.0f} min (arrows < 5% hidden)",
                 x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(run / f"markov_chain.{ext}", dpi=200)
    plt.close(fig)


def plot_matrices(run, junctions, legs, turn, prob, lines):
    fig, axes = plt.subplots(1, len(junctions), figsize=(5.2 * len(junctions), 4.4))
    for ax, j in zip(np.atleast_1d(axes), junctions):
        L = legs[j]
        P = np.array([[prob[(j, x, y)] for y in L] for x in L])
        ax.imshow(np.nan_to_num(P), cmap="Blues", vmin=0, vmax=1)
        for r, x in enumerate(L):
            for c, y in enumerate(L):
                p = P[r, c]
                txt = "-" if not p == p else f"{p:.0%}\n({turn[j][(x, y)]})"
                ax.text(c, r, txt, ha="center", va="center", fontsize=7.5,
                        color="white" if p == p and p > 0.55 else INK)
        names = [lines[x]["label"] for x in L]
        ax.set_xticks(range(len(L)), names, rotation=30, ha="right", fontsize=7.5)
        ax.set_yticks(range(len(L)), names, fontsize=7.5)
        ax.set_xlabel("exit leg", color=MUTED)
        ax.set_ylabel("entry leg", color=MUTED)
        ax.set_title(f"{j}: P(exit | entry), (completed routes)", loc="left", fontsize=9)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(run / f"turning_matrix.{ext}", dpi=200)
    plt.close(fig)


def check_sheet(run, video, movements, lines, n):
    """Entry and exit crops of random routes, to judge by eye whether each is one vehicle."""
    src = run / "annotated.mp4"
    cap = cv2.VideoCapture(str(src if src.exists() else video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    random.seed(0)
    pick = random.sample(movements, min(n, len(movements)))
    tiles = []
    for m in pick:
        pair = []
        for line, t in ((m["from"], m["t_in"]), (m["to"], m["t_out"])):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps)))
            ok, frame = cap.read()
            cx, cy = mid(lines[line]).astype(int)
            x0, y0 = max(cx - 110, 0), max(cy - 70, 0)
            crop = frame[y0:y0 + 140, x0:x0 + 220] if ok else np.zeros((140, 220, 3), np.uint8)
            crop = cv2.resize(crop, (330, 210))
            pair.append(crop)
        tile = np.hstack(pair)
        cv2.putText(tile, f"id {m['track_id']} {m['category']} {m['junction']}: "
                          f"{m['from']} -> {m['to']}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (0, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    while len(tiles) % 2:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]
    cv2.imwrite(str(run / "route_check_sheet.jpg"), np.vstack(rows))


if __name__ == "__main__":
    main()
