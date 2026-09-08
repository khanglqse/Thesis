"""Hierarchical matched-case statistics for the Hai Chau campaign."""

import math
import statistics

import numpy as np


DETERMINISTIC_CONTROLLERS = frozenset((
    "tuned_fixed", "max_pressure", "hysteretic_mp",
))


def paired_bootstrap(differences, seed=20260908, samples=10000):
    values = np.asarray([float(value) for value in differences], dtype=float)
    if not len(values):
        raise ValueError("paired bootstrap requires at least one difference")
    if not np.isfinite(values).all():
        raise ValueError("paired bootstrap requires finite differences")
    if int(samples) <= 0:
        raise ValueError("bootstrap samples must be positive")
    if len(values) == 1:
        return float(values[0]), float(values[0])
    rng = np.random.RandomState(int(seed))
    indexes = rng.randint(0, len(values), size=(int(samples), len(values)))
    means = values[indexes].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def _summary(values):
    values = [float(value) for value in values]
    if not values:
        raise ValueError("cannot summarize an empty statistical unit")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("statistical units must be finite")
    low, high = paired_bootstrap(values)
    return {
        "n_independent": len(values),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "standard_deviation": (
            float(statistics.stdev(values)) if len(values) > 1 else 0.0),
        "bootstrap_ci95": [low, high],
        "independent_values": values,
    }


def _row(run):
    metrics = run.get("metrics")
    if not isinstance(metrics, dict):
        return dict(run)
    flattened = dict(run)
    flattened.pop("metrics", None)
    flattened.update(metrics)
    return flattened


def _match_key(row):
    return (
        row.get("regime"), row.get("case_id"), row.get("demand_seed"),
        row.get("simulator_seed"),
    )


