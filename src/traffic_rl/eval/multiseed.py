"""Multi-seed aggregation: mean / std / 95% CI across seeds. 3.6-safe (NumPy only).

Turns single-seed point estimates into claims with a confidence interval. Each
seed contributes one `run_episode` row per controller; we pool across seeds and
report mean, population std (ddof=0), and a normal-approx 95% CI on the mean.
"""
import math

from traffic_rl.eval.compare import cumulative_wait_hours

# Metrics summarised per controller. "wait_hours" = final cumulative waiting time
# (vehicle-hours), the headline metric; derived from the per-decision queue trace.
_METRICS = ("mean_total_queue", "wait_hours", "final_average_travel_time")


def summary_stats(values):
    import numpy as np
    a = np.asarray(list(values), dtype=float)
    n = int(a.size)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci95": 0.0, "n": 0}
    mean = float(a.mean())
    std = float(a.std())                       # ddof=0 (population)
    ci95 = float(1.96 * std / math.sqrt(n)) if n > 1 else 0.0
    return {"mean": mean, "std": std, "ci95": ci95, "n": n}


def _wait_hours(row):
    cum = cumulative_wait_hours(row.get("queue_series") or [], 10)
    return cum[-1] if cum else 0.0


def _metric_value(row, metric):
    if metric == "wait_hours":
        return _wait_hours(row)
    return float(row.get(metric) or 0.0)


def aggregate_seeds(per_seed_rows):
    """per_seed_rows: list (outer=seed) of lists of run_episode rows.

    Returns {controller: {metric: summary_stats}} for each metric in _METRICS.
    """
    acc = {}
    for rows in per_seed_rows:
        for row in rows:
            ctrl = row["controller"]
            d = acc.setdefault(ctrl, dict((m, []) for m in _METRICS))
            for m in _METRICS:
                d[m].append(_metric_value(row, m))
    return dict(
        (ctrl, dict((m, summary_stats(vals)) for m, vals in md.items()))
        for ctrl, md in acc.items()
    )
