#!/usr/bin/env python3
"""Build the evidence-backed Da Nang pilot network and demand manifests."""

import hashlib
import csv
import copy
import json
import math
import random
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from traffic_rl.network.flow_gen import (
    load_danang_camera_presets,
    load_published_turning_movements,
)


TARGET_LON_LAT = (108.2210, 16.02622)
MAIN_INCOMING = {
    "NW": "693841066#17",
    "SE": "693841322#1",
    "NE": "693841069#0",
    "SW": "302763979#8",
}
MAIN_OUTGOING = {
    "NW": "-693841066#17",
    "SE": "1175814891#1",
    "NE": "693841068#1",
    "SW": "302763980#1",
}
PCU_FACTORS = {"motorcycle": 0.3, "car": 1.0, "bus": 2.0, "truck": 2.5}
MOVEMENT_BY_PAIR = {
    ("NW", "SE"): "through", ("NW", "SW"): "right", ("NW", "NE"): "left",
    ("SE", "NW"): "through", ("SE", "NE"): "right", ("SE", "SW"): "left",
    ("NE", "SW"): "through", ("NE", "NW"): "right", ("NE", "SE"): "left",
    ("SW", "NE"): "through", ("SW", "SE"): "right", ("SW", "NW"): "left",
}

PUBLISHED_APPROACH_LANES = {"NW": 2, "SE": 2, "NE": 3, "SW": 3}
ISOLATED_BOUNDARY_XY = {
    "NW": (-212.13, 212.13),
    "SE": (230.48, -192.03),
    "NE": (166.41, 249.62),
    "SW": (-257.25, -154.35),
}
CAMERA_MOVEMENT_PAIRS = {
    ("camera_01", "through"): ("SW", "NE"),
    ("camera_01", "left"): ("SW", "NW"),
    ("camera_02", "through"): ("NW", "SE"),
    ("camera_02", "left"): ("NW", "NE"),
}
SUMO_VEHICLE_TYPES = {
    "motorcycle": {"vClass": "motorcycle", "length": "2.0", "width": "0.8",
                   "accel": "3.5", "decel": "5.0", "minGap": "0.5",
                   "maxSpeed": "13.89", "sigma": "0.7", "tau": "1.2",
                   "minGapLat": "0.30",
                   "latAlignment": "compact", "lcSublane": "1.0", "lcPushy": "0.0"},
    "car": {"vClass": "passenger", "length": "5.0", "width": "1.8",
            "accel": "2.0", "decel": "4.5", "minGap": "2.5",
            "maxSpeed": "11.11", "sigma": "0.5"},
    "truck": {"vClass": "truck", "length": "8.0", "width": "2.5",
              "accel": "1.3", "decel": "4.0", "minGap": "3.0",
              "maxSpeed": "10.0", "sigma": "0.5"},
    "bus": {"vClass": "bus", "length": "12.0", "width": "2.5",
            "accel": "1.2", "decel": "4.0", "minGap": "3.0",
            "maxSpeed": "10.0", "sigma": "0.5"},
}


def make_portable_manifest(value, root):
    """Replace workspace-absolute paths with repository-relative paths."""
    root = Path(root).resolve()
    if isinstance(value, dict):
        return dict((key, make_portable_manifest(item, root))
                    for key, item in value.items())
    if isinstance(value, list):
        return [make_portable_manifest(item, root) for item in value]
    if isinstance(value, str):
        try:
            return str(Path(value).resolve().relative_to(root))
        except (ValueError, OSError):
            return value
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _distance(node, target_xy):
    x, y = node.getCoord()
    return math.hypot(x - target_xy[0], y - target_xy[1])


