#!/usr/bin/env python3
"""Create the hashable 53-signal geometry used by the offline defense viewer."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet


ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha256(value):
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _physical_geometry(root, roadnet_path, roadnet, controlled_ids):
    """Return source-backed street, lane, junction and phase geometry."""
    sumo_path = root / "datasets/haichau_network_v2/source/danang_haichau.net.xml"
    names = {}
    if sumo_path.is_file():
        for edge in ET.parse(str(sumo_path)).getroot().iter("edge"):
            edge_id = edge.get("id")
            if edge_id and edge.get("name"):
                names[edge_id] = edge.get("name")

    roads = []
    xs, ys = [], []
    for road in roadnet.get("roads", ()):
        points = [[float(point["x"]), float(point["y"])]
                  for point in road.get("points", ())]
        for x, y in points:
            xs.append(x)
            ys.append(y)
        lanes = [{
            "id": "%s_%d" % (road["id"], index),
            "index": index,
            "width": float(lane.get("width", 0.0)),
            "max_speed": float(lane.get("maxSpeed", 0.0)),
        } for index, lane in enumerate(road.get("lanes", ()))]
        roads.append({
            "id": road["id"], "name": names.get(road["id"]),
            "start": road["startIntersection"],
            "end": road["endIntersection"], "points": points,
            "lanes": lanes,
        })

    junctions = []
    for inter in roadnet.get("intersections", ()):
        point = inter.get("point", {})
        if "x" not in point or "y" not in point:
            continue
        light = inter.get("trafficLight", {})
        movements = []
        for index, link in enumerate(inter.get("roadLinks", ())):
            movements.append({
                "index": index, "type": link.get("type"),
                "start_road": link.get("startRoad"),
                "end_road": link.get("endRoad"),
                "lane_links": [{
                    "start_lane": "%s_%d" % (
                        link.get("startRoad"), lane.get("startLaneIndex")),
                    "end_lane": "%s_%d" % (
                        link.get("endRoad"), lane.get("endLaneIndex")),
                    "points": [[float(p["x"]), float(p["y"])]
                               for p in lane.get("points", ())],
                } for lane in link.get("laneLinks", ())],
            })
        road_by_id = dict((road["id"], road) for road in roads)
        road_ids = list(inter.get("roads", ()))
        junctions.append({
            "id": inter["id"], "x": float(point["x"]),
            "y": float(point["y"]), "controlled": inter["id"] in controlled_ids,
            "virtual": bool(inter.get("virtual", False)),
            "incoming_roads": [road_id for road_id in road_ids
                               if road_by_id.get(road_id, {}).get("end") == inter["id"]],
            "outgoing_roads": [road_id for road_id in road_ids
                               if road_by_id.get(road_id, {}).get("start") == inter["id"]],
            "movements": movements,
            "phases": [{
                "index": index, "duration": float(phase.get("time", 0.0)),
                "available_movements": list(phase.get("availableRoadLinks", ())),
            } for index, phase in enumerate(light.get("lightphases", ()))],
        })
    return {
        "source_path": str(roadnet_path.relative_to(root)),
        "source_sha256": _sha256(roadnet_path),
        "sumo_source_path": (str(sumo_path.relative_to(root))
                             if sumo_path.is_file() else None),
        "sumo_source_sha256": (_sha256(sumo_path) if sumo_path.is_file() else None),
        "coordinate_units": "CityFlow local metres",
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
        "roads": roads, "junctions": junctions,
    }


def build_viewer(project_root, manifest_path, output_path):
    root = Path(project_root).resolve()
    manifest_path = (root / manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    network_record = manifest.get("network", {})
    roadnet_path = (root / network_record.get("path", "")).resolve()
    if _sha256(roadnet_path) != network_record.get("sha256"):
        raise ValueError("network hash drift")
    roadnet = json.loads(roadnet_path.read_text())
    parsed_roadnet = RoadNet.load(str(roadnet_path))
    agent_ids = list(network_record.get("agent_ids", ()))
    if len(agent_ids) != 53 or len(set(agent_ids)) != 53:
        raise ValueError("manifest must identify exactly 53 signals")
    intersections = dict((item["id"], item)
                         for item in roadnet.get("intersections", ()))
    known = set(agent_ids)
    adjacency = network_record.get("signal_adjacency")
    if adjacency != parsed_roadnet.signal_adjacency():
        raise ValueError("manifest signal adjacency drift")
    if set(adjacency.get("upstream", {})) != known \
            or set(adjacency.get("downstream", {})) != known:
        raise ValueError("signal adjacency node coverage differs from manifest")
    neighbor_sets = dict((node_id, set()) for node_id in agent_ids)
    links = set()
    for edge in adjacency.get("directed_edges", ()):
        if (not isinstance(edge, list) or len(edge) != 2
                or edge[0] not in known or edge[1] not in known
                or edge[0] == edge[1]):
            raise ValueError("signal adjacency contains invalid edge")
        source, target = edge
        links.add((source, target))
        neighbor_sets[source].add(target)
        neighbor_sets[target].add(source)
    adjacency_sha256 = _canonical_sha256(adjacency)
    if network_record.get("signal_adjacency_sha256") != adjacency_sha256:
        raise ValueError("manifest signal adjacency hash drift")
    nodes = []
    for node_id in agent_ids:
        point = intersections.get(node_id, {}).get("point", {})
        try:
            x, y = float(point["x"]), float(point["y"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("signal coordinates are missing: %s" % node_id)
        nodes.append({
            "id": node_id, "name": "Signal %s" % node_id,
            "x": x, "y": y, "neighbors": sorted(neighbor_sets[node_id]),
        })
    document = {
        "schema_version": 1,
        "controlled_signals": 53,
        "coordinate_units": "CityFlow roadnet coordinates",
        "signal_adjacency_sha256": adjacency_sha256,
        "signal_adjacency_policy": adjacency["policy"],
        "signal_adjacency_stats": adjacency["stats"],
        "nodes": nodes,
        "links": [{"source": source, "target": target}
                  for source, target in sorted(links)],
        "geometry": _physical_geometry(root, roadnet_path, roadnet, known),
    }
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    target = (root / output_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("viewer output must remain inside project root")
    if target.exists() and target.read_text() != encoded:
        raise ValueError("refusing to replace different viewer geometry")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(encoded)
    return {"path": str(target.relative_to(root)), "sha256": _sha256(target),
            "controlled_signals": 53, "links": len(links),
            "signal_adjacency_sha256": adjacency_sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(ROOT))
    parser.add_argument(
        "--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument(
        "--output", default="results/haichau_network_v2/release-inputs/viewer-network.json")
    args = parser.parse_args(argv)
    print(json.dumps(build_viewer(
        args.project_root, args.manifest, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
