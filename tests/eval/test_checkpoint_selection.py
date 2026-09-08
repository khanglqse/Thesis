import pytest

from traffic_rl.eval.checkpoint_selection import (
    choose_checkpoint, choose_reporting_checkpoint, relative_regret,
    score_validation)


def _row(scenario, candidate_queue, baseline_queue,
         candidate_completion=1.0, baseline_completion=1.0):
    return {
        "scenario": scenario,
        "candidate_queue": candidate_queue,
        "baseline_queue": baseline_queue,
        "candidate_completion": candidate_completion,
        "baseline_completion": baseline_completion,
    }


def test_relative_regret_uses_baseline_denominator():
    assert relative_regret(80.0, 100.0) == pytest.approx(-0.2)


def test_checkpoint_that_loses_normal_is_ineligible():
    rows = [_row("normal", 105, 100), _row("am_peak", 80, 100),
            _row("pm_peak", 70, 100)]

    assert score_validation(rows)["eligible"] is False


@pytest.mark.parametrize("regressing_scenario", ["am_peak", "pm_peak"])
def test_peak_regression_is_ineligible_despite_normal_improvement(regressing_scenario):
    rows = [_row(scenario, 101 if scenario == regressing_scenario else 80, 100)
            for scenario in ("normal", "am_peak", "pm_peak")]

    assert score_validation(rows)["eligible"] is False


@pytest.mark.parametrize("missing_scenario", ["normal", "am_peak", "pm_peak"])
def test_incomplete_regime_coverage_is_ineligible(missing_scenario):
    rows = [_row(scenario, 90, 100)
            for scenario in ("normal", "am_peak", "pm_peak")
            if scenario != missing_scenario]

    assert score_validation(rows)["eligible"] is False


def test_unexpected_regime_is_ineligible():
    rows = [_row(scenario, 90, 100)
            for scenario in ("normal", "am_peak", "pm_peak", "extra")]

    assert score_validation(rows)["eligible"] is False


def test_all_regimes_can_equal_baseline_with_complete_completion_evidence():
    rows = [_row(scenario, 100, 100, 0.99, 1.0)
            for scenario in ("normal", "am_peak", "pm_peak")]

    assert score_validation(rows)["eligible"] is True


def test_peak_gate_uses_regime_mean_rather_than_each_case():
    rows = [_row("normal", 100, 100), _row("am_peak", 105, 100),
            _row("am_peak", 90, 100), _row("pm_peak", 100, 100)]

    assert score_validation(rows)["eligible"] is True


def test_completion_degradation_over_two_points_is_ineligible():
    rows = [_row("normal", 95, 100, 0.97, 1.0),
            _row("am_peak", 80, 100), _row("pm_peak", 70, 100)]

    assert score_validation(rows)["eligible"] is False


def test_missing_completion_is_ineligible():
    rows = [{"scenario": scenario, "candidate_queue": 90,
             "baseline_queue": 100}
            for scenario in ("normal", "am_peak", "pm_peak")]

    assert score_validation(rows)["eligible"] is False


def test_score_averages_seeds_within_each_regime():
    rows = [_row("normal", 90, 100), _row("normal", 100, 100),
            _row("am_peak", 80, 100), _row("pm_peak", 70, 100)]
    score = score_validation(rows)

    assert score["normal_regret"] == pytest.approx(-0.05)
    assert score["worst_regret"] == pytest.approx(-0.05)
    assert score["mean_regret"] == pytest.approx((-0.05 - 0.2 - 0.3) / 3.0)
    assert score["eligible"] is True


def test_selection_minimizes_worst_regret_then_mean_then_step():
    evaluations = {
        "step-30": {"eligible": True, "worst_regret": -0.01,
                    "mean_regret": -0.10, "training_step": 30},
        "step-20": {"eligible": True, "worst_regret": -0.01,
                    "mean_regret": -0.20, "training_step": 20},
        "step-10": {"eligible": True, "worst_regret": -0.01,
                    "mean_regret": -0.20, "training_step": 10},
        "ineligible": {"eligible": False, "worst_regret": -0.50,
                       "mean_regret": -0.50, "training_step": 1},
    }

    assert choose_checkpoint(evaluations) == "step-10"


def test_selection_fails_closed_when_no_candidate_is_eligible():
    with pytest.raises(ValueError, match="eligible"):
        choose_checkpoint({"bad": {"eligible": False}})


def test_reporting_selection_chooses_best_validation_when_all_ineligible():
    evaluations = {
        "step-30": {"eligible": False, "worst_regret": 0.30,
                    "mean_regret": 0.10, "training_step": 30},
        "step-20": {"eligible": False, "worst_regret": 0.20,
                    "mean_regret": 0.15, "training_step": 20},
        "step-10": {"eligible": False, "worst_regret": 0.20,
                    "mean_regret": 0.15, "training_step": 10},
    }

    assert choose_reporting_checkpoint(evaluations) == "step-10"
