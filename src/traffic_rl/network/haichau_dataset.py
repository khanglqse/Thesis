"""Audit and demand tooling for the versioned Hai Chau CityFlow dataset."""

from collections import Counter, deque
import random

from traffic_rl.network.flow_gen import VEHICLE_TEMPLATES
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import validate_disjoint_splits


def _weak_component_count(nodes, edges):
    if not nodes:
        return 0
    neighbors = {node: set() for node in nodes}
    for start, end in edges:
        neighbors[start].add(end)
        neighbors[end].add(start)
    remaining = set(nodes)
    components = 0
    while remaining:
        components += 1
        pending = [min(remaining)]
        remaining.remove(pending[0])
        while pending:
            node = pending.pop()
            unseen = neighbors[node] & remaining
            remaining.difference_update(unseen)
            pending.extend(sorted(unseen, reverse=True))
    return components


def audit_network(path):
    """Return deterministic graph counts and all detected phase-reference errors."""
    roadnet = RoadNet.load(str(path))
    road_by_id = roadnet._road_by_id
    intersection_ids = set(roadnet._by_id)
    agents = sorted(roadnet.signalized_ids())
    agent_set = set(agents)
    errors = []

    for road in sorted(roadnet.roads, key=lambda item: item["id"]):
        road_id = road["id"]
        for field in ("startIntersection", "endIntersection"):
            if road.get(field) not in intersection_ids:
                errors.append(
                    "road %s references missing intersection %s" % (road_id, road.get(field))
                )

    for intersection in sorted(roadnet.intersections, key=lambda item: item["id"]):
        intersection_id = intersection["id"]
        for road_id in intersection.get("roads", []):
            if road_id not in road_by_id:
                errors.append(
                    "intersection %s references missing road %s" % (intersection_id, road_id)
                )

        road_links = intersection.get("roadLinks", [])
        for link_index, road_link in enumerate(road_links):
            start_id = road_link.get("startRoad")
            end_id = road_link.get("endRoad")
            start_road = road_by_id.get(start_id)
            end_road = road_by_id.get(end_id)
            if start_road is None:
                errors.append(
                    "intersection %s roadLink %d references missing road %s"
                    % (intersection_id, link_index, start_id)
                )
            if end_road is None:
                errors.append(
                    "intersection %s roadLink %d references missing road %s"
                    % (intersection_id, link_index, end_id)
                )
            for lane_link_index, lane_link in enumerate(road_link.get("laneLinks", [])):
                start_lane = lane_link.get("startLaneIndex")
                end_lane = lane_link.get("endLaneIndex")
                if start_road is not None and (
                    not isinstance(start_lane, int)
                    or start_lane < 0
                    or start_lane >= len(start_road.get("lanes", []))
                ):
                    errors.append(
                        "intersection %s roadLink %d laneLink %d has invalid start lane index %s"
                        % (intersection_id, link_index, lane_link_index, start_lane)
                    )
                if end_road is not None and (
                    not isinstance(end_lane, int)
                    or end_lane < 0
                    or end_lane >= len(end_road.get("lanes", []))
                ):
                    errors.append(
                        "intersection %s roadLink %d laneLink %d has invalid end lane index %s"
                        % (intersection_id, link_index, lane_link_index, end_lane)
                    )

        traffic_light = intersection.get("trafficLight") or {}
        for phase_index, phase in enumerate(traffic_light.get("lightphases", [])):
            for road_link_index in phase.get("availableRoadLinks", []):
                if (
                    not isinstance(road_link_index, int)
                    or road_link_index < 0
                    or road_link_index >= len(road_links)
                ):
                    errors.append(
                        "intersection %s phase %d has invalid roadLink index %s"
                        % (intersection_id, phase_index, road_link_index)
                    )

    edges = sorted(
        {
            (road["startIntersection"], road["endIntersection"])
            for road in roadnet.roads
            if road.get("startIntersection") in agent_set
            and road.get("endIntersection") in agent_set
        }
    )
    return {
        "roads": len(roadnet.roads),
        "intersections": len(roadnet.intersections),
        "controlled_signals": len(agents),
        "agent_ids": agents,
        "directed_signal_edges": [list(edge) for edge in edges],
        "weak_components": _weak_component_count(agents, edges),
        "phase_errors": sorted(set(errors)),
    }


def count_controlled_signals(roadnet, route):
    """Count distinct controlled intersections crossed by a road route."""
    controlled = set(roadnet.signalized_ids())
    return len(
        {
            roadnet._road_by_id[road_id]["endIntersection"]
            for road_id in route
            if road_id in roadnet._road_by_id
            and roadnet._road_by_id[road_id]["endIntersection"] in controlled
        }
    )


