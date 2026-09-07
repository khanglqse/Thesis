"""Generate a CityFlow flow.json: motorbike-heavy synthetic demand via random walks."""
from __future__ import annotations

import json
import random
import csv
import math
from pathlib import Path
from typing import List

from traffic_rl.network.roadnet import RoadNet

# CityFlow vehicle templates. Motorbike: shorter/narrower, common in Vietnam.
VEHICLE_TEMPLATES = {
    "motorbike": {
        # Vietnamese motorbike: short, narrow, aggressive car-following with a very
        # small gap/headway so they pack tightly and weave — denser, more chaotic
        # than a car-dominated flow. CityFlow is still lane-disciplined, so this
        # approximates (not reproduces) real motorbike sub-lane filtering.
        "length": 2.0, "width": 1.0, "maxPosAcc": 3.5, "maxNegAcc": 5.0,
        "usualPosAcc": 3.0, "usualNegAcc": 4.5, "minGap": 0.5,
        "maxSpeed": 13.89, "headwayTime": 0.8,
    },
    "car": {
        "length": 5.0, "width": 2.0, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 2.5,
        "maxSpeed": 11.11, "headwayTime": 1.5,
    },
}


def load_published_turning_movements(path):
    """Load the published Da Nang peak turning table without losing provenance."""
    rows = []
    with Path(path).open(newline="") as stream:
        for raw in csv.DictReader(stream):
            row = dict(raw)
            row["pcu_per_hour"] = int(row["pcu_per_hour"])
            rows.append(row)
    identities = set((row["approach"], row["movement"]) for row in rows)
    expected = set((approach, movement)
                   for approach in ("NW", "SE", "NE", "SW")
                   for movement in ("left", "through", "right"))
    if identities != expected or len(rows) != len(expected):
        raise ValueError("turning table must contain each of 12 movements exactly once")
    return rows


def load_danang_camera_presets(path):
    """Aggregate four digitized camera lines into reproducible time presets."""
    by_hour = {}
    count_fields = ("car_veh_per_h", "motorcycle_veh_per_h",
                    "truck_veh_per_h", "bus_veh_per_h")
    with Path(path).open(newline="") as stream:
        for row in csv.DictReader(stream):
            hour = row["hour_start"]
            out = by_hour.setdefault(hour, {
                "hour_start": hour,
                "observed_vehicle_count_per_hour": 0,
                "derived_pcu_per_hour": 0.0,
                "covered_movements": 0,
                "scope": "four_camera_counting_lines",
                "_uncertainty_sq": 0.0,
            })
            out["observed_vehicle_count_per_hour"] += sum(
                int(row[field]) for field in count_fields)
            out["derived_pcu_per_hour"] += float(row["derived_pcu_per_h"])
            out["covered_movements"] += 1
            out["_uncertainty_sq"] += float(
                row["digitization_uncertainty_veh_per_h"]) ** 2

    hours = {"normal": "13:00", "am_peak": "08:00", "pm_peak": "17:00"}
    presets = {}
    for name, hour in hours.items():
        if hour not in by_hour:
            raise ValueError("camera profile is missing preset hour %s" % hour)
        row = dict(by_hour[hour])
        row["digitization_uncertainty_vehicle_per_hour"] = math.sqrt(
            row.pop("_uncertainty_sq"))
        presets[name] = row
    return presets


def _random_route(rn: RoadNet, entry_roads: List[str], length: int, rng: random.Random) -> List[str]:
    """Random walk over road adjacency starting from an entry road."""
    route = [rng.choice(entry_roads)]
    while len(route) < length:
        nxts = rn.next_roads(route[-1])
        if not nxts:
            break
        route.append(rng.choice(nxts))
    return route


def generate_flow(
    rn: RoadNet,
    num_flows: int,
    route_length: int,
    seed: int,
    motorbike_ratio: float,
    start_time: int = 0,
    end_time: int = 3600,
    interval: float = 2.0,
) -> List[dict]:
    """Return a list of CityFlow flow entries (deterministic given seed)."""
    rng = random.Random(seed)
    entry_roads = rn.entry_roads()
    if not entry_roads:
        raise ValueError("roadnet has no entry roads (no virtual boundary intersections)")

    flows: List[dict] = []
    for _ in range(num_flows):
        route = _random_route(rn, entry_roads, route_length, rng)
        kind = "motorbike" if rng.random() < motorbike_ratio else "car"
        flows.append({
            "vehicle": VEHICLE_TEMPLATES[kind],
            "route": route,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time,
        })
    return flows


def write_flow(rn: RoadNet, out_path: str, **kwargs) -> Path:
    flows = generate_flow(rn, **kwargs)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(flows, indent=2))
    return out
