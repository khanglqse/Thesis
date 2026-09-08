#!/usr/bin/env python3
"""Create the hashable 53-signal geometry used by the offline defense viewer."""

import argparse
import hashlib
import json
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet


ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha256(value):
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
