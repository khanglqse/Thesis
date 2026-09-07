import pytest


def test_rl_summary_uses_training_seed_as_the_independent_unit():
    from traffic_rl.report.danang import summarize_metric

    rows = [
        {"train_seed": 1, "queue": 10.0},
        {"train_seed": 1, "queue": 14.0},
        {"train_seed": 2, "queue": 20.0},
        {"train_seed": 2, "queue": 24.0},
    ]
    result = summarize_metric(rows, "queue", learning_controller=True)
    assert result["n_independent"] == 2
    assert result["mean"] == 17.0
    assert result["independent_values"] == [12.0, 22.0]


def test_paired_rl_effect_averages_demands_within_training_seed():
    from traffic_rl.report.danang import paired_effect

    baseline = [
        {"demand_seed": 101, "queue": 20.0},
        {"demand_seed": 102, "queue": 30.0},
    ]
    rl = [
        {"train_seed": 1, "demand_seed": 101, "queue": 10.0},
        {"train_seed": 1, "demand_seed": 102, "queue": 20.0},
        {"train_seed": 2, "demand_seed": 101, "queue": 15.0},
        {"train_seed": 2, "demand_seed": 102, "queue": 25.0},
    ]
    result = paired_effect(rl, baseline, "queue")
    assert result["n_independent"] == 2
    assert result["mean_difference"] == -7.5
    assert result["relative_change_percent"] == pytest.approx(-30.0)
