#!/usr/bin/env python3
"""
Download OpenStreetMap road network for Da Nang, Vietnam.
Saves GraphML (for later conversion to CityFlow) and optionally GeoJSON.
Requires: pip install osmnx
"""
from pathlib import Path
import sys

# Project root = parent of scripts/
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "osm_danang"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    try:
        import osmnx as ox
    except ImportError:
        print("Install osmnx first: pip install osmnx", file=sys.stderr)
        sys.exit(1)

    # Bbox (left, bottom, right, top) = (west, south, east, north). Da Nang center ~8km.
    bbox = (108.12, 16.00, 108.28, 16.08)
    print("Downloading OSM road network for: Da Nang (center bbox)")
    print("(This may take 1–2 minutes...)")

    G = ox.graph_from_bbox(bbox, network_type="drive", simplify=True)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    print(f"Nodes: {n_nodes}, Edges: {n_edges}")

    graphml_path = OUT_DIR / "danang_roads.graphml"
    ox.save_graphml(G, graphml_path)
    print(f"Saved: {graphml_path}")

    # Optional: save as GeoJSON for inspection (nodes + edges)
    try:
        gdf_nodes = ox.graph_to_gdfs(G, edges=False)
        gdf_edges = ox.graph_to_gdfs(G, nodes=False)
        nodes_geojson = OUT_DIR / "danang_nodes.geojson"
        edges_geojson = OUT_DIR / "danang_edges.geojson"
        gdf_nodes.to_file(nodes_geojson, driver="GeoJSON")
        gdf_edges.to_file(edges_geojson, driver="GeoJSON")
        print(f"Saved: {nodes_geojson}, {edges_geojson}")
    except Exception as e:
        print(f"GeoJSON export skipped: {e}")

    print("Done. Use danang_roads.graphml for OSM -> CityFlow conversion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
