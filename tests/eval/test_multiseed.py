from traffic_rl.eval.multiseed import summary_stats, aggregate_seeds


def test_summary_stats_basic():
    s = summary_stats([2.0, 4.0, 6.0])
    assert s["mean"] == 4.0 and s["n"] == 3
    assert abs(s["std"] - 2.0) < 1e-6             # sample std (ddof=1), not population
    assert s["ci95"] > 0


def test_summary_stats_ci95_uses_student_t_for_five_seeds():
    # Five seeds -> df=4, t(0.975, 4)=2.776. For [1,2,3,4,5] the sample std (ddof=1)
    # is 1.581139, so the correct small-sample CI is
    #   2.776 * 1.581139 / sqrt(5) = 1.9629,
    # NOT the normal-approx population-std value 1.96*1.41421/sqrt(5) = 1.2396.
    s = summary_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(s["ci95"] - 1.9629) < 1e-2


def test_summary_stats_single_value_no_ci():
    s = summary_stats([7.0])
    assert s["mean"] == 7.0 and s["n"] == 1 and s["ci95"] == 0.0


def test_aggregate_seeds_groups_by_controller():
    seed0 = [{"controller": "DQN", "mean_total_queue": 100.0,
              "queue_series": [10.0] * 6, "final_average_travel_time": 5.0}]
    seed1 = [{"controller": "DQN", "mean_total_queue": 120.0,
              "queue_series": [12.0] * 6, "final_average_travel_time": 5.0}]
    out = aggregate_seeds([seed0, seed1])
    assert out["DQN"]["mean_total_queue"]["mean"] == 110.0
    assert out["DQN"]["wait_hours"]["n"] == 2
    # wait_hours = last cumulative of queue*10/3600; seed0=6*10*10/3600, seed1=6*12*10/3600
    assert out["DQN"]["wait_hours"]["mean"] > 0


def test_aggregate_uses_per_step_queue_integral_when_available():
    row = {"controller": "DQN", "mean_total_queue": 999.0,
           "queue_series": [999.0] * 10,
           "queue_integral_vehicle_hours": 0.25,
           "final_average_travel_time": 5.0}
    out = aggregate_seeds([[row]])
    assert out["DQN"]["wait_hours"]["mean"] == 0.25
