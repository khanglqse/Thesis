#!/usr/bin/env python3
"""Build the evidence-backed Da Nang pilot network and demand manifests."""

import hashlib
import json
import math
import shutil
import subprocess
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


def write_sumo_routes(network, demand, route_path):
    """Write deterministic SUMO route flows through the audited target junction."""
    route_path = Path(route_path)
    route_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("routes")
    vehicle_types = {
        "motorcycle": {"vClass": "motorcycle", "length": "2.0", "width": "0.8",
                       "accel": "3.5", "decel": "5.0", "minGap": "0.5",
                       "maxSpeed": "13.89", "sigma": "0.7", "minGapLat": "0.30",
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
    for kind in ("motorcycle", "car", "truck", "bus"):
        ET.SubElement(root, "vType", dict({"id": kind}, **vehicle_types[kind]))

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


def main():
    root = Path(__file__).resolve().parent.parent
    source = root / "datasets/danang_published"
    output = root / "results/research_pilot/generated"
    network = build_network(source / "osm/ntn_cmt8_29_20260907.osm",
                            output / "pilot.net.xml")
    demands = build_demand_files(source / "tran2025_peak_turning_movements.csv",
                                 source / "phan2025_camera_hourly_digitized.csv", output)
    for name, demand in demands.items():
        demand.update(write_sumo_routes(network, demand,
                                        output / ("%s.rou.xml" % name)))
    manifest = make_portable_manifest({"network": network, "demands": demands}, root)
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"network": network["network_path"],
                      "target_tls_id": network["target_tls_id"],
                      "cases": sorted(demands)}, indent=2))


if __name__ == "__main__":
    main()
