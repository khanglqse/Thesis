from pathlib import Path

from traffic_rl.network import flow_gen


DATA = Path(__file__).parents[2] / "datasets" / "danang_published"


def test_peak_turning_table_has_twelve_movements_and_published_total():
    load = getattr(flow_gen, "load_published_turning_movements")
    rows = load(DATA / "tran2025_peak_turning_movements.csv")
    assert len(rows) == 12
    assert sum(row["pcu_per_hour"] for row in rows) == 6171
    assert {(row["approach"], row["movement"]) for row in rows} == {
        (approach, movement)
        for approach in ("NW", "SE", "NE", "SW")
        for movement in ("left", "through", "right")
    }


def test_camera_profile_exposes_normal_am_and_pm_vehicle_counts():
    load = getattr(flow_gen, "load_danang_camera_presets")
    presets = load(DATA / "phan2025_camera_hourly_digitized.csv")
    assert presets["normal"]["hour_start"] == "13:00"
    assert presets["am_peak"]["hour_start"] == "08:00"
    assert presets["pm_peak"]["hour_start"] == "17:00"
    assert presets["normal"]["observed_vehicle_count_per_hour"] == 1395
    assert presets["am_peak"]["observed_vehicle_count_per_hour"] == 2330
    assert presets["pm_peak"]["observed_vehicle_count_per_hour"] == 2400


def test_camera_profile_keeps_observed_scope_and_digitization_uncertainty():
    load = getattr(flow_gen, "load_danang_camera_presets")
    normal = load(DATA / "phan2025_camera_hourly_digitized.csv")["normal"]
    assert normal["covered_movements"] == 4
    assert normal["scope"] == "four_camera_counting_lines"
    assert normal["digitization_uncertainty_vehicle_per_hour"] > 0
