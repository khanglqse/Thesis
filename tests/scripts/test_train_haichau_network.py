from scripts.train_haichau_network import _pilot_profile


def test_makefile_exposes_all_pinned_training_modes():
    makefile = open("Makefile").read()
    for mode in ("smoke", "pilot", "final"):
        assert "haichau-train-%s: haichau-foundation-verify" % mode in makefile
        assert "--mode %s --learning-seed $(LEARNING_SEED)" % mode in makefile


def test_five_seed_projection_uses_end_to_end_wall_time():
    summary = {
        "wall_time_seconds": 120.0,
        "baseline_tuning_wall_time_seconds": 80.0,
        "simulated_seconds_per_second": 2.0,
        "updates_per_second": 3.0,
        "validation_wall_time_seconds": 20.0,
    }

    profile = _pilot_profile(summary, learning_seed=11, peak_rss_kb=1000,
                             source_summary="summary.json")

    assert profile["measured_end_to_end_wall_time_seconds"] == 120.0
    assert profile["baseline_tuning_wall_time_seconds"] == 80.0
    assert profile["projected_five_seed_campaign_seconds"] == 600.0
