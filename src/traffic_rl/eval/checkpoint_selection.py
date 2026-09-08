"""Validation-only checkpoint scoring for the Hai Chau network policy."""
import math


CHECKPOINT_ELIGIBILITY_POLICY = {
    "schema_version": 2,
    "required_regimes": ["normal", "am_peak", "pm_peak"],
    "maximum_completion_loss": 0.02,
    "maximum_insertion_loss": 0.02,
    "queue_regret_limit_per_regime": 0.0,
    "comparison_unit": "matched_validation_case",
}


def _deterministic_sum(values):
    """Sum floats left-to-right so evidence is stable across Python runtimes."""
    total = 0.0
    for value in values:
        total += value
    return total


def relative_regret(candidate, baseline):
    baseline = float(baseline)
    if baseline <= 0:
        raise ValueError("baseline queue must be positive")
    return (float(candidate) - baseline) / baseline


def score_validation(rows):
    if not rows:
        raise ValueError("validation rows are required")
    by_scenario = {}
    completion_degradations = []
    insertion_degradations = []
    for row in rows:
        scenario = row.get("scenario", row.get("regime"))
        if not scenario:
            raise ValueError("validation row is missing scenario")
        regret = relative_regret(row["candidate_queue"], row["baseline_queue"])
        by_scenario.setdefault(scenario, []).append(regret)
        if "candidate_completion" in row and "baseline_completion" in row:
            completion_degradations.append(
                float(row["baseline_completion"])
                - float(row["candidate_completion"]))
        if "candidate_insertion" in row and "baseline_insertion" in row:
            candidate_insertion = float(row["candidate_insertion"])
            baseline_insertion = float(row["baseline_insertion"])
            if (not math.isfinite(candidate_insertion)
                    or not math.isfinite(baseline_insertion)
                    or not 0.0 <= candidate_insertion <= 1.0
                    or not 0.0 <= baseline_insertion <= 1.0):
                raise ValueError("insertion rate must be finite and within [0, 1]")
            insertion_degradations.append(
                baseline_insertion - candidate_insertion)

    scenario_regrets = {
        scenario: _deterministic_sum(values) / len(values)
        for scenario, values in by_scenario.items()
    }
    regrets = list(scenario_regrets.values())
    normal_regret = scenario_regrets.get("normal", float("inf"))
    max_completion_degradation = max(completion_degradations or [0.0])
    completion_evidence_complete = len(completion_degradations) == len(rows)
    max_insertion_degradation = max(insertion_degradations or [0.0])
    insertion_evidence_complete = len(insertion_degradations) == len(rows)
    required_scenarios = set(("normal", "am_peak", "pm_peak"))
    all_regimes_non_inferior = (set(scenario_regrets) == required_scenarios
                               and all(regret <= 0.0 for regret in regrets))
    return {
        "worst_regret": max(regrets),
        "mean_regret": _deterministic_sum(regrets) / len(regrets),
        "normal_regret": normal_regret,
        "max_completion_degradation": max_completion_degradation,
        "completion_evidence_complete": completion_evidence_complete,
        "max_insertion_degradation": max_insertion_degradation,
        "insertion_evidence_complete": insertion_evidence_complete,
        "scenario_regrets": scenario_regrets,
        "eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "eligible": bool(completion_evidence_complete
                         and insertion_evidence_complete
                         and all_regimes_non_inferior
                         and max_completion_degradation <= 0.02
                         and max_insertion_degradation <= 0.02),
    }


def choose_checkpoint(evaluations):
    eligible = []
    for checkpoint_id, evaluation in evaluations.items():
        score = (score_validation(evaluation)
                 if isinstance(evaluation, list) else evaluation)
        if score.get("eligible", False):
            training_step = score.get("training_step", float("inf"))
            eligible.append((float(score["worst_regret"]),
                             float(score["mean_regret"]),
                             float(training_step), checkpoint_id))
    if not eligible:
        raise ValueError("no eligible validation checkpoint")
    eligible.sort()
    return eligible[0][3]


