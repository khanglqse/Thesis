from traffic_rl.report import chapter4

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
TRAIN_LOG = {
    "episodes": [
        {"episode": 0, "mean_reward": -0.778, "mean_total_queue": 422.74,
         "mean_loss": 26.17, "final_average_travel_time": 121.53, "epsilon": 0.968},
        {"episode": 47, "mean_reward": -0.270, "mean_total_queue": 286.1,
         "mean_loss": 3.4, "final_average_travel_time": 119.7, "epsilon": 0.05},
    ]
}


def test_build_chapter4_is_english_markdown():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG)
    assert md.startswith("# Chapter 4")
    # Section headings present
    for heading in ["Experimental Setup", "Baseline", "Training",
                    "Results", "Analysis", "Limitations"]:
        assert heading in md
    # Markdown comparison table with every controller
    for ctrl in ["MaxPressure", "DQN", "FixedTime", "Random"]:
        assert ctrl in md
    # Real numbers rendered
    assert "105" in md            # agent count
    assert "274.26" in md         # DQN queue
    # Figures referenced
    assert "comparison_metrics.png" in md
    assert "training_curve.png" in md


def test_build_chapter4_reports_training_progress():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG)
    # First->last episode queue reduction should be mentioned (422.74 -> 286.1)
    assert "422" in md
    assert "286" in md


def test_build_chapter4_custom_fig_dir():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG, fig_dir="figs")
    assert "figs/comparison_metrics.png" in md
