import math

import pytest

from traffic_rl.eval.network_statistics import (
    aggregate_campaign,
    evaluate_acceptance,
    paired_bootstrap,
)


def _rows(learning_seeds=(11, 12), regimes=("normal",), demands=(101, 102, 103)):
    rows = []
    for regime in regimes:
        regime_offset = 20 if regime == "pm_peak" else 0
        for demand_seed in demands:
            baseline_queue = 100 + regime_offset + demand_seed - 100
            rows.append({
                "controller_id": "tuned_fixed",
                "case_id": "%s-%s" % (regime, demand_seed),
                "regime": regime,
                "learning_seed": None,
                "demand_seed": demand_seed,
                "simulator_seed": demand_seed + 100,
                "queue_integral_vehicle_seconds": baseline_queue,
                "completion_rate": 0.95,
            })
            for learning_seed in learning_seeds:
                rows.append({
                    "controller_id": "neighbor_phase_ddqn",
                    "case_id": "%s-%s" % (regime, demand_seed),
                    "regime": regime,
                    "learning_seed": learning_seed,
                    "demand_seed": demand_seed,
                    "simulator_seed": demand_seed + 100,
                    "queue_integral_vehicle_seconds": baseline_queue - learning_seed + 10,
                    "completion_rate": 0.94,
                })
    return rows


def test_rl_aggregation_averages_demands_inside_learning_seed():
    summary = aggregate_campaign(_rows())
    result = summary["neighbor_phase_ddqn"]["normal"]
    assert result["n_independent"] == 2
    assert result["queue"]["independent_values"] == [101.0, 100.0]
    assert result["queue_difference_vs_tuned_fixed"]["independent_values"] == [-1.0, -2.0]


def test_deterministic_baseline_uses_matched_demand_as_unit():
    summary = aggregate_campaign(_rows())
    result = summary["tuned_fixed"]["normal"]
    assert result["n_independent"] == 3
    assert result["queue"]["mean"] == 102.0


def test_paired_bootstrap_is_deterministic_and_reports_ordered_bounds():
    first = paired_bootstrap([-4, -2, 0, 1], seed=7, samples=1000)
    second = paired_bootstrap([-4, -2, 0, 1], seed=7, samples=1000)
    assert first == second
    assert first[0] <= first[1]


def test_paired_bootstrap_rejects_non_finite_data():
    with pytest.raises(ValueError, match="finite"):
        paired_bootstrap([1.0, math.nan])


def test_peak_gate_requires_ci_below_zero():
    summary = aggregate_campaign(_rows(
        learning_seeds=(11, 12, 13, 14, 15),
        regimes=("normal", "pm_peak"),
    ))
    result = evaluate_acceptance(summary)
    assert result["peak_improvement"] is True


def test_normal_gate_rejects_positive_point_estimate():
    rows = _rows(learning_seeds=(11, 12, 13, 14, 15))
    for row in rows:
        if row["controller_id"] == "neighbor_phase_ddqn":
            row["queue_integral_vehicle_seconds"] += 20
    result = evaluate_acceptance(aggregate_campaign(rows))
    assert result["normal_point_noninferiority"] is False
    assert result["accepted"] is False


def test_completion_gate_uses_worst_matched_case_not_the_mean():
    rows = _rows(learning_seeds=(11, 12, 13, 14, 15), demands=(101, 102))
    rows[-1]["completion_rate"] = 0.90
    result = evaluate_acceptance(aggregate_campaign(rows))
    assert result["completion_degradation_max"] == pytest.approx(0.05)
    assert result["completion_preserved"] is False


def test_missing_matched_baseline_fails_closed():
    rows = [row for row in _rows() if row["controller_id"] != "tuned_fixed"]
    with pytest.raises(ValueError, match="matched tuned_fixed"):
        aggregate_campaign(rows)


def test_five_seed_gate_counts_candidate_seeds_only():
    rows = _rows(learning_seeds=(11, 12), regimes=("normal", "pm_peak"))
    learned = [row for row in _rows(
        learning_seeds=(21, 22, 23, 24, 25), regimes=("normal", "pm_peak"))
        if row["controller_id"] == "neighbor_phase_ddqn"]
    for row in learned:
        row["controller_id"] = "shared_ddqn_legacy"
    result = evaluate_acceptance(aggregate_campaign(rows + learned))
    assert result["five_learning_seeds"] is False


def test_each_gated_regime_requires_the_declared_learning_seed_set():
    rows = _rows(
        learning_seeds=(11, 12, 13, 14, 15),
        regimes=("normal", "pm_peak"),
    )
    rows = [row for row in rows if not (
        row["regime"] == "pm_peak"
        and row["controller_id"] == "neighbor_phase_ddqn"
        and row["learning_seed"] != 11
    )]

    result = evaluate_acceptance(aggregate_campaign(
        rows, required_learning_seeds=(11, 12, 13, 14, 15),
        required_regimes=("normal", "pm_peak"),
    ))

    assert result["five_learning_seeds"] is False
    assert result["peak_improvement"] is False
    assert result["accepted"] is False


def test_learning_seed_case_coverage_must_be_identical():
    rows = _rows(learning_seeds=(11, 12), demands=(101, 102))
    rows = [row for row in rows if not (
        row["controller_id"] == "neighbor_phase_ddqn"
        and row["learning_seed"] == 12
        and row["demand_seed"] == 102
    )]

    with pytest.raises(ValueError, match="identical matched-case coverage"):
        aggregate_campaign(rows)


def test_duplicate_learning_seed_case_cell_is_rejected():
    rows = _rows(learning_seeds=(11, 12), demands=(101,))
    duplicate = dict(next(row for row in rows if (
        row["controller_id"] == "neighbor_phase_ddqn"
        and row["learning_seed"] == 11
    )))

    with pytest.raises(ValueError, match="duplicate learning seed/case"):
        aggregate_campaign(rows + [duplicate])


def test_declared_minimum_demand_units_is_an_acceptance_gate():
    summary = aggregate_campaign(
        _rows(
            learning_seeds=(11, 12, 13, 14, 15),
            regimes=("normal", "am_peak", "pm_peak"),
            demands=(101,),
        ),
        required_learning_seeds=(11, 12, 13, 14, 15),
        minimum_demand_units=2,
    )

    result = evaluate_acceptance(summary)

    assert result["minimum_independent_units_met"] is False
    assert result["accepted"] is False


def test_candidate_seed_coverage_must_equal_full_baseline_cell_set():
    rows = _rows(
        learning_seeds=(11, 12, 13, 14, 15),
        regimes=("normal", "am_peak", "pm_peak"),
        demands=(101, 102),
    )
    rows = [row for row in rows if not (
        row["controller_id"] == "neighbor_phase_ddqn"
        and row["demand_seed"] == 102
    )]

    with pytest.raises(ValueError, match="full tuned_fixed matched-case set"):
        aggregate_campaign(
            rows, required_learning_seeds=(11, 12, 13, 14, 15),
            minimum_demand_units=2,
        )
