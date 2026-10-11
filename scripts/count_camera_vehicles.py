#!/usr/bin/env python3
"""Count vehicles crossing screen-lines in a fixed traffic-camera video.

Detector: a YOLOv8 model fine-tuned on VisDrone (top-down/aerial view), because
COCO-pretrained YOLO misses almost every motorbike from a high-mounted camera.
From this angle the rider of a motorbike is usually labelled ``pedestrian``, so
two-wheeler-like classes are folded into ``motorcycle``. Pedestrians are not a
category: count lines sit on the carriageway away from crosswalks, and a
line margin stops queued vehicles whose box jitters on the line from counting.
Tracks come from ByteTrack; a vehicle is counted once per line when its
bottom-centre point goes from one side of the line segment to the other, and its
class is the confidence-weighted majority over the whole track.

Example:
    python3 scripts/count_camera_vehicles.py \
        --video data/camera/caurong_20260701_pm_30-45.mp4 \
        --config configs/camera/caurong_west.json \
        --model data/camera/models/yolov8m-visdrone.pt \
        --start-clock 16:45:00 --out results/camera_counts/caurong_20260701_pm
"""

import argparse
import csv
import json
import signal
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import YAML, IterableSimpleNamespace
from ultralytics.utils.checks import check_yaml

MODEL_URL = "https://huggingface.co/mshamrai/yolov8m-visdrone/resolve/main/best.pt"
CATEGORIES = ("motorcycle", "car", "truck", "bus")
COLORS_BGR = {"motorcycle": (214, 120, 42), "car": (52, 104, 235),
              "truck": (122, 175, 27), "bus": (0, 161, 237)}


def side(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def line_coords(a, b, p, scale):
    """Signed distance of p from line a->b (in 1280-wide pixels) and position u along it."""
    ab = np.hypot(b[0] - a[0], b[1] - a[1])
    u = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / ab ** 2
    return side(a, b, p) / ab / scale, u


def drop_nested(xyxy, conf, frac=0.6):
    """Keep-mask that removes a box mostly contained in a larger box.

    From above, VisDrone labels the rider (``pedestrian``) and the motorbike
    (``motor``) as two boxes, the small one inside the big one; their IoU is too
    low for NMS, so without this one motorbike becomes two tracks.
    """
    area = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
    ix = np.clip(np.minimum(xyxy[:, None, 2], xyxy[None, :, 2])
                 - np.maximum(xyxy[:, None, 0], xyxy[None, :, 0]), 0, None)
    iy = np.clip(np.minimum(xyxy[:, None, 3], xyxy[None, :, 3])
                 - np.maximum(xyxy[:, None, 1], xyxy[None, :, 1]), 0, None)
    bigger = (area[None, :] > area[:, None]) & (area[None, :] < 6 * area[:, None])
    inside = ix * iy >= frac * area[:, None]
    keep = ~(bigger & inside).any(axis=1)
    return keep


def expand(dets, scale):
    """Boxes with width/height scaled about the centre (buffered IoU).

    A 10-px motorbike moves about its own length between processed frames, so
    raw boxes from consecutive frames barely overlap and ByteTrack keeps starting
    new tracks. Matching on enlarged boxes restores the overlap.
    """
    if scale == 1 or not len(dets):
        return dets
    d = dets.data.clone()
    cx, cy = (d[:, 0] + d[:, 2]) / 2, (d[:, 1] + d[:, 3]) / 2
    w, h = (d[:, 2] - d[:, 0]) * scale / 2, (d[:, 3] - d[:, 1]) * scale / 2
    d[:, 0], d[:, 1], d[:, 2], d[:, 3] = cx - w, cy - h, cx + w, cy + h
    return Boxes(d, dets.orig_shape)


class LineCounter:
    """Per-track line-crossing state; one record per (track, line, direction)."""

    def __init__(self, lines, margin, sx, sy):
        self.lines, self.margin, self.sx, self.sy = lines, margin, sx, sy
        self.history = defaultdict(lambda: deque(maxlen=64))  # tid -> (t, x, y)
        self.last_side = {}                                    # (tid, line) -> side, clear of it
        self.counted = set()

    def update(self, t, tid, p):
        hist, found = self.history[tid], []
        for ln in self.lines:
            dist, u = line_coords(ln["A"], ln["B"], p, self.sx)
            if abs(dist) < self.margin or not -0.05 <= u <= 1.05:
                continue
            sgn = 1 if dist > 0 else -1
            prev_sgn = self.last_side.get((tid, ln["name"]))
            self.last_side[(tid, ln["name"])] = sgn
            direction = ln["pos"] if sgn > 0 else ln["neg"]
            key = (tid, ln["name"], direction)
            if prev_sgn is None or prev_sgn == sgn or key in self.counted:
                continue
            # crossed: was >= margin on one side, now >= margin on the other
            old = next((h for h in hist if t - h[0] <= 1.0), hist[0]) if hist else (t, *p)
            dt = max(t - old[0], 1e-6)
            speed = np.hypot((p[0] - old[1]) / self.sx, (p[1] - old[2]) / self.sy) / dt
            self.counted.add(key)
            found.append({"t_s": round(t, 2), "line": ln["name"], "direction": direction,
                          "track_id": tid, "speed_px_s": round(float(speed), 1)})
        hist.append((t, *p))
        return found


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--video", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True, help=f"VisDrone YOLO weights ({MODEL_URL})")
    ap.add_argument("--out", required=True)
    ap.add_argument("--imgsz", type=int, default=2560,
                    help="inference size; upscaling is what makes 10-px motorbikes detectable")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--iou", type=float, default=0.3,
                    help="class-agnostic NMS IoU; low because riders and bikes overlap")
    ap.add_argument("--stride", type=int, default=3, help="process every Nth frame")
    ap.add_argument("--track-scale", type=float, default=3.0,
                    help="box enlargement used only for track association (buffered IoU)")
    ap.add_argument("--match-thresh", type=float, default=0.9, help="ByteTrack match_thresh")
    ap.add_argument("--track-buffer", type=int, default=60,
                    help="processed frames a lost track is kept for re-association")
    ap.add_argument("--margin", type=float, default=8.0,
                    help="px a track must be clear of the line on both sides; stops queued "
                         "vehicles whose box jitters on the line from being counted")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--start-clock", default=None,
                    help="wall-clock HH:MM:SS of the first frame, read from the burned-in overlay")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--save-video", action="store_true",
                    help="write an annotated check video with track IDs and trails")
    return ap.parse_args()


