import json

from traffic_rl.report import loader

COMPARISON = {
    "table": [
        {"controller": "MaxPressure", "agents": 105, "steps": 1000,
         "final_average_travel_time": 118.79, "final_vehicle_count": 4968,
         "mean_total_queue": 278.98, "mean_reward": -0.2258},
        {"controller": "DQN", "agents": 105, "steps": 1000,
         "final_average_travel_time": 119.64, "final_vehicle_count": 4938,
         "mean_total_queue": 274.26, "mean_reward": -0.1772},
        {"controller": "FixedTime", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.44, "final_vehicle_count": 5135,
         "mean_total_queue": 422.92, "mean_reward": -0.8105},
        {"controller": "Random", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.89, "final_vehicle_count": 5156,
         "mean_total_queue": 434.98, "mean_reward": -0.8461},
    ],
    "best_controller": "MaxPressure",
    "improvement_vs_fixed_pct": 1.477,
}


def test_load_json_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(COMPARISON))
    assert loader.load_json(str(p)) == COMPARISON


def test_best_per_metric():
    best = loader.best_per_metric(COMPARISON)
    assert best["travel_time"] == "MaxPressure"   # lowest travel time
    assert best["queue"] == "DQN"                  # lowest queue
    assert best["reward"] == "DQN"                 # highest (least negative) reward


def test_improvements_vs_fixed():
    imp = loader.improvements_vs_fixed(COMPARISON)
    # DQN travel time better than FixedTime -> positive percentage
    assert imp["DQN"]["travel_time_pct"] > 0
    # DQN queue much better than FixedTime (274 vs 423) -> ~35%
    assert 30 < imp["DQN"]["queue_pct"] < 40
    # DQN reward better (less negative) than FixedTime -> positive
    assert imp["DQN"]["reward_pct"] > 0
    # FixedTime vs itself is exactly 0
    assert imp["FixedTime"]["travel_time_pct"] == 0
    assert imp["FixedTime"]["queue_pct"] == 0
    assert imp["FixedTime"]["reward_pct"] == 0


def test_improvements_handles_missing_fixed():
    no_fixed = {"table": [r for r in COMPARISON["table"]
                          if r["controller"] != "FixedTime"]}
    assert loader.improvements_vs_fixed(no_fixed) == {}