def choose_reporting_checkpoint(evaluations):
    """Choose best validation score even when the eligibility gate rejects all."""
    ranked = []
    for checkpoint_id, evaluation in evaluations.items():
        score = (score_validation(evaluation)
                 if isinstance(evaluation, list) else evaluation)
        training_step = score.get("training_step", float("inf"))
        ranked.append((float(score["worst_regret"]),
                       float(score["mean_regret"]),
                       float(training_step), checkpoint_id))
    if not ranked:
        raise ValueError("no validation checkpoint")
    ranked.sort()
    return ranked[0][3]


def _selected_tuned_baseline_rows(tuning, expected_case_ids):
    if not isinstance(tuning, dict) or not isinstance(tuning.get("selected"), dict):
        raise ValueError("validation-tuned fixed baseline selection is missing")
    duration = tuning["selected"].get("fixed_green_duration")
    candidates = tuning.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("validation-tuned fixed baseline candidates are missing")
    matches = [candidate for candidate in candidates
               if isinstance(candidate, dict)
               and candidate.get("fixed_green_duration") == duration]
    if len(matches) != 1 or not isinstance(matches[0].get("rows"), list):
        raise ValueError("selected validation-tuned fixed baseline is invalid")
    rows = matches[0]["rows"]
    case_ids = [row.get("case_id") if isinstance(row, dict) else None
                for row in rows]
    expected = set(expected_case_ids)
    if len(case_ids) != len(expected) or set(case_ids) != expected:
        raise ValueError("exact validation cases must each appear once in fixed baseline")
    return dict(zip(case_ids, rows))


def validate_checkpoint_selection(validation, selection, tuning,
                                  expected_case_ids):
    """Recompute every validation score and reject incomplete/forged evidence."""
    if not isinstance(validation, dict) or not validation:
        raise ValueError("validation evidence is missing")
    if not isinstance(selection, dict):
        raise ValueError("checkpoint selection is invalid")
    if selection.get("eligibility_policy") != CHECKPOINT_ELIGIBILITY_POLICY:
        raise ValueError("checkpoint eligibility policy is missing or obsolete")
    expected = set(expected_case_ids)
    if not expected:
        raise ValueError("expected validation cases are missing")
    baseline_rows = _selected_tuned_baseline_rows(tuning, expected)
    recomputed_scores = {}
    for checkpoint_id, evidence in validation.items():
        if not isinstance(evidence, dict) or not isinstance(
                evidence.get("rows"), list):
            raise ValueError("validation checkpoint rows are missing")
        rows = evidence["rows"]
        case_ids = [row.get("case_id") if isinstance(row, dict) else None
                    for row in rows]
        if len(case_ids) != len(expected) or set(case_ids) != expected:
            raise ValueError(
                "exact validation cases must each appear once in checkpoint evidence")
        for row in rows:
            baseline = baseline_rows[row["case_id"]]
            expected_values = {
                "scenario": baseline.get("scenario"),
                "baseline_queue": baseline.get(
                    "queue_integral_vehicle_seconds"),
                "baseline_completion": baseline.get("completion_rate"),
                "baseline_insertion": baseline.get("insertion_rate"),
            }
            if any(row.get(field) != value
                   for field, value in expected_values.items()):
                raise ValueError(
                    "validation-tuned fixed baseline evidence drift")
        recomputed = score_validation(rows)
        reported = evidence.get("score")
        if isinstance(reported, dict) and "training_step" in reported:
            recomputed["training_step"] = reported["training_step"]
        if reported != recomputed:
            raise ValueError("validation checkpoint score was not recomputed from rows")
        recomputed_scores[checkpoint_id] = recomputed
    selected = selection.get("selected_checkpoint")
    if selected not in recomputed_scores:
        raise ValueError("selected checkpoint lacks validation evidence")
    if selection.get("score") != recomputed_scores[selected]:
        raise ValueError("selection score drifts from validation evidence")
    if (selection.get("status") != "eligible"
            or selection.get("eligible_for_test_evaluation") is not True
            or recomputed_scores[selected].get("eligible") is not True):
        raise ValueError("checkpoint selection is not validation-eligible")
    return selected
