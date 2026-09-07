"""Statistical summaries for the Da Nang held-out protocol."""

import statistics

import numpy as np


def _summary(values):
    values = [float(value) for value in values]
    rng = np.random.RandomState(20260907)
    samples = np.asarray(values, dtype=float)
    if len(samples) > 1:
        indexes = rng.randint(0, len(samples), size=(20000, len(samples)))
        bootstrap_means = samples[indexes].mean(axis=1)
        low, high = np.percentile(bootstrap_means, [2.5, 97.5])
        standard_deviation = statistics.stdev(values)
    else:
        low = high = samples[0]
        standard_deviation = 0.0
    return {
        "n_independent": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "standard_deviation": standard_deviation,
        "bootstrap_ci95": [float(low), float(high)],
        "independent_values": values,
    }


def summarize_metric(rows, metric, learning_controller=False):
    """Summarize raw rows without treating crossed RL seeds as independent."""
    if learning_controller:
        grouped = {}
        for row in rows:
            grouped.setdefault(int(row["train_seed"]), []).append(float(row[metric]))
        values = [statistics.mean(grouped[seed]) for seed in sorted(grouped)]
    else:
        values = [float(row[metric]) for row in rows]
    return _summary(values)


def paired_effect(learning_rows, baseline_rows, metric):
    """Compute DQN-minus-baseline paired effects, averaged within train seed."""
    baseline = dict((int(row["demand_seed"]), float(row[metric]))
                    for row in baseline_rows)
    grouped = {}
    for row in learning_rows:
        demand_seed = int(row["demand_seed"])
        grouped.setdefault(int(row["train_seed"]), []).append(
            float(row[metric]) - baseline[demand_seed])
    values = [statistics.mean(grouped[seed]) for seed in sorted(grouped)]
    result = _summary(values)
    baseline_mean = statistics.mean(baseline.values())
    result["mean_difference"] = result.pop("mean")
    result["relative_change_percent"] = (
        100.0 * result["mean_difference"] / baseline_mean if baseline_mean else None)
    return result
