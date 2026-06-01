# OSM data – Đà Nẵng

Dữ liệu OpenStreetMap cho trung tâm Đà Nẵng, tải bằng:

```bash
python3 scripts/download_osm_danang.py
```

## File

| File | Mô tả |
|------|--------|
| `danang_roads.graphml` | Đồ thị đường (NetworkX): nút = giao lộ, cạnh = đoạn đường. Dùng làm input cho bước OSM → CityFlow. |
| `danang_nodes.geojson` | Điểm nút (giao lộ) dạng GeoJSON. |
| `danang_edges.geojson` | Cạnh (đoạn đường) dạng GeoJSON. |

## Vùng dữ liệu

- Bounding box (trung tâm Đà Nẵng): `(west, south, east, north) = (108.12, 16.00, 108.28, 16.08)`.
- Muốn đổi vùng: sửa `bbox` trong `scripts/download_osm_danang.py` rồi chạy lại.

## Bước tiếp theo

Chuyển `danang_roads.graphml` sang CityFlow (`cityflow_danang/roadnet.json` + `flow.json`) bằng công cụ OSM→CityFlow hoặc script converter, sau đó chạy:

```bash
./scripts/cityflow_ui_demo.sh generate_danang
./scripts/cityflow_ui_demo.sh serve_danang 8080
```
