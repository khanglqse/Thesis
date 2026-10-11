# Camera vehicle counts: Tay Cau Rong junction, Da Nang

One public camera, one 15-minute PM-peak window. Counts were collected by this thesis using a YOLO detector and line-crossing analysis. They are **not** calibration data for the CityFlow/SUMO demand, and the evidence ledger has not been updated to treat them as such.

## Source

| | |
|---|---|
| Video | YouTube `31Fhtgcq_fc`, channel @0511.VietNam ("Phat Trien Da Nang"). Recording titled "chieu 1/07/2026"; the burned-in overlay shows **2026-07-11** |
| Window | offset 01:08:00–01:23:00 = overlay **17:15:59–17:30:59** |
| File | `data/camera/caurong_20260711_pm_peak.mp4` (720p, 30 fps; gitignored) |
| Terms | 0511.vn permits non-commercial use only; cite the source |

## Method

`scripts/count_camera_vehicles.py` (config `configs/camera/caurong_20260711.json`):

- **Detector:** YOLOv8x fine-tuned on VisDrone ([mshamrai/yolov8x-visdrone](https://huggingface.co/mshamrai/yolov8x-visdrone)), run at imgsz 2560 with conf 0.15. COCO YOLO found about 0 motorbikes from this camera height.
- **Two-wheelers:** VisDrone labels the rider as `pedestrian`, so `motor`, `bicycle`, `pedestrian`, `people` and the tricycle classes are folded into **motorcycle**. Duplicate boxes are removed in two steps: class-agnostic NMS at IoU 0.3, then a filter that drops nested boxes (rider inside bike).
- **Tracking:** ByteTrack at 10 fps with buffered IoU, where boxes are enlarged ×3 for association only, plus match 0.9 and buffer 60.
- **Counting:** the bottom-centre of each box must move from at least 8 px on one side of a line to at least 8 px on the other. Each track is counted once per (line, direction). A track's class is its confidence-weighted vote over its whole life.

`scripts/analyze_camera_routes.py`:

- **Turning movements:** the consecutive crossings in one track (enter junction on leg X, then leave on leg Y) give P(Y | X) per junction.
- **Network Markov chain:** J1 and J2 are chained through the main-axis link as an absorbing Markov chain.
- **Volumes:** these always come from the inbound line counts. Completed routes supply proportions only.

## Results (17:16–17:31, 11 Jul 2026)

All-class line crossings: **4,323**. These are motorcycle 2,420, car/van 1,873, truck 11 and bus 19.

The main axis between the two junctions is near-field, so its counts are the most reliable:

| | Northbound | Southbound |
|---|---:|---:|
| Motorcycles | 1,010 | 517 |
| Cars | 323 | 152 |

Car/van turning probabilities (`only_car/turning_movements.csv`), from completed routes:

| Junction | From | To | P |
|---|---|---|---:|
| J1 | West road | Main axis (north) | 89% (110/123) |
| J1 | Main axis, south | Main axis (north) | 89% (119/133) |
| J1 | Main axis (from north) | Main axis, south | 91% (105/115) |
| J2 | Main axis (from south) | Dragon Bridge | 75% (154/204) |
| J2 | Main axis (from south) | Bach Dang riverside | 21% (42/204) |
| J2 | Dragon Bridge | Main axis (south) | 62% (34/55) |
| J2 | Bach Dang riverside | Bridge / North-west | 39% / 37% (n=59) |

Through the chain, about **68% of cars entering from the west road or from the south end up on the Dragon Bridge** (`only_car/network_od.csv`).

The south-east road, the north-west road, and the west road (outbound) carry almost all their traffic in one direction: the count in the other direction is ≤ 13. That pattern looks like one-way operation, but it has not been checked against signage.

## Quality checks and limitations

- **Flow conservation (cars):** J1 480 in vs 501 out (4%); J2 612 in vs 735 out (17%). Car counts are internally consistent.
- **Flow conservation (motorcycles): fails.** Motorcycles entering at the cordon number 174, while 703 leave. The far-field lines (Dragon Bridge ramp, north-west road) detect almost no motorbikes; the bridge shows 0 inbound. Motorcycle totals at cordon lines are therefore a **lower bound**, and motorcycle turning proportions are not reported. Only the near-field main-axis counts are usable for motorcycles.
- **Route completion:** an inbound crossing counts as completed when it is followed by an outbound crossing at the same junction. For cars this happens 63% of the time; for motorcycles it is very low (2–70% by leg) because tracks fragment in the swarms.
- **Route precision:** `route_check_sheet.jpg` crops around the line midpoint, and the scene is too dense to confirm IDs by eye. Precision has not been verified. Check routes against track IDs in `annotated.mp4`, which is local only.
- **No manual ground-truth count yet.** Count one line for 1–2 minutes by hand and compare with `per_minute.csv` / `crossings.csv` before quoting absolute numbers.
- **NMS time limit:** the warning appeared a few times under CPU load, so a handful of frames may have truncated detections.
- **Scope:** one camera, one date, 15 minutes, partial view of two junctions.

## Realtime check (`realtime_check_m1280_s4/`)

Faster settings: YOLOv8m-VisDrone, imgsz 1280, 7.5 processed fps. With these, the full pipeline processed **180 s of video in 169 s** end to end, model load included. The machine was an Apple M4 Pro laptop on PyTorch MPS, with no other heavy jobs running. That is a realtime factor of 1.06 for one camera.

Detector time per frame:

| Model, input size | ms per frame |
|---|---:|
| YOLOv8x, 2560 | 470 |
| YOLOv8m, 2560 | 192 |
| YOLOv8m, 1920 | 125 |
| YOLOv8m, 1280 | 68 |

Compared with the reference run over the same 180 s, the fast settings counted near-field cars at +8% (194 vs 180) and near-field motorcycles at −10% (394 vs 439).

What realtime means for control:

- **Latency is not the constraint.** The SUMO controller decides every 10 s and the CityFlow residual every 300 s, while detection takes about 0.13 s per frame.
- **Network scale is not tested.** A 53-junction network would need one realtime camera pipeline per junction, for example an edge device at each junction sending counts every 10 s.

Speed-up applied along the way: `drop_nested` was vectorised (73 → 0.9 ms per frame, identical output).

## Reproduce

```sh
python3 scripts/count_camera_vehicles.py --video data/camera/caurong_20260711_pm_peak.mp4 \
  --config configs/camera/caurong_20260711.json \
  --model data/camera/models/yolov8x-visdrone.pt \
  --out results/camera_counts/caurong_20260711_1716 --start-clock 17:15:59 --save-video
python3 scripts/analyze_camera_routes.py results/camera_counts/caurong_20260711_1716 \
  --video data/camera/caurong_20260711_pm_peak.mp4
python3 scripts/analyze_camera_routes.py results/camera_counts/caurong_20260711_1716 --only car
python3 scripts/plot_camera_counts.py results/camera_counts/caurong_20260711_1716
python3 scripts/plot_camera_markov_map.py results/camera_counts/caurong_20260711_1716/only_car [--lang vi] [--bare]
```

`markov_map*.png` draws the car Markov chain on an OpenStreetMap base (`datasets/camera_caurong/`). The camera legs are mapped to streets in the `map` block of the config:

| Line | Street |
|---|---|
| `west_road` | Trần Phú |
| `boulevard_south` | Nguyễn Văn Linh (west) |
| `southeast_road` | Trưng Nữ Vương |
| `boulevard_mid` | Nguyễn Văn Linh, the link between J1 and J2 |
| `riverside_east` | 2 Tháng 9 |
| `bridge` | Cầu Rồng |
| `northwest_road` | Bạch Đằng (north) |

The defense decks use the `--bare` versions. Deck changes: main slide 12 (+60 s, total 39:50) and backup B10, in both `.build-40min-vi` and `.build-40min-en`.

Runtime is about 95 min on an Apple-silicon Mac under load (MPS, about 1.6 fps processed).
