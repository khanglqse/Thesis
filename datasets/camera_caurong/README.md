# OSM extract around the Tay Cau Rong junction

Base map for `scripts/plot_camera_markov_map.py`. The extract was downloaded on 2026-10-05 with osmnx from the Overpass API, bbox `(108.2185, 16.0588, 108.2275, 16.0636)`.

| File | Content |
|---|---|
| `caurong_drive.graphml` | Drivable road graph, including `oneway` tags |
| `caurong_water.geojson` | Han River polygons |
| `caurong_buildings.geojson` | Building footprints |

© OpenStreetMap contributors, ODbL 1.0.

The one-way tags match the directions the camera counted in only one direction:

- Trần Phú is southbound into J1.
- Trưng Nữ Vương leaves J1 only.
- Bạch Đằng north of the bridge is northbound, so traffic only leaves J2 that way.
