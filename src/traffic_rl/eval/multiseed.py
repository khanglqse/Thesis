"""Multi-seed aggregation: mean / sample-std / 95% CI across seeds. 3.6-safe (NumPy only).

Turns single-seed point estimates into claims with a confidence interval. Each
seed contributes one `run_episode` row per controller; we pool across seeds and
report the mean, the *sample* standard deviation (ddof=1), and a Student-t 95%
confidence interval on the mean. With only ~5 seeds a normal-approx (z=1.96) CI on
a population std is materially too narrow, so we use t(0.975, df=n-1) with the
sample std -- the standard small-sample interval and the correct one to report for
reinforcement-learning results (cf. Henderson et al. 2018; Colas et al. 2018).
"""
import math

from traffic_rl.eval.compare import cumulative_wait_hours

# Metrics summarised per controller. "wait_hours" = final cumulative waiting time
# (vehicle-hours), the headline metric; derived from the per-decision queue trace.
_METRICS = ("mean_total_queue", "wait_hours", "final_average_travel_time")

# Two-sided 95% Student-t critical values t(0.975, df), keyed by degrees of freedom
# (df = n-1). Hardcoded so the module stays SciPy-free (Python-3.6 container). Seed
# counts are small (typically 5 -> df=4 -> 2.776); df beyond the table falls back to
# the normal-approx 1.96, which the t-values converge to as df grows.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def _t95(df):
    """t(0.975, df); falls back to the z-approx 1.96 for df outside the table."""
    if df <= 0:
        return 0.0
    return _T95.get(df, 1.96)


def summary_stats(values):
    import numpy as np
    a = np.asarray(list(values), dtype=float)
    n = int(a.size)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci95": 0.0, "n": 0}
    mean = float(a.mean())
    std = float(a.std(ddof=1)) if n > 1 else 0.0   # sample std (ddof=1)
    ci95 = float(_t95(n - 1) * std / math.sqrt(n)) if n > 1 else 0.0
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