def stop(*_):
    raise KeyboardInterrupt


def main():
    args = parse_args()
    signal.signal(signal.SIGTERM, stop)
    cfg = json.loads(Path(args.config).read_text())
    lines = cfg["lines"]
    to_cat = {raw: cat for cat, raws in cfg["class_map"].items() for raw in raws}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sx, sy = W / cfg["frame_size"][0], H / cfg["frame_size"][1]
    for ln in lines:
        ln["A"] = (ln["a"][0] * sx, ln["a"][1] * sy)
        ln["B"] = (ln["b"][0] * sx, ln["b"][1] * sy)
    clock0 = (datetime.strptime(args.start_clock, "%H:%M:%S")
              if args.start_clock else None)

    model = YOLO(args.model)
    track_cfg = YAML.load(check_yaml("bytetrack.yaml"))
    track_cfg["track_buffer"] = args.track_buffer
    track_cfg["match_thresh"] = args.match_thresh
    tracker = BYTETracker(IterableSimpleNamespace(**track_cfg))
    writer = None
    if args.save_video:
        writer = cv2.VideoWriter(str(out / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps / args.stride, (W, H))

    # raw crossings are appended as they happen so a crash still leaves data on disk
    raw_cols = ["t_s", "line", "direction", "track_id", "speed_px_s"]
    raw_file = (out / "crossings_raw.csv").open("w", newline="")
    raw_writer = csv.DictWriter(raw_file, fieldnames=raw_cols)
    raw_writer.writeheader()

    counter = LineCounter(lines, args.margin, sx, sy)
    votes = defaultdict(Counter)                      # tid -> category -> conf sum
    events = []
    live = Counter()                                  # running count per line for overlay
    idx, t, t_start = 0, 0.0, time.time()
    last_frame = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            if (idx - 1) % args.stride:
                continue
            t = (idx - 1) / fps
            if args.max_seconds and t > args.max_seconds:
                break
            res = model.predict(frame, imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                                agnostic_nms=True, device=args.device, verbose=False)[0]
            dets = res.boxes.cpu()
            dets = dets[drop_nested(dets.xyxy.numpy(), dets.conf.numpy())]
            tracks = tracker.update(expand(dets, args.track_scale), frame)
            for x1, y1, x2, y2, tid, c, k, _ in tracks:
                cat = to_cat.get(res.names[int(k)])
                if cat is None:
                    continue
                tid = int(tid)
                votes[tid][cat] += float(c)
                # undo the association enlargement before using the box
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                hw, hh = (x2 - x1) / 2 / args.track_scale, (y2 - y1) / 2 / args.track_scale
                x1, y1, x2, y2 = cx - hw, cy - hh, cx + hw, cy + hh
                for record in counter.update(t, tid, (cx, y2)):
                    events.append(record)
                    raw_writer.writerow(record)
                    live[record["line"]] += 1
                hist = counter.history[tid]
                if writer is not None:
                    col = COLORS_BGR[cat]
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), col, 1)
                    pts = np.array([(h[1], h[2]) for h in list(hist)[-20:]], np.int32)
                    cv2.polylines(frame, [pts], False, col, 1)
                    cv2.putText(frame, str(tid), (int(x1), int(y1) - 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.3, col, 1, cv2.LINE_AA)
            for ln in lines:
                A = tuple(int(v) for v in ln["A"]); B = tuple(int(v) for v in ln["B"])
                cv2.line(frame, A, B, (255, 255, 255), 2)
                cv2.putText(frame, f"{ln['name']}: {live[ln['name']]}", (A[0] + 4, A[1] - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            if writer is not None:
                writer.write(frame)
            last_frame = frame
            n_done = (idx - 1) // args.stride + 1
            if n_done % 300 == 0:
                raw_file.flush()
                el = time.time() - t_start
                print(f"t={t:7.1f}s  frames={n_done}  crossings={len(events)}  "
                      f"{n_done / el:.2f} fps", flush=True)
    except KeyboardInterrupt:
        print(f"interrupted at t={t:.1f}s; writing partial results", flush=True)
    finally:
        raw_file.close()
        if writer is not None:
            writer.release()
    finalize(args, cfg, lines, out, events, votes, clock0, t, fps, last_frame)


def finalize(args, cfg, lines, out, events, votes, clock0, t_end, fps, last_frame):
    duration = min(t_end, args.max_seconds or t_end)
    # each track's class is its confidence-weighted vote over its whole life
    for e in events:
        e["category"] = votes[e["track_id"]].most_common(1)[0][0]
        if clock0:
            e["clock"] = (clock0 + timedelta(seconds=e["t_s"])).strftime("%H:%M:%S")

    with (out / "crossings.csv").open("w", newline="") as f:
        cols = ["t_s", "clock", "line", "direction", "category", "track_id", "speed_px_s"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(events)

    table = Counter((e["line"], e["direction"], e["category"]) for e in events)
    with (out / "counts_by_line.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "direction", *CATEGORIES, "total_veh", "veh_per_h", "pcu_per_h"])
        for ln in lines:
            for d in (ln["neg"], ln["pos"]):
                row = [table[(ln["name"], d, c)] for c in CATEGORIES]
                pcu = sum(n * cfg["pcu"][c] for n, c in zip(row, CATEGORIES))
                w.writerow([ln["name"], d, *row, sum(row),
                            round(sum(row) * 3600 / duration), round(pcu * 3600 / duration)])

    per_min = Counter((int(e["t_s"] // 60), e["category"]) for e in events)
    with (out / "per_minute.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "clock_start", *CATEGORIES])
        for m in range(int(np.ceil(duration / 60))):
            clk = ((clock0 + timedelta(minutes=m)).strftime("%H:%M") if clock0 else "")
            w.writerow([m, clk, *[per_min[(m, c)] for c in CATEGORIES]])

    if last_frame is not None:
        cv2.imwrite(str(out / "lines_last_frame.jpg"), last_frame)

    totals = Counter(e["category"] for e in events)
    meta = {
        "video": str(args.video), "config": str(args.config), "model": str(args.model),
        "model_source": MODEL_URL, "imgsz": args.imgsz, "conf": args.conf,
        "stride": args.stride, "fps_source": fps, "fps_processed": fps / args.stride,
        "line_margin_px": args.margin, "agnostic_nms": True, "nms_iou": args.iou,
        "nested_box_filter": 0.6, "tracker": "bytetrack", "track_buffer": args.track_buffer,
        "track_scale": args.track_scale, "match_thresh": args.match_thresh,
        "duration_s": round(duration, 1), "start_clock": args.start_clock,
        "lines": [{k: ln[k] for k in ("name", "label", "a", "b", "pos", "neg", "legs", "cordon")}
                  for ln in lines],
        "crossings_by_class": {c: totals[c] for c in CATEGORIES},
        "total_crossings": len(events),
        "pcu_factors": cfg["pcu"], "pcu_source": cfg["pcu_source"],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(json.dumps(meta["crossings_by_class"]), f"crossings={len(events)} in {duration:.0f}s")


if __name__ == "__main__":
    main()
