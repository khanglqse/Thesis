#!/usr/bin/env python3
"""Export a trained SharedDQN + one intersection's structure to JSON for the
browser sandbox demo. Host-only (Python 3.13); imports 3.6-safe src modules.

  PYTHONPATH=src python scripts/export_sandbox_model.py --area haichau_rush
  PYTHONPATH=src python scripts/export_sandbox_model.py --area haichau_rush --list
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.agents.dqn import SharedDQN

ROOT = Path(__file__).resolve().parent.parent

# Per-scenario encoder config (kept in sync with the exp_*.sh training overrides).
SCENARIOS = {
    "haichau_rush":  {"count_norm": 5.0,  "state_mode": "basic", "fixed_green": 25},
    "haichau_calib": {"count_norm": 10.0, "state_mode": "basic", "fixed_green": 25},
    "haichau_peak":  {"count_norm": 40.0, "state_mode": "basic", "fixed_green": 25},
    "haichau":       {"count_norm": 40.0, "state_mode": "basic", "fixed_green": 25},
}


def load_bundle(area, ckpt, count_norm, state_mode):
    rn = RoadNet.load(str(ROOT / "data" / "danang" / "roadnet_{}.json".format(area)))
    enc = ObservationEncoder(rn, count_norm=count_norm, state_mode=state_mode)
    npz = np.load(str(ROOT / ckpt) if not Path(ckpt).is_absolute() else ckpt)
    hidden = npz["W1"].shape[1]
    net = SharedDQN(enc.obs_dim, enc.max_green, hidden=hidden)
    net.load(str(ROOT / ckpt) if not Path(ckpt).is_absolute() else ckpt)
    weights = {k: npz[k].astype(np.float32).tolist() for k in npz.files}
    return rn, enc, net, weights


def forward_mirror(weights, obs):
    """NumPy re-impl of the JS forward pass; source of truth for the parity test."""
    x = np.asarray(obs, dtype=np.float32)
    a1 = np.maximum(x.dot(np.asarray(weights["W1"], np.float32)) + np.asarray(weights["b1"], np.float32), 0.0)
    a2 = np.maximum(a1.dot(np.asarray(weights["W2"], np.float32)) + np.asarray(weights["b2"], np.float32), 0.0)
    if "Wv" in weights:  # dueling
        v = a2.dot(np.asarray(weights["Wv"], np.float32)) + np.asarray(weights["bv"], np.float32)
        adv = a2.dot(np.asarray(weights["Wa"], np.float32)) + np.asarray(weights["ba"], np.float32)
        return v + (adv - adv.mean())
    return a2.dot(np.asarray(weights["W3"], np.float32)) + np.asarray(weights["b3"], np.float32)


def parity_samples(net, obs_dim, n_actions, n, seed):
    rng = np.random.RandomState(seed)
    out = []
    full_mask = np.ones(n_actions, dtype=bool)
    for _ in range(n):
        obs = (rng.rand(obs_dim) * 3.0).astype(np.float32)
        q = net.q_values(obs)[0]
        out.append({"obs": obs.tolist(), "q": q.tolist(),
                    "greedy": int(net.greedy_action(obs, full_mask))})
    return out


_COMPASS_VI = ["Đông", "Đông Bắc", "Bắc", "Tây Bắc", "Tây", "Tây Nam", "Nam", "Đông Nam"]


def bearing_deg(cx, cy, px, py):
    return (math.degrees(math.atan2(py - cy, px - cx)) + 360.0) % 360.0


def compass_vi(bearing):
    return _COMPASS_VI[int((bearing + 22.5) // 45) % 8]


def _incoming_road_ids(rn, inter_id):
    return [r for r in rn._by_id[inter_id]["roads"]
            if rn._road_by_id[r]["endIntersection"] == inter_id]


def score_intersection(rn, inter_id):
    greens = rn.green_phases(inter_id)
    lp = rn._lightphases(inter_id)
    n_links = len(rn._by_id[inter_id].get("roadLinks", []))
    # a "clean" green phase serves a strict subset of roadLinks (not all-green)
    clean = sum(1 for g in greens if 0 < len(lp[g].get("availableRoadLinks", [])) < n_links)
    n_in = len(_incoming_road_ids(rn, inter_id))
    # a node with NO all-green phase must always outrank one that has any,
    # regardless of in-approach count or raw phase count (Max-Pressure would
    # otherwise camp on the all-green phase and the sandbox demo degenerates).
    no_allgreen = 1 if (greens and clean == len(greens)) else 0
    return (no_allgreen, min(n_in, 4), clean, len(greens))


def pick_intersection(rn):
    return max(rn.signalized_ids(), key=lambda i: score_intersection(rn, i))


def _far_point(rn, road_id, cx, cy):
    pts = rn._road_by_id[road_id]["points"]
    return max(pts, key=lambda p: (p["x"] - cx) ** 2 + (p["y"] - cy) ** 2)


def intersection_block(rn, enc, inter_id):
    inter = rn._by_id[inter_id]
    cx, cy = inter["point"]["x"], inter["point"]["y"]
    incoming = rn.incoming_lanes(inter_id)
    outgoing = rn.outgoing_lanes(inter_id)
    road_links = inter["roadLinks"]
    greens = rn.green_phases(inter_id)
    lp = rn._lightphases(inter_id)

    def road_lane_ids(road_id):
        n = len(rn._road_by_id[road_id]["lanes"])
        return ["{}_{}".format(road_id, k) for k in range(n)]

    def approach_label(road_id):
        fp = _far_point(rn, road_id, cx, cy)
        return compass_vi(bearing_deg(cx, cy, fp["x"], fp["y"]))

    phases = []
    for g in greens:
        movements, appset = [], []
        for rl_idx in lp[g].get("availableRoadLinks", []):
            rl = road_links[rl_idx]
            in_l, out_l = [], []
            for ll in rl["laneLinks"]:
                il = "{}_{}".format(rl["startRoad"], ll["startLaneIndex"])
                ol = "{}_{}".format(rl["endRoad"], ll["endLaneIndex"])
                if il not in in_l:
                    in_l.append(il)
                if ol not in out_l:
                    out_l.append(ol)
            movements.append({"from_road": rl["startRoad"], "to_road": rl["endRoad"],
                              "in_lanes": in_l, "out_lanes": out_l,
                              "turn": rl.get("type", "go_straight")})
            lab = approach_label(rl["startRoad"])
            if lab not in appset:
                appset.append(lab)
        phases.append({"phase_index": g, "movements": movements, "approaches_vi": appset})

    approaches = []
    for road_id in inter["roads"]:
        road = rn._road_by_id[road_id]
        role = "in" if road["endIntersection"] == inter_id else "out"
        fp = _far_point(rn, road_id, cx, cy)
        approaches.append({"road": road_id, "role": role,
                           "angle_deg": bearing_deg(cx, cy, fp["x"], fp["y"]),
                           "compass_vi": compass_vi(bearing_deg(cx, cy, fp["x"], fp["y"])),
                           "lanes": road_lane_ids(road_id)})

    return {"incoming_lanes": incoming, "outgoing_lanes": outgoing,
            "num_greens": len(greens), "green_phases": phases,
            "geometry": {"center": [cx, cy], "approaches": approaches}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="haichau_rush")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--inter", default=None)
    ap.add_argument("--out", default="frontend/sandbox_model.json")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    scen = SCENARIOS.get(args.area, {"count_norm": 5.0, "state_mode": "basic", "fixed_green": 25})
    ckpt = args.ckpt or "results/{a}/dqn_{a}.npz".format(a=args.area)
    rn, enc, net, weights = load_bundle(args.area, ckpt, scen["count_norm"], scen["state_mode"])

    if args.list:
        ranked = sorted(rn.signalized_ids(), key=lambda i: score_intersection(rn, i), reverse=True)
        for i in ranked[:10]:
            no_allgreen, n_in, clean, ng = score_intersection(rn, i)
            print("{:>2} no-allgreen  {:>2} in-approaches  {:>2} clean-phases  {:>2} greens   {}".format(
                no_allgreen, n_in, clean, ng, i))
        return 0

    inter_id = args.inter or pick_intersection(rn)
    bundle = {
        "meta": {"area": args.area, "intersection_id": inter_id,
                 "state_mode": scen["state_mode"], "count_norm": scen["count_norm"],
                 "fixed_green": scen["fixed_green"], "action_interval": 10,
                 "min_green": 10, "yellow_time": 3, "dueling": "Wv" in weights},
        "dims": {"max_in": enc.max_in, "max_out": enc.max_out, "max_green": enc.max_green,
                 "obs_dim": enc.obs_dim, "hidden": int(np.asarray(weights["W1"]).shape[1]),
                 "n_actions": enc.max_green},
        "intersection": intersection_block(rn, enc, inter_id),
        "weights": weights,
        "parity": parity_samples(net, enc.obs_dim, enc.max_green, args.samples, seed=1),
    }
    out_path = ROOT / args.out
    out_path.write_text(json.dumps(bundle))
    print("wrote", out_path, "obs_dim=", enc.obs_dim, "n_actions=", enc.max_green)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
