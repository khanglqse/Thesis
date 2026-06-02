from traffic_rl.eval.compare import aggregate, cumulative_wait_hours


def test_cumulative_wait_hours():
    # 3 decisions, 360 vehicles waiting each, 10s interval -> 1 veh-h per decision
    cum = cumulative_wait_hours([360, 360, 360], action_interval=10)
    assert len(cum) == 3
    assert abs(cum[0] - 1.0) < 1e-9        # 360*10/3600 = 1.0
    assert abs(cum[-1] - 3.0) < 1e-9       # running total
    assert cumulative_wait_hours([]) == []

def test_aggregate_builds_table_and_best():
    rows = [
        {"controller": "Random", "final_average_travel_time": 400.0, "mean_total_queue": 50},
        {"controller": "FixedTime", "final_average_travel_time": 360.0, "mean_total_queue": 40},
        {"controller": "MaxPressure", "final_average_travel_time": 300.0, "mean_total_queue": 30},
        {"controller": "DQN", "final_average_travel_time": 290.0, "mean_total_queue": 28},
    ]
    out = aggregate(rows)
    assert out["best_controller"] == "DQN"      # lowest travel time
    assert out["table"][0]["controller"] in {"Random", "FixedTime", "MaxPressure", "DQN"}
    assert round(out["improvement_vs_fixed_pct"], 2) == round((360.0 - 290.0) / 360.0 * 100, 2)
