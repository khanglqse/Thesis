"""Pure helpers for loading and summarising comparison/training results.

Host-only (Python 3.13). No cityflow import.
"""
import json


def load_json(path):
    with open(path) as f:
        return json.load(f)


def _rows(comparison):
    return comparison.get("table", [])


def best_per_metric(comparison):
    """Return {metric: controller} for the best controller per metric.

    Lower is better for travel_time and queue; higher (least negative) for reward.
    """
    rows = _rows(comparison)
    if not rows:
        return {}
    return {
        "travel_time": min(rows, key=lambda r: r["final_average_travel_time"])["controller"],
        "queue": min(rows, key=lambda r: r["mean_total_queue"])["controller"],
        "reward": max(rows, key=lambda r: r["mean_reward"])["controller"],
    }


def improvements_vs_fixed(comparison):
    """Per-controller percentage improvement relative to the FixedTime baseline.

    Positive always means "better": travel time and queue are reductions,
    reward is the increase relative to |FixedTime reward|.
    Returns {} if there is no FixedTime row.
    """
    rows = _rows(comparison)
    fixed = next((r for r in rows if r["controller"] == "FixedTime"), None)
    if fixed is None:
        return {}
    f_tt = fixed["final_average_travel_time"]
    f_q = fixed["mean_total_queue"]
    f_r = fixed["mean_reward"]
    out = {}
    for r in rows:
        tt = (f_tt - r["final_average_travel_time"]) / f_tt * 100.0 if f_tt else 0.0
        q = (f_q - r["mean_total_queue"]) / f_q * 100.0 if f_q else 0.0
        rew = (r["mean_reward"] - f_r) / abs(f_r) * 100.0 if f_r else 0.0
        out[r["controller"]] = {
            "travel_time_pct": tt,
            "queue_pct": q,
            "reward_pct": rew,
        }
    return out
