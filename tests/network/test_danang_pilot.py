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


def test_observed_camera_demands_keep_exact_digitized_vehicle_counts(tmp_path):
    from scripts import build_danang_pilot

    result = build_danang_pilot.build_observed_camera_demand_files(
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    assert result["am_peak"]["scheduled_vehicles"] == 2330
    assert result["normal"]["scheduled_vehicles"] == 1395
    assert result["pm_peak"]["scheduled_vehicles"] == 2400
    assert result["am_peak"]["observation_scope"] == "four digitized camera movement lines"
    assert {
        (row["approach"], row["destination"])
        for row in result["am_peak"]["movements"]
    } == {("SW", "NE"), ("SW", "NW"), ("NW", "SE"), ("NW", "NE")}
    assert sum(
        sum(row["vehicle_rates_per_hour"].values())
        for row in result["am_peak"]["movements"]
    ) == 2330


def test_scaled_demand_is_explicitly_labeled_synthetic():
    from scripts import build_danang_pilot

    source = {
        "case_id": "observed",
        "scheduled_vehicles": 100,
        "target_pcu_per_hour": 70.0,
        "movements": [{"target_pcu_per_hour": 70.0,
                       "vehicle_rates_per_hour": {"motorcycle": 80, "car": 20,
                                                   "truck": 0, "bus": 0}}],
    }
    scaled = build_danang_pilot.scale_demand(source, 1.25)
    assert scaled["scheduled_vehicles"] == 125
    assert scaled["target_pcu_per_hour"] == 87.5
    assert scaled["movements"][0]["vehicle_rates_per_hour"]["motorcycle"] == 100
    assert scaled["data_status"] == "synthetic_scale_sensitivity"
    assert source["scheduled_vehicles"] == 100


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


def test_explicit_demand_realizations_preserve_counts_but_change_departures(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_isolated_published_junction(
        tmp_path / "pilot.net.xml"
    )
    demands = build_danang_pilot.build_observed_camera_demand_files(
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    first = tmp_path / "seed11.rou.xml"
    second = tmp_path / "seed31.rou.xml"
    a = build_danang_pilot.write_sumo_vehicle_realization(
        network, demands["am_peak"], first, demand_seed=11
    )
    b = build_danang_pilot.write_sumo_vehicle_realization(
        network, demands["am_peak"], second, demand_seed=31
    )
    vehicles_a = ET.parse(first).getroot().findall("vehicle")
    vehicles_b = ET.parse(second).getroot().findall("vehicle")
    assert len(vehicles_a) == len(vehicles_b) == 2330
    assert a["route_sha256"] != b["route_sha256"]
    departures = [float(vehicle.attrib["depart"]) for vehicle in vehicles_a]
    assert departures == sorted(departures)
    assert [vehicle.attrib["type"] for vehicle in vehicles_a].count("motorcycle") == 1495


def test_motorcycle_sublane_sensitivity_case_is_executable(tmp_path):
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


def test_lane_model_heldout_rear_end_regression(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_isolated_published_junction(
        tmp_path / "base.net.xml"
    )
    published = tmp_path / "published.net.xml"
    build_danang_pilot.write_published_signal_network(network, published)
    demands = build_danang_pilot.build_observed_camera_demand_files(
        ROOT / "datasets/danang_published/phan2025_camera_hourly_digitized.csv",
        tmp_path,
    )
    route = tmp_path / "am_seed102.rou.xml"
    build_danang_pilot.write_sumo_vehicle_realization(
        network, demands["am_peak"], route, demand_seed=102
    )
    collision_output = tmp_path / "collisions.xml"
    completed = subprocess.run([
        "sumo", "--net-file", str(published), "--route-files", str(route),
        "--seed", "202", "--no-step-log", "true", "--time-to-teleport", "-1",
        "--collision.action", "warn", "--collision.check-junctions", "true",
        "--collision-output", str(collision_output), "--end", "1800",
    ], text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert not ET.parse(collision_output).getroot().findall("collision")


def test_published_signal_program_matches_103_second_cycle(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_network(
        ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm",
        tmp_path / "pilot.net.xml",
    )
    program = build_danang_pilot.build_published_signal_program(network)
    assert [phase["duration"] for phase in program] == [32, 7, 28, 7, 22, 7]
    assert sum(phase["duration"] for phase in program) == 103
    assert all(len(phase["state"]) == 21 for phase in program)
    assert [phase["kind"] for phase in program] == [
        "green", "yellow", "green", "yellow", "green", "yellow"
    ]


def test_published_signal_network_replaces_target_program(tmp_path):
    from scripts import build_danang_pilot

    network = build_danang_pilot.build_network(
        ROOT / "datasets/danang_published/osm/ntn_cmt8_29_20260907.osm",
        tmp_path / "pilot.net.xml",
    )
    output = tmp_path / "pilot_published.net.xml"
    build_danang_pilot.write_published_signal_network(network, output)
    programs = [node for node in ET.parse(output).getroot().findall("tlLogic")
                if node.attrib["id"] == network["target_tls_id"]]
    assert len(programs) == 1
    assert programs[0].attrib["programID"] == "published_103s"
    assert sum(int(phase.attrib["duration"]) for phase in programs[0].findall("phase")) == 103


def test_build_isolated_published_junction_has_auditable_geometry(tmp_path):
    from scripts import build_danang_pilot

    result = build_danang_pilot.build_isolated_published_junction(
        tmp_path / "danang_isolated.net.xml"
    )
    network = __import__("sumolib").net.readNet(result["network_path"], withPrograms=True)

    assert len(network.getTrafficLights()) == 1
    assert result["target_tls_id"] == "danang_ntn_cmt8_29"
    assert result["model_scope"] == "isolated_target_junction"
    assert result["approach_length_m"] == {
        "NW": pytest.approx(300, abs=1),
        "SE": pytest.approx(300, abs=1),
        "NE": pytest.approx(300, abs=1),
        "SW": pytest.approx(300, abs=1),
    }
    assert {
        direction: network.getEdge(edge_id).getLaneNumber()
        for direction, edge_id in result["incoming_edges"].items()
    } == {"NW": 2, "SE": 2, "NE": 3, "SW": 3}
    assert all(len(edges) == 1 for edges in result["route_edges"].values())
