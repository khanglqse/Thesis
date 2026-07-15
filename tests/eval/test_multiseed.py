from traffic_rl.eval.multiseed import summary_stats, aggregate_seeds


def test_summary_stats_basic():
    s = summary_stats([2.0, 4.0, 6.0])
    assert s["mean"] == 4.0 and s["n"] == 3
    assert abs(s["std"] - 1.632993) < 1e-4        # population std (ddof=0)
    assert s["ci95"] > 0


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