def _approach_chain(edge, target_xy, upstream, minimum_length=250.0):
    chain = [edge]
    total = edge.getLength()
    while total < minimum_length:
        endpoint = chain[0].getFromNode() if upstream else chain[-1].getToNode()
        candidates = list(chain[0].getIncoming() if upstream else chain[-1].getOutgoing())
        candidates = [candidate for candidate in candidates
                      if candidate not in chain and
                      _distance(candidate.getFromNode() if upstream else candidate.getToNode(),
                                target_xy) > _distance(endpoint, target_xy) + 0.01]
        if not candidates:
            break
        same_name = [candidate for candidate in candidates
                     if candidate.getName() == edge.getName()]
        candidates = same_name or candidates
        candidate = max(
            candidates,
            key=lambda item: _distance(
                item.getFromNode() if upstream else item.getToNode(), target_xy),
        )
        if upstream:
            chain.insert(0, candidate)
        else:
            chain.append(candidate)
        total += candidate.getLength()
    return chain, total


def build_network(osm_path, network_path):
    """Convert the pinned OSM extract and identify the four published approaches."""
    import sumolib

    osm_path = Path(osm_path).resolve()
    network_path = Path(network_path).resolve()
    network_path.parent.mkdir(parents=True, exist_ok=True)
    netconvert = shutil.which("netconvert")
    if not netconvert:
        raise RuntimeError("netconvert is required to build the SUMO pilot")
    command = [
        netconvert, "--osm-files", str(osm_path), "--output-file", str(network_path),
        "--output.street-names", "true", "--tls.guess", "true",
        "--junctions.join", "true", "--ramps.guess", "true",
        "--roundabouts.guess", "true", "--remove-edges.isolated", "true",
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError("netconvert failed: %s" % completed.stderr)

    network = sumolib.net.readNet(str(network_path), withPrograms=True)
    target_xy = network.convertLonLat2XY(*TARGET_LON_LAT)
    target = min(network.getNodes(), key=lambda node: _distance(node, target_xy))
    if target.getType() != "traffic_light":
        raise ValueError("nearest OSM junction is not signalized")

    incoming = {}
    outgoing = {}
    approach_lengths = {}
    route_edges = {}
    for direction, edge_id in MAIN_INCOMING.items():
        edge = network.getEdge(edge_id)
        chain, length = _approach_chain(edge, target.getCoord(), upstream=True)
        incoming[direction] = edge_id
        approach_lengths[direction] = length
        route_edges["in_" + direction] = [item.getID() for item in chain]
    for direction, edge_id in MAIN_OUTGOING.items():
        edge = network.getEdge(edge_id)
        chain, _ = _approach_chain(edge, target.getCoord(), upstream=False)
        outgoing[direction] = edge_id
        route_edges["out_" + direction] = [item.getID() for item in chain]

    return {
        "network_path": str(network_path),
        "network_sha256": _sha256(network_path),
        "osm_path": str(osm_path),
        "osm_sha256": _sha256(osm_path),
        "target_tls_id": target.getID(),
        "target_distance_m": _distance(target, target_xy),
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "approach_length_m": approach_lengths,
        "route_edges": route_edges,
        "netconvert_command": command,
        "netconvert_warnings": completed.stderr.splitlines(),
    }


def build_isolated_published_junction(network_path):
    """Build the published Da Nang target as an isolated 300 m junction.

    The orientation comes from the pinned OSM extract. Lane counts come from the
    site description in Phan et al. (2025): two lanes per Lethanhnghi/Hoaxuan
    approach and three per 2/9/Cachmangthang8 approach. Isolating the target
    prevents adjacent OSM junctions from confounding signal-controller results.
    """
    network_path = Path(network_path).resolve()
    network_path.parent.mkdir(parents=True, exist_ok=True)
    netconvert = shutil.which("netconvert")
    if not netconvert:
        raise RuntimeError("netconvert is required to build the SUMO pilot")

    with tempfile.TemporaryDirectory(prefix="danang-junction-") as directory:
        directory = Path(directory)
        nodes = ET.Element("nodes")
        ET.SubElement(nodes, "node", {
            "id": "danang_ntn_cmt8_29", "x": "0", "y": "0",
            "type": "traffic_light", "tlType": "static",
        })
        for direction, (x, y) in ISOLATED_BOUNDARY_XY.items():
            ET.SubElement(nodes, "node", {
                "id": "boundary_" + direction, "x": str(x), "y": str(y),
                "type": "priority",
            })
        node_path = directory / "nodes.nod.xml"
        ET.ElementTree(nodes).write(node_path, encoding="utf-8", xml_declaration=True)

        edges = ET.Element("edges")
        for direction in ("NW", "SE", "NE", "SW"):
            lane_count = str(PUBLISHED_APPROACH_LANES[direction])
            ET.SubElement(edges, "edge", {
                "id": "in_" + direction, "from": "boundary_" + direction,
                "to": "danang_ntn_cmt8_29", "numLanes": lane_count,
                "speed": "13.89",
            })
            ET.SubElement(edges, "edge", {
                "id": "out_" + direction, "from": "danang_ntn_cmt8_29",
                "to": "boundary_" + direction, "numLanes": lane_count,
                "speed": "13.89",
            })
        edge_path = directory / "edges.edg.xml"
        ET.ElementTree(edges).write(edge_path, encoding="utf-8", xml_declaration=True)

        connections = ET.Element("connections")
        for origin, destination in MOVEMENT_BY_PAIR:
            ET.SubElement(connections, "connection", {
                "from": "in_" + origin, "to": "out_" + destination,
            })
        connection_path = directory / "connections.con.xml"
        ET.ElementTree(connections).write(
            connection_path, encoding="utf-8", xml_declaration=True)

        command = [
            netconvert, "--node-files", str(node_path), "--edge-files", str(edge_path),
            "--connection-files", str(connection_path), "--output-file", str(network_path),
            "--no-turnarounds", "true",
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode:
            raise RuntimeError("netconvert failed: %s" % completed.stderr)

    incoming = dict((direction, "in_" + direction)
                    for direction in PUBLISHED_APPROACH_LANES)
    outgoing = dict((direction, "out_" + direction)
                    for direction in PUBLISHED_APPROACH_LANES)
    return {
        "network_path": str(network_path),
        "network_sha256": _sha256(network_path),
        "model_scope": "isolated_target_junction",
        "geometry_source": "pinned OSM approach bearings",
        "lane_count_source": "Phan et al. (2025) site description",
        "target_tls_id": "danang_ntn_cmt8_29",
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "approach_length_m": dict((key, math.hypot(*value))
                                  for key, value in ISOLATED_BOUNDARY_XY.items()),
        "route_edges": dict(
            [("in_" + key, [value]) for key, value in incoming.items()] +
            [("out_" + key, [value]) for key, value in outgoing.items()]
        ),
        "netconvert_command": command,
        "netconvert_warnings": completed.stderr.splitlines(),
    }


def _profile_totals(csv_path, hour):
    import csv

    totals = dict((kind, 0.0) for kind in PCU_FACTORS)
    with Path(csv_path).open(newline="") as stream:
        for row in csv.DictReader(stream):
            if row["hour_start"] != hour:
                continue
            totals["car"] += int(row["car_veh_per_h"])
            totals["motorcycle"] += int(row["motorcycle_veh_per_h"])
            totals["truck"] += int(row["truck_veh_per_h"])
            totals["bus"] += int(row["bus_veh_per_h"])
    return totals


def build_demand_files(turning_csv, camera_csv, output_dir):
    """Create provenance-rich demand manifests for normal, AM and PM cases."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    movements = load_published_turning_movements(turning_csv)
    presets = load_danang_camera_presets(camera_csv)
    am_pcu = presets["am_peak"]["derived_pcu_per_hour"]
    results = {}
    for name, preset in presets.items():
        class_counts = _profile_totals(camera_csv, preset["hour_start"])
        pcu_by_class = dict((kind, class_counts[kind] * factor)
                            for kind, factor in PCU_FACTORS.items())
        observed_pcu = sum(pcu_by_class.values())
        pcu_fractions = dict((kind, value / observed_pcu)
                             for kind, value in pcu_by_class.items())
        scale = observed_pcu / am_pcu
        target_pcu = 6171.0 * scale
        demand_movements = []
        scheduled = 0.0
        scheduled_motorcycles = 0.0
        for movement in movements:
            movement_pcu = movement["pcu_per_hour"] * scale
            vehicle_rates = dict(
                (kind, movement_pcu * pcu_fractions[kind] / PCU_FACTORS[kind])
                for kind in PCU_FACTORS)
            scheduled += sum(vehicle_rates.values())
            scheduled_motorcycles += vehicle_rates["motorcycle"]
            demand_movements.append({
                "approach": movement["approach"],
                "movement": movement["movement"],
                "destination": movement["destination"],
                "target_pcu_per_hour": movement_pcu,
                "vehicle_rates_per_hour": vehicle_rates,
                "observation_status": movement["observation_status"],
            })
        payload = {
            "case_id": "danang_%s" % name,
            "source_id": "phan2025_3dqn_danang",
            "source_scope": "four observed camera lines scaled to published 12-movement peak table",
            "hour_start": preset["hour_start"],
            "duration_seconds": 3600,
            "demand_scale_vs_am_peak": scale,
            "target_pcu_per_hour": target_pcu,
            "scheduled_vehicles": int(round(scheduled)),
            "motorcycle_share": scheduled_motorcycles / scheduled,
            "pcu_factors": PCU_FACTORS,
            "movements": demand_movements,
        }
        path = output_dir / ("demand_%s.json" % name)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        results[name] = dict(payload)
        results[name]["demand_path"] = str(path)
        results[name]["demand_sha256"] = _sha256(path)
    return results


def build_observed_camera_demand_files(camera_csv, output_dir):
    """Build the four directly observed movement-line demand cases.

    Values are digitized from Figures 17--18 of Phan et al. (2025). They are
    kept as vehicle counts by class and are not expanded to the eight movements
    outside the two published camera views.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    presets = load_danang_camera_presets(camera_csv)
    with Path(camera_csv).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    results = {}
    for name, preset in presets.items():
        movements = []
        scheduled = 0
        motorcycle_count = 0
        target_pcu = 0.0
        uncertainty = 0
        for row in rows:
            if row["hour_start"] != preset["hour_start"]:
                continue
            pair = CAMERA_MOVEMENT_PAIRS[(row["camera"], row["movement"])]
            rates = dict((kind, int(row[kind + "_veh_per_h"]))
                         for kind in PCU_FACTORS)
            count = sum(rates.values())
            scheduled += count
            motorcycle_count += rates["motorcycle"]
            target_pcu += float(row["derived_pcu_per_h"])
            uncertainty += int(row["digitization_uncertainty_veh_per_h"])
            movements.append({
                "approach": pair[0],
                "movement": row["movement"],
                "destination": pair[1],
                "target_pcu_per_hour": float(row["derived_pcu_per_h"]),
                "vehicle_rates_per_hour": rates,
                "observation_status": "digitized_from_published_camera_figure",
                "camera": row["camera"],
            })
        payload = {
            "case_id": "danang_observed_%s" % name,
            "source_id": "phan2025_camera_profile",
            "observation_scope": "four digitized camera movement lines",
            "hour_start": preset["hour_start"],
            "duration_seconds": 3600,
            "target_pcu_per_hour": target_pcu,
            "scheduled_vehicles": scheduled,
            "motorcycle_share": motorcycle_count / scheduled,
            "digitization_uncertainty_veh_per_hour": uncertainty,
            "pcu_factors": PCU_FACTORS,
            "movements": movements,
        }
        path = output_dir / ("demand_observed_%s.json" % name)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        results[name] = dict(payload)
        results[name]["demand_path"] = str(path)
        results[name]["demand_sha256"] = _sha256(path)
    return results


def scale_demand(demand, scale):
    """Return a labeled synthetic sensitivity case at a demand multiplier."""
    result = copy.deepcopy(demand)
    scale = float(scale)
    result["case_id"] = "%s_scale_%g" % (demand["case_id"], scale)
    result["demand_scale"] = scale
    result["data_status"] = "synthetic_scale_sensitivity"
    result["target_pcu_per_hour"] = demand["target_pcu_per_hour"] * scale
    scheduled = 0.0
    motorcycles = 0.0
    for movement in result["movements"]:
        movement["target_pcu_per_hour"] *= scale
        for kind in movement["vehicle_rates_per_hour"]:
            movement["vehicle_rates_per_hour"][kind] *= scale
        scheduled += sum(movement["vehicle_rates_per_hour"].values())
        motorcycles += movement["vehicle_rates_per_hour"].get("motorcycle", 0)
    result["scheduled_vehicles"] = int(round(scheduled))
    result["motorcycle_share"] = motorcycles / scheduled if scheduled else 0.0
    return result


def write_sumo_routes(network, demand, route_path):
    """Write deterministic SUMO route flows through the audited target junction."""
    route_path = Path(route_path)
    route_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")
    for kind in ("motorcycle", "car", "truck", "bus"):
        ET.SubElement(root, "vType", dict({"id": kind}, **SUMO_VEHICLE_TYPES[kind]))

    for movement in demand["movements"]:
        origin = movement["approach"]
        destination = movement["destination"]
        route_id = "%s_%s" % (origin, destination)
        edges = (network["route_edges"]["in_" + origin] +
                 network["route_edges"]["out_" + destination])
        ET.SubElement(root, "route", {"id": route_id, "edges": " ".join(edges)})
        for kind in ("motorcycle", "car", "truck", "bus"):
            rate = movement["vehicle_rates_per_hour"][kind]
            if rate <= 0:
                continue
            ET.SubElement(root, "flow", {
                "id": "%s_%s" % (route_id, kind),
                "type": kind,
                "route": route_id,
                "begin": "0",
                "end": str(demand["duration_seconds"]),
                "vehsPerHour": "%.6f" % rate,
                "departLane": "best",
                "departPos": "random_free",
                "departSpeed": "max",
            })
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(route_path), encoding="utf-8", xml_declaration=True)
    return {"route_path": str(route_path), "route_sha256": _sha256(route_path)}


def write_sumo_vehicle_realization(network, demand, route_path, demand_seed):
    """Write an explicit, count-preserving departure realization for one seed."""
    route_path = Path(route_path)
    route_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")
    for kind in ("motorcycle", "car", "truck", "bus"):
        ET.SubElement(root, "vType", dict({"id": kind}, **SUMO_VEHICLE_TYPES[kind]))

    rng = random.Random(int(demand_seed))
    vehicles = []
    duration = float(demand["duration_seconds"])
    for movement in demand["movements"]:
        origin = movement["approach"]
        destination = movement["destination"]
        route_id = "%s_%s" % (origin, destination)
        edges = (network["route_edges"]["in_" + origin] +
                 network["route_edges"]["out_" + destination])
        ET.SubElement(root, "route", {"id": route_id, "edges": " ".join(edges)})
        for kind in ("motorcycle", "car", "truck", "bus"):
            count = int(round(movement["vehicle_rates_per_hour"][kind] *
                              duration / 3600.0))
            for index in range(count):
                depart = (index + rng.random()) * duration / max(count, 1)
                vehicles.append((depart, {
                    "id": "%s_%s_%04d" % (route_id, kind, index),
                    "type": kind,
                    "route": route_id,
                    "depart": "%.3f" % depart,
                    "departLane": "best",
                    "departPos": "random_free",
                    "departSpeed": "max",
                }))
    for _, attributes in sorted(vehicles, key=lambda item: item[0]):
        ET.SubElement(root, "vehicle", attributes)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(route_path), encoding="utf-8", xml_declaration=True)
    return {"route_path": str(route_path), "route_sha256": _sha256(route_path),
            "demand_seed": int(demand_seed), "scheduled_vehicles": len(vehicles)}