def _seeded_boundary_route(roadnet, entries, exits, min_signals, rng):
    starts = list(entries)
    rng.shuffle(starts)
    controlled = set(roadnet.signalized_ids())
    for start in starts:
        start_intersection = roadnet._road_by_id[start]["endIntersection"]
        start_count = int(start_intersection in controlled)
        pending = deque([(start, [start], {start_intersection} & controlled)])
        visited = {(start, min(start_count, min_signals))}
        while pending:
            current, path, signals = pending.popleft()
            if current in exits and len(path) > 1 and len(signals) >= min_signals:
                return path
            neighbors = sorted(roadnet.next_roads(current))
            rng.shuffle(neighbors)
            for next_road in neighbors:
                if next_road in path or next_road not in roadnet._road_by_id:
                    continue
                next_intersection = roadnet._road_by_id[next_road]["endIntersection"]
                next_signals = signals | ({next_intersection} & controlled)
                state = (next_road, min(len(next_signals), min_signals))
                if state in visited:
                    continue
                visited.add(state)
                pending.append((next_road, path + [next_road], next_signals))
    return None


def generate_routes(roadnet, seed, route_count, min_signals):
    """Generate seeded boundary-to-boundary routes meeting signal coverage."""
    if route_count < 0 or min_signals < 0:
        raise ValueError("route_count and min_signals must be non-negative")
    entries = sorted(roadnet.entry_roads())
    virtual = {
        intersection["id"]
        for intersection in roadnet.intersections
        if intersection.get("virtual")
    }
    exits = {
        road["id"]
        for road in roadnet.roads
        if road.get("endIntersection") in virtual
    }
    if not entries or not exits:
        raise ValueError("insufficient multi-signal routes")

    rng = random.Random(seed)
    routes = []
    for _ in range(route_count):
        route = _seeded_boundary_route(roadnet, entries, exits, min_signals, rng)
        if route is None:
            raise ValueError("insufficient multi-signal routes")
        routes.append(route)
    return routes


def _vehicle_family(seed, count, motorcycle_ratio):
    if not 0.0 <= motorcycle_ratio <= 1.0:
        raise ValueError("motorcycle_ratio must be between zero and one")
    rng = random.Random(seed + 104729)
    return [
        "motorbike" if rng.random() < motorcycle_ratio else "car"
        for _ in range(count)
    ]


def build_flow_cases(roadnet, config):
    """Build all seeded split/regime CityFlow cases from resolved inputs."""
    regimes = config["regimes"]
    if "normal" not in regimes:
        raise ValueError("normal regime is required")
    normal_interval = float(regimes["normal"]["interval_seconds"])
    if normal_interval <= 0:
        raise ValueError("regime intervals must be positive")

    cases = []
    for split in ("train", "validation", "test"):
        split_config = config.get("splits", {}).get(split, {})
        demand_seeds = split_config.get("demand_seeds", [])
        sim_seeds = split_config.get("sim_seeds", [])
        if len(demand_seeds) != len(sim_seeds):
            raise ValueError("demand and simulation seeds must be paired")
        for demand_seed, sim_seed in zip(demand_seeds, sim_seeds):
            routes = generate_routes(
                roadnet,
                seed=demand_seed,
                route_count=int(config["route_count"]),
                min_signals=int(config["min_controlled_signals_per_route"]),
            )
            vehicle_kinds = _vehicle_family(
                demand_seed, len(routes), float(config["motorcycle_ratio"])
            )
            histogram = Counter(
                count_controlled_signals(roadnet, route) for route in routes
            )
            for scenario, regime in regimes.items():
                interval = float(regime["interval_seconds"])
                if interval <= 0:
                    raise ValueError("regime intervals must be positive")
                flow = [
                    {
                        "vehicle": dict(VEHICLE_TEMPLATES[kind]),
                        "route": list(route),
                        "interval": interval,
                        "startTime": 0,
                        "endTime": int(config["horizon_seconds"]),
                    }
                    for route, kind in zip(routes, vehicle_kinds)
                ]
                cases.append(
                    {
                        "case_id": "%s_%s_demand%s" % (split, scenario, demand_seed),
                        "split": split,
                        "scenario": scenario,
                        "demand_seed": demand_seed,
                        "sim_seed": sim_seed,
                        "scale": normal_interval / interval,
                        "flow": flow,
                        "route_signal_histogram": {
                            str(signal_count): histogram[signal_count]
                            for signal_count in sorted(histogram)
                        },
                        "data_source_label": config["demand_label"],
                    }
                )
    validate_disjoint_splits(cases)
    return cases