def _independent(rows, metric, learning):
    if learning:
        grouped = {}
        cells = set()
        for row in rows:
            seed = row.get("learning_seed")
            if seed is None:
                raise ValueError("learning controller row is missing learning_seed")
            cell = (int(seed), _match_key(row))
            if cell in cells:
                raise ValueError("duplicate learning seed/case cell")
            cells.add(cell)
            grouped.setdefault(int(seed), []).append(row)
        coverage = [set(_match_key(row) for row in grouped[seed])
                    for seed in sorted(grouped)]
        if coverage and any(value != coverage[0] for value in coverage[1:]):
            raise ValueError(
                "learning seeds require identical matched-case coverage")
        return [statistics.mean(float(row[metric]) for row in grouped[seed])
                for seed in sorted(grouped)]
    ordered = sorted(rows, key=_match_key)
    keys = [_match_key(row) for row in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate deterministic matched-case cell")
    return [float(row[metric]) for row in ordered]


def aggregate_campaign(runs, required_learning_seeds=None,
                       required_regimes=("normal", "am_peak", "pm_peak"),
                       minimum_learning_seeds=5, minimum_demand_units=1,
                       normal_point_limit=0.0,
                       normal_ci_margin_fraction=0.05,
                       peak_ci_upper_limit=0.0,
                       completion_degradation_limit=0.02,
                       primary_learned_controller="neighbor_phase_ddqn"):
    """Aggregate demand cases inside learning seeds before inference."""
    if int(minimum_learning_seeds) <= 0 or int(minimum_demand_units) <= 0:
        raise ValueError("minimum independent units must be positive")
    if (not isinstance(primary_learned_controller, str)
            or not primary_learned_controller
            or primary_learned_controller in DETERMINISTIC_CONTROLLERS):
        raise ValueError("primary learned controller is invalid")
    rows = [_row(run) for run in runs]
    required = (
        "controller_id", "case_id", "regime", "demand_seed",
        "simulator_seed", "queue_integral_vehicle_seconds", "completion_rate",
    )
    for row in rows:
        missing = [field for field in required if row.get(field) is None]
        if missing:
            raise ValueError("campaign row requires %s" % ", ".join(missing))
        queue = float(row["queue_integral_vehicle_seconds"])
        completion = float(row["completion_rate"])
        if not math.isfinite(queue) or queue < 0:
            raise ValueError("queue metric must be finite and non-negative")
        if not math.isfinite(completion) or not 0 <= completion <= 1:
            raise ValueError("completion rate must be finite and between zero and one")

    baseline_rows = [row for row in rows
                     if row["controller_id"] == "tuned_fixed"]
    baseline = {}
    for row in baseline_rows:
        key = _match_key(row)
        if key in baseline:
            raise ValueError("deterministic tuned_fixed baseline is duplicated")
        baseline[key] = row
    if any(row["controller_id"] != "tuned_fixed" for row in rows) \
            and not baseline:
        raise ValueError("matched tuned_fixed baseline is required")

    grouped = {}
    for row in rows:
        grouped.setdefault(row["controller_id"], {}).setdefault(
            row["regime"], []).append(row)
    summary = {}
    all_learning_seeds = set()
    for controller_id in sorted(grouped):
        summary[controller_id] = {}
        for regime in sorted(grouped[controller_id]):
            group = grouped[controller_id][regime]
            learning = controller_id not in DETERMINISTIC_CONTROLLERS
            if learning:
                all_learning_seeds.update(int(row["learning_seed"]) for row in group)
            queue_values = _independent(
                group, "queue_integral_vehicle_seconds", learning)
            matched_keys = set(_match_key(row) for row in group)
            baseline_keys = set(
                key for key in baseline if key[0] == regime)
            if controller_id != "tuned_fixed" and matched_keys != baseline_keys:
                raise ValueError(
                    "%s/%s must cover the full tuned_fixed matched-case set" %
                    (controller_id, regime))
            result = {
                "n_independent": len(queue_values),
                "matched_demand_units": len(matched_keys),
                "statistical_unit": (
                    "learning_seed_after_matched_case_mean" if learning
                    else "matched_demand_simulator_case"),
                "queue": _summary(queue_values),
                "completion_rate": _summary(_independent(
                    group, "completion_rate", learning)),
                "raw_rows": group,
            }
            if controller_id != "tuned_fixed":
                differences = []
                completion_degradations = []
                for row in group:
                    base = baseline.get(_match_key(row))
                    if base is None:
                        raise ValueError(
                            "matched tuned_fixed row is missing for %s" %
                            (row["case_id"],))
                    differences.append(dict(
                        row,
                        _queue_difference=(
                            float(row["queue_integral_vehicle_seconds"])
                            - float(base["queue_integral_vehicle_seconds"])),
                        _completion_degradation=(
                            float(base["completion_rate"])
                            - float(row["completion_rate"])),
                    ))
                difference_values = _independent(
                    differences, "_queue_difference", learning)
                difference_summary = _summary(difference_values)
                baseline_mean = statistics.mean(
                    float(baseline[_match_key(row)][
                        "queue_integral_vehicle_seconds"])
                    for row in group)
                difference_summary["baseline_mean"] = float(baseline_mean)
                difference_summary["relative_change_percent"] = (
                    100.0 * difference_summary["mean"] / baseline_mean
                    if baseline_mean else None)
                result["queue_difference_vs_tuned_fixed"] = difference_summary
                completion_degradations = [
                    value["_completion_degradation"] for value in differences]
                result["completion_degradation_vs_tuned_fixed"] = {
                    "max": max(completion_degradations),
                    "raw_values": completion_degradations,
                }
            summary[controller_id][regime] = result
    summary["_metadata"] = {
        "bootstrap_seed": 20260908,
        "bootstrap_samples": 10000,
        "learning_seeds": sorted(all_learning_seeds),
        "required_learning_seeds": sorted(
            int(seed) for seed in (
                required_learning_seeds
                if required_learning_seeds is not None else all_learning_seeds)),
        "required_regimes": list(required_regimes),
        "minimum_learning_seeds": int(minimum_learning_seeds),
        "minimum_demand_units": int(minimum_demand_units),
        "normal_point_limit": float(normal_point_limit),
        "normal_ci_margin_fraction": float(normal_ci_margin_fraction),
        "peak_ci_upper_limit": float(peak_ci_upper_limit),
        "completion_degradation_limit": float(completion_degradation_limit),
        "queue_metric": "queue_integral_vehicle_seconds",
        "baseline_controller": "tuned_fixed",
        "primary_learned_controller": primary_learned_controller,
    }
    return summary


def evaluate_acceptance(summary):
    metadata = summary.get("_metadata", {})
    required_regimes = tuple(metadata.get(
        "required_regimes", ("normal", "am_peak", "pm_peak")))
    required_seeds = set(metadata.get("required_learning_seeds", ()))
    minimum_learning_seeds = int(metadata.get("minimum_learning_seeds", 5))
    minimum_demand_units = int(metadata.get("minimum_demand_units", 1))
    normal_point_limit = float(metadata.get("normal_point_limit", 0.0))
    normal_ci_margin_fraction = float(
        metadata.get("normal_ci_margin_fraction", 0.05))
    peak_ci_upper_limit = float(metadata.get("peak_ci_upper_limit", 0.0))
    completion_degradation_limit = float(
        metadata.get("completion_degradation_limit", 0.02))
    primary = metadata.get(
        "primary_learned_controller", "neighbor_phase_ddqn")
    candidate = summary.get(primary, {})
    normal = candidate.get("normal")
    if not normal or "queue_difference_vs_tuned_fixed" not in normal:
        return {
            "normal_point_noninferiority": False,
            "normal_ci_noninferiority": False,
            "peak_improvement": False,
            "completion_preserved": False,
            "completion_degradation_max": None,
            "five_learning_seeds": False,
            "minimum_independent_units_met": False,
            "accepted": False,
        }

    unit_status = {}
    for regime in required_regimes:
        result = candidate.get(regime, {})
        seeds = set(row.get("learning_seed") for row in result.get("raw_rows", [])
                    if row.get("learning_seed") is not None)
        baseline_n = summary.get("tuned_fixed", {}).get(regime, {}).get(
            "n_independent", 0)
        unit_status[regime] = bool(
            seeds == required_seeds
            and len(seeds) >= minimum_learning_seeds
            and result.get("n_independent", 0) >= minimum_learning_seeds
            and result.get("matched_demand_units", 0) >= minimum_demand_units
            and baseline_n >= minimum_demand_units)
    units_met = bool(required_regimes) and all(unit_status.values())

    normal_effect = normal["queue_difference_vs_tuned_fixed"]
    normal_point = unit_status.get("normal", False) \
        and normal_effect["mean"] <= normal_point_limit
    normal_ci = unit_status.get("normal", False) \
        and normal_effect["bootstrap_ci95"][1] <= (
            normal_ci_margin_fraction * normal_effect["baseline_mean"])
    peaks = []
    for regime in ("am_peak", "pm_peak"):
        value = candidate.get(regime, {}).get("queue_difference_vs_tuned_fixed")
        if value and unit_status.get(regime, False):
            peaks.append(value["bootstrap_ci95"][1] < peak_ci_upper_limit)
    peak_improvement = any(peaks)
    degradations = [
        result["completion_degradation_vs_tuned_fixed"]["max"]
        for regime, result in candidate.items()
        if isinstance(result, dict)
        and "completion_degradation_vs_tuned_fixed" in result
    ]
    worst_degradation = max(degradations) if degradations else None
    completion_preserved = (
        worst_degradation is not None
        and worst_degradation <= completion_degradation_limit)
    five_seeds = bool(required_seeds) and all(
        unit_status.get(regime, False) for regime in required_regimes)
    return {
        "normal_point_noninferiority": bool(normal_point),
        "normal_ci_noninferiority": bool(normal_ci),
        "peak_improvement": bool(peak_improvement),
        "completion_preserved": bool(completion_preserved),
        "completion_degradation_max": worst_degradation,
        "five_learning_seeds": five_seeds,
        "minimum_independent_units_met": units_met,
        "independent_unit_status": unit_status,
        "accepted": bool(normal_point and normal_ci and peak_improvement
                         and completion_preserved and five_seeds and units_met),
    }
