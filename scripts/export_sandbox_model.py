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

    # (Task 2 fills in intersection selection, geometry, phase movements, and the
    # full bundle. Task 1 stops after weights/dims/parity so the parity path is
    # testable on its own.)
    bundle = {
        "meta": {"area": args.area, "state_mode": scen["state_mode"],
                 "count_norm": scen["count_norm"], "fixed_green": scen["fixed_green"],
                 "action_interval": 10, "min_green": 10, "yellow_time": 3,
                 "dueling": "Wv" in weights},
        "dims": {"max_in": enc.max_in, "max_out": enc.max_out, "max_green": enc.max_green,
                 "obs_dim": enc.obs_dim, "hidden": int(np.asarray(weights["W1"]).shape[1]),
                 "n_actions": enc.max_green},
        "weights": weights,
        "parity": parity_samples(net, enc.obs_dim, enc.max_green, args.samples, seed=1),
    }
    out_path = ROOT / args.out
    out_path.write_text(json.dumps(bundle))
    print("wrote", out_path, "obs_dim=", enc.obs_dim, "n_actions=", enc.max_green)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