def build_published_signal_program(network_metadata):
    """Map Figure 4's three greens and 7-second clearances to SUMO links."""
    import sumolib

    network = sumolib.net.readNet(network_metadata["network_path"], withPrograms=True)
    tls = network.getTLS(network_metadata["target_tls_id"])
    state_size = max(connection[2] for connection in tls.getConnections()) + 1

    pair_links = {}
    for origin, incoming_id in network_metadata["incoming_edges"].items():
        incoming = network.getEdge(incoming_id)
        for destination, outgoing_id in network_metadata["outgoing_edges"].items():
            if origin == destination:
                continue
            outgoing = network.getEdge(outgoing_id)
            pair_links[(origin, destination)] = [
                connection.getTLLinkIndex()
                for connection in incoming.getOutgoing().get(outgoing, [])
            ]

    def green_state(action):
        state = ["r"] * state_size
        for pair, movement in MOVEMENT_BY_PAIR.items():
            origin = pair[0]
            enabled = False
            permissive = False
            if movement == "right":
                enabled, permissive = True, True
            elif action == 0 and origin in ("NW", "SE"):
                enabled, permissive = True, movement == "left"
            elif action == 1 and origin in ("NE", "SW") and movement == "through":
                enabled = True
            elif action == 2 and origin in ("NE", "SW") and movement == "left":
                enabled = True
            if enabled:
                for link_index in pair_links[pair]:
                    state[link_index] = "g" if permissive else "G"
        return "".join(state)

    durations = (32, 28, 22)
    phases = []
    for action, duration in enumerate(durations):
        green = green_state(action)
        phases.append({"duration": duration, "state": green,
                       "kind": "green", "action": action})
        phases.append({"duration": 7,
                       "state": "".join("y" if value in "Gg" else "r"
                                        for value in green),
                       "kind": "yellow", "action": action})
    return phases


