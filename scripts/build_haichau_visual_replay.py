#!/usr/bin/env python3
"""Convert CityFlow native telemetry into the compact Hai Chau demo schema."""

import argparse
import hashlib
import json
import math
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def vehicle_class(length, width):
    # These exact templates are declared as motorbike/car by flow_gen.py and
    # retained verbatim in every frozen Hai Chau demand file.
    if abs(length - 2.0) < 1e-6 and abs(width - 1.0) < 1e-6:
        return "motorbike"
    if abs(length - 5.0) < 1e-6 and abs(width - 2.0) < 1e-6:
        return "car"
    return "unknown"


def parse_line(line, controlled_incoming, controlled_points, radius):
    vehicle_text, separator, signal_text = line.rstrip("\n").partition(";")
    vehicles = []
    counts = {"active_total": 0, "motorbike": 0, "car": 0, "unknown": 0,
              "rendered": 0}
    radius_sq = radius * radius
    for record in vehicle_text.split(","):
        fields = record.split()
        if len(fields) < 7:
            continue
        x, y, heading = map(float, fields[0:3])
        length, width = map(float, fields[5:7])
        kind = vehicle_class(length, width)
        counts["active_total"] += 1
        counts[kind] += 1
        visible = any((x - px) ** 2 + (y - py) ** 2 <= radius_sq
                      for px, py in controlled_points)
        if visible:
            vehicles.append({
                "id": fields[3], "x": round(x, 2), "y": round(y, 2),
                "heading": round(heading, 5), "length": length,
                "width": width, "class": kind,
            })
    counts["rendered"] = len(vehicles)
    signals = {}
    if separator:
        for record in signal_text.split(","):
            fields = record.split()
            if fields and fields[0] in controlled_incoming:
                signals[fields[0]] = fields[1:]
    return vehicles, signals, counts


def build(raw_path, result_path, network_path, output_path, radius, max_seconds=None,
          run_id=None, display_controller_id=None):
    result = json.loads(Path(result_path).read_text())
    replay = result.get("replay", result)
    network = json.loads(Path(network_path).read_text())
    geometry = network["geometry"]
    controlled = [junction for junction in geometry["junctions"]
                  if junction.get("controlled")]
    controlled_points = [(item["x"], item["y"]) for item in controlled]
    controlled_incoming = set(road_id for item in controlled
                              for road_id in item["incoming_roads"])
    lines = Path(raw_path).read_text().splitlines()
    frames = []
    source_frames = replay["frames"]
    if max_seconds is not None:
        source_frames = [frame for frame in source_frames
                         if int(frame["t"]) <= max_seconds]
    for frame in source_frames:
        enriched = dict(frame)
        elapsed = int(frame["t"])
        if elapsed == 0:
            enriched.update({
                "vehicles": [], "signals": {},
                "counts": {"active_total": 0, "motorbike": 0, "car": 0,
                           "unknown": 0, "rendered": 0},
            })
        else:
            if elapsed > len(lines):
                raise ValueError("native replay is shorter than compact replay")
            vehicles, signals, counts = parse_line(
                lines[elapsed - 1], controlled_incoming, controlled_points, radius)
            enriched.update({"vehicles": vehicles, "signals": signals,
                             "counts": counts})
        frames.append(enriched)
    payload = dict(replay)
    metrics = result.get("metrics", replay.get("metrics", {}))
    payload.update({
        "run_id": run_id,
        "case_id": metrics.get("case_id"),
        "regime": metrics.get("regime"),
        "controller_id": display_controller_id or metrics.get("controller_id"),
        "source_controller_id": metrics.get("controller_id"),
        "learning_seed": metrics.get("learning_seed"),
        "demand_seed": metrics.get("demand_seed"),
        "simulator_seed": metrics.get("simulator_seed"),
        "checkpoint_sha256": metrics.get("checkpoint_sha256"),
        "checkpoint_contract_sha256": metrics.get("checkpoint_contract_sha256"),
        "metrics": dict((key, metrics.get(key)) for key in (
            "queue_integral_vehicle_seconds", "pending_integral_vehicle_seconds",
            "completion_rate", "arrived", "running", "pending")
                        if key in metrics),
        "metrics_provenance": (
            "stored complete 3600-second evaluation; separate from partial visual telemetry"),
    })
    payload["format_version"] = 3
    payload["frames"] = frames
    payload["telemetry"] = {
        "source": "CityFlow native replayLogFile",
        "raw_sha256": sha256(raw_path),
        "vehicle_position_units": "CityFlow local metres",
        "heading_units": "radians",
        "class_source": "exact frozen demand vehicle template dimensions",
        "render_policy": "within %.1f metres of a controlled signal" % radius,
        "whole_network_counts": True,
        "complete_horizon": (
            int(frames[-1]["t"]) >= int(replay["frames"][-1]["t"])
            and len(lines) >= int(replay["frames"][-1]["t"])),
        "available_through_seconds": int(frames[-1]["t"]),
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return {"output": str(target), "sha256": sha256(target),
            "frames": len(frames), "bytes": target.stat().st_size,
            "max_active": max(frame["counts"]["active_total"] for frame in frames),
            "max_rendered": max(frame["counts"]["rendered"] for frame in frames)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-replay", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--network", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--render-radius", type=float, default=140.0)
    parser.add_argument("--max-seconds", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--display-controller-id")
    args = parser.parse_args(argv)
    if not math.isfinite(args.render_radius) or args.render_radius <= 0:
        raise ValueError("render radius must be positive")
    print(json.dumps(build(args.raw_replay, args.result, args.network,
                           args.output, args.render_radius, args.max_seconds,
                           args.run_id, args.display_controller_id), sort_keys=True))


if __name__ == "__main__":
    main()
