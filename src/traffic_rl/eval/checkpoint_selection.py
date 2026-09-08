"""Validation-only checkpoint scoring for the Hai Chau network policy."""


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

    scenario_regrets = {
        scenario: sum(values) / len(values)
        for scenario, values in by_scenario.items()
    }
    regrets = list(scenario_regrets.values())
    normal_regret = scenario_regrets.get("normal", float("inf"))
    max_completion_degradation = max(completion_degradations or [0.0])
    return {
        "worst_regret": max(regrets),
        "mean_regret": sum(regrets) / len(regrets),
        "normal_regret": normal_regret,
        "max_completion_degradation": max_completion_degradation,
        "scenario_regrets": scenario_regrets,
        "eligible": bool(normal_regret <= 0.0
                         and max_completion_degradation <= 0.02),
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
