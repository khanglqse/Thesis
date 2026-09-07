from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).parents[2]


def test_portable_manifest_removes_workspace_absolute_paths():
    from scripts import build_danang_pilot

    portable = build_danang_pilot.make_portable_manifest(
        {"network_path": str(ROOT / "results/research_pilot/generated/pilot.net.xml")},
        ROOT,
    )
    assert portable == {"network_path": "results/research_pilot/generated/pilot.net.xml"}


@pytest.mark.skipif(not (ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm").exists(),
                    reason="versioned OSM pilot snapshot unavailable")
def test_build_pilot_network_finds_the_published_signal_and_four_approaches(tmp_path):
    from scripts import build_danang_pilot

    result = build_danang_pilot.build_network(
        ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm",
        tmp_path / "pilot.net.xml",
    )
    assert Path(result["network_path"]).exists()
    assert result["target_tls_id"]
    assert result["target_distance_m"] < 10
    assert set(result["incoming_edges"]) == {"NW", "NE", "SE", "SW"}
    assert set(result["outgoing_edges"]) == {"NW", "NE", "SE", "SW"}
    assert all(length >= 250 for length in result["approach_length_m"].values())


def test_demand_presets_preserve_pcu_and_report_scheduled_vehicle_counts(tmp_path):
    from scripts import build_danang_pilot

    result = build_danang_pilot.build_demand_files(
        ROOT / "datasets/danang_published/tran2025_peak_turning_movements.csv",
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    assert set(result) == {"normal", "am_peak", "pm_peak"}
    assert result["am_peak"]["target_pcu_per_hour"] == 6171.0
    assert result["normal"]["target_pcu_per_hour"] < result["am_peak"]["target_pcu_per_hour"]
    assert result["pm_peak"]["scheduled_vehicles"] > result["normal"]["scheduled_vehicles"]
    assert result["am_peak"]["motorcycle_share"] > 0.5
    assert all(Path(row["demand_path"]).exists() for row in result.values())


def test_sumo_routes_cover_twelve_movements_and_four_vehicle_classes(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_network(
        ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm",
        tmp_path / "pilot.net.xml",
    )
    demands = build_danang_pilot.build_demand_files(
        ROOT / "datasets/danang_published/tran2025_peak_turning_movements.csv",
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    route_path = tmp_path / "am_peak.rou.xml"
    build_danang_pilot.write_sumo_routes(network, demands["am_peak"], route_path)
    root = ET.parse(route_path).getroot()
    assert len(root.findall("route")) == 12
    assert len(root.findall("vType")) == 4
    assert len(root.findall("flow")) == 36  # no buses were plotted at the 08:00 preset
    assert {flow.attrib["type"] for flow in root.findall("flow")} == {
        "motorcycle", "car", "truck"
    }
    completed = subprocess.run(
        ["sumo", "--net-file", network["network_path"], "--route-files", str(route_path),
         "--lateral-resolution", "0.4", "--no-step-log", "true", "--end", "1"],
        text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_motorcycle_sublane_smoke_has_no_collision_teleports(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_network(
        ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm",
        tmp_path / "pilot.net.xml",
    )
    demands = build_danang_pilot.build_demand_files(
        ROOT / "datasets/danang_published/tran2025_peak_turning_movements.csv",
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    route_path = tmp_path / "am_peak.rou.xml"
    build_danang_pilot.write_sumo_routes(network, demands["am_peak"], route_path)
    completed = subprocess.run(
        ["sumo", "--net-file", network["network_path"], "--route-files", str(route_path),
         "--lateral-resolution", "0.4", "--seed", "1", "--no-step-log", "true",
         "--duration-log.statistics", "true", "--end", "300"],
        text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Teleporting vehicle" not in completed.stderr
    assert "Teleports:" not in completed.stdout
