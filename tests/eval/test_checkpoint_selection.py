import pytest

from traffic_rl.eval.checkpoint_selection import (
    choose_checkpoint, choose_reporting_checkpoint, relative_regret,
    score_validation, validate_checkpoint_selection)


def _row(scenario, candidate_queue, baseline_queue,
         candidate_completion=1.0, baseline_completion=1.0,
         candidate_insertion=1.0, baseline_insertion=1.0):
    return {
        "scenario": scenario,
        "candidate_queue": candidate_queue,
        "baseline_queue": baseline_queue,
        "candidate_completion": candidate_completion,
        "baseline_completion": baseline_completion,
        "candidate_insertion": candidate_insertion,
        "baseline_insertion": baseline_insertion,
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


def test_insertion_degradation_over_two_points_is_ineligible():
    rows = [_row("normal", 90, 100, candidate_insertion=0.979,
                 baseline_insertion=1.0),
            _row("am_peak", 80, 100), _row("pm_peak", 70, 100)]

    score = score_validation(rows)

    assert score["max_insertion_degradation"] == pytest.approx(0.021)
    assert score["eligible"] is False


def test_missing_insertion_evidence_is_ineligible():
    rows = [_row(scenario, 90, 100)
            for scenario in ("normal", "am_peak", "pm_peak")]
    del rows[0]["candidate_insertion"]

    score = score_validation(rows)

    assert score["insertion_evidence_complete"] is False
    assert score["eligible"] is False


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -0.01, 1.01])
def test_invalid_insertion_rate_fails_closed(invalid):
    rows = [_row(scenario, 90, 100)
            for scenario in ("normal", "am_peak", "pm_peak")]
    rows[0]["candidate_insertion"] = invalid

    with pytest.raises(ValueError, match="insertion rate"):
        score_validation(rows)


def test_score_averages_seeds_within_each_regime():
    rows = [_row("normal", 90, 100), _row("normal", 100, 100),
            _row("am_peak", 80, 100), _row("pm_peak", 70, 100)]
    score = score_validation(rows)

    assert score["normal_regret"] == pytest.approx(-0.05)
    assert score["worst_regret"] == pytest.approx(-0.05)
    assert score["mean_regret"] == pytest.approx((-0.05 - 0.2 - 0.3) / 3.0)
    assert score["eligible"] is True


def test_validation_mean_is_stable_across_python_sum_implementations():
    from traffic_rl.eval.checkpoint_selection import _deterministic_sum

    regrets = [
        3.5619589294679868,
        1.7591974067585805,
        1.7762790158116415,
    ]

    assert _deterministic_sum(regrets) / len(regrets) == 2.365811784012736


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


def test_artifact_validation_rejects_forged_old_eligible_score():
    rows = [_row(scenario, 90, 100)
            for scenario in ("normal", "am_peak", "pm_peak")]
    for row in rows:
        row.pop("candidate_insertion")
        row.pop("baseline_insertion")
        row["case_id"] = "validation-" + row["scenario"]
    validation = {"step-80": {"rows": rows, "score": {"eligible": True}}}
    selection = {
        "status": "eligible", "selected_checkpoint": "step-80",
        "eligible_for_test_evaluation": True,
        "eligibility_policy": {"schema_version": 1},
        "score": {"eligible": True},
    }

    with pytest.raises(ValueError, match="policy|score"):
        validate_checkpoint_selection(
            validation, selection, _tuning(rows),
            {row["case_id"] for row in rows})


def test_artifact_validation_requires_each_exact_validation_case_once():
    rows = []
    for scenario in ("normal", "am_peak", "pm_peak"):
        row = _row(scenario, 90, 100)
        row["case_id"] = "validation-" + scenario
        rows.append(row)
    score = score_validation(rows)
    validation = {"step-80": {"rows": rows, "score": score}}
    selection = {
        "status": "eligible", "selected_checkpoint": "step-80",
        "eligible_for_test_evaluation": True,
        "eligibility_policy": score["eligibility_policy"], "score": score,
    }

    with pytest.raises(ValueError, match="exact validation cases"):
        validate_checkpoint_selection(
            validation, selection, _tuning(rows),
            {"validation-normal", "validation-am_peak", "validation-pm_peak",
             "validation-normal-second-seed"})


def _tuning(rows):
    return {
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "rows": [{
                "case_id": row["case_id"], "scenario": row["scenario"],
                "queue_integral_vehicle_seconds": row["baseline_queue"],
                "completion_rate": row.get("baseline_completion"),
                "insertion_rate": row.get("baseline_insertion"),
            } for row in rows],
        }],
    }


def test_artifact_validation_rejects_baseline_values_from_another_case_run():
    rows = []
    for scenario in ("normal", "am_peak", "pm_peak"):
        row = _row(scenario, 90, 100)
        row["case_id"] = "validation-" + scenario
        rows.append(row)
    score = score_validation(rows)
    validation = {"step-80": {"rows": rows, "score": score}}
    selection = {
        "status": "eligible", "selected_checkpoint": "step-80",
        "eligible_for_test_evaluation": True,
        "eligibility_policy": score["eligibility_policy"], "score": score,
    }
    tuning = _tuning(rows)
    tuning["candidates"][0]["rows"][0]["insertion_rate"] = 0.95

    with pytest.raises(ValueError, match="baseline.*drift"):
        validate_checkpoint_selection(
            validation, selection, tuning, {row["case_id"] for row in rows})
