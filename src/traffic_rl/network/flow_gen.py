"""Generate a CityFlow flow.json: motorbike-heavy synthetic demand via random walks."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from traffic_rl.network.roadnet import RoadNet

# CityFlow vehicle templates. Motorbike: shorter/narrower, common in Vietnam.
VEHICLE_TEMPLATES = {
    "motorbike": {
        "length": 2.0, "width": 1.0, "maxPosAcc": 3.0, "maxNegAcc": 5.0,
        "usualPosAcc": 2.5, "usualNegAcc": 4.5, "minGap": 1.0,
        "maxSpeed": 13.89, "headwayTime": 1.0,
    },
    "car": {
        "length": 5.0, "width": 2.0, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 2.5,
        "maxSpeed": 11.11, "headwayTime": 1.5,
    },
}


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