def write_published_signal_network(network_metadata, output_path):
    """Replace the target OSM TLS with the published 103-second program."""
    output_path = Path(output_path)
    tree = ET.parse(network_metadata["network_path"])
    root = tree.getroot()
    matches = [node for node in root.findall("tlLogic")
               if node.attrib.get("id") == network_metadata["target_tls_id"]]
    if not matches:
        raise ValueError("target tlLogic not found in SUMO network")
    insertion_index = list(root).index(matches[0])
    for node in matches:
        root.remove(node)
    program = ET.Element("tlLogic", {
        "id": network_metadata["target_tls_id"],
        "type": "static",
        "programID": "published_103s",
        "offset": "0",
    })
    for phase in build_published_signal_program(network_metadata):
        ET.SubElement(program, "phase", {
            "duration": str(phase["duration"]), "state": phase["state"]})
    root.insert(insertion_index, program)
    ET.indent(tree, space="    ")
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
    return {"published_network_path": str(output_path),
            "published_network_sha256": _sha256(output_path),
            "published_signal_program": build_published_signal_program(network_metadata)}


def main():
    root = Path(__file__).resolve().parent.parent
    source = root / "datasets/danang_published"
    output = root / "results/research_pilot/generated"
    osm_network = build_network(source / "osm/ntn_cmt8_29_20260907.osm",
                                output / "pilot.net.xml")
    osm_network.update(write_published_signal_network(
        osm_network, output / "pilot_published.net.xml"))
    network = build_isolated_published_junction(output / "danang_isolated.net.xml")
    network.update(write_published_signal_network(
        network, output / "danang_isolated_published.net.xml"))
    demands = build_demand_files(source / "tran2025_peak_turning_movements.csv",
                                 source / "phan2025_camera_hourly_digitized.csv", output)
    observed_demands = build_observed_camera_demand_files(
        source / "phan2025_camera_hourly_digitized.csv", output)
    for name, demand in demands.items():
        demand.update(write_sumo_routes(network, demand,
                                        output / ("estimated_%s.rou.xml" % name)))
    for name, demand in observed_demands.items():
        demand.update(write_sumo_routes(
            network, demand, output / ("observed_%s.rou.xml" % name)))
    manifest = make_portable_manifest({
        "network": network,
        "osm_reference_network": osm_network,
        "estimated_full_intersection_demands": demands,
        "observed_camera_demands": observed_demands,
    }, root)
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"network": network["network_path"],
                      "target_tls_id": network["target_tls_id"],
                      "estimated_cases": sorted(demands),
                      "observed_cases": sorted(observed_demands)}, indent=2))


if __name__ == "__main__":
    main()
