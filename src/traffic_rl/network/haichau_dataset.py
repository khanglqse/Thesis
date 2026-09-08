"""Audit and demand tooling for the versioned Hai Chau CityFlow dataset."""

from collections import Counter, deque
import random

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import canonical_sha256, validate_disjoint_splits


# Kept local so the pinned Python 3.6 research runtime does not import the
# legacy flow generator, whose Python 3.7 future import is host-only.
VEHICLE_TEMPLATES = {
    "motorbike": {
        "length": 2.0,
        "width": 1.0,
        "maxPosAcc": 3.5,
        "maxNegAcc": 5.0,
        "usualPosAcc": 3.0,
        "usualNegAcc": 4.5,
        "minGap": 0.5,
        "maxSpeed": 13.89,
        "headwayTime": 0.8,
    },
    "car": {
        "length": 5.0,
        "width": 2.0,
        "maxPosAcc": 2.0,
        "maxNegAcc": 4.5,
        "usualPosAcc": 2.0,
        "usualNegAcc": 4.5,
        "minGap": 2.5,
        "maxSpeed": 11.11,
        "headwayTime": 1.5,
    },
}


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
    green_phase_counts = {agent_id: 0 for agent_id in agents}
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
            serves_movement = False
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
                elif road_links[road_link_index].get("laneLinks"):
                    serves_movement = True
                else:
                    errors.append(
                        "intersection %s phase %d roadLink %d has no lane movements"
                        % (intersection_id, phase_index, road_link_index)
                    )
            if intersection_id in agent_set and serves_movement:
                green_phase_counts[intersection_id] += 1

        if (
            intersection_id in agent_set
            and green_phase_counts[intersection_id] < 2
        ):
            errors.append(
                "intersection %s has fewer than two movement-serving green phases"
                % intersection_id
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
        "lanes": sum(len(road.get("lanes", [])) for road in roadnet.roads),
        "intersections": len(roadnet.intersections),
        "controlled_signals": len(agents),
        "green_phases": sum(green_phase_counts.values()),
        "agent_green_phase_counts": green_phase_counts,
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


def _shortest_route(roadnet, start, target):
    pending = deque([[start]])
    visited = {start}
    while pending:
        path = pending.popleft()
        if path[-1] == target and len(path) > 1:
            return path
        for next_road in sorted(roadnet.next_roads(path[-1])):
            if next_road not in visited and next_road in roadnet._road_by_id:
                visited.add(next_road)
                pending.append(path + [next_road])
    return None


def route_is_valid(roadnet, route, min_signals=0):
    """Return whether a loop-free route connects boundaries through valid links."""
    if not route or len(route) != len(set(route)):
        return False
    if any(road_id not in roadnet._road_by_id for road_id in route):
        return False
    virtual = {i["id"] for i in roadnet.intersections if i.get("virtual")}
    if roadnet._road_by_id[route[0]]["startIntersection"] not in virtual:
        return False
    if roadnet._road_by_id[route[-1]]["endIntersection"] not in virtual:
        return False
    if any(route[index + 1] not in roadnet.next_roads(route[index])
           for index in range(len(route) - 1)):
        return False
    return count_controlled_signals(roadnet, route) >= min_signals


def build_route_catalog(roadnet, min_signals):
    """Enumerate one stable shortest route for every valid boundary OD pair."""
    entries = sorted(roadnet.entry_roads())
    virtual = {i["id"] for i in roadnet.intersections if i.get("virtual")}
    exits = sorted(r["id"] for r in roadnet.roads
                   if r.get("endIntersection") in virtual)
    catalog = []
    for entry in entries:
        for exit_road in exits:
            route = _shortest_route(roadnet, entry, exit_road)
            if route is None or not route_is_valid(roadnet, route, min_signals):
                continue
            route_hash = canonical_sha256(route)
            catalog.append({
                "route_family_id": "rf_" + route_hash,
                "route_sha256": route_hash,
                "origin_road": route[0],
                "destination_road": route[-1],
                "controlled_signals": count_controlled_signals(roadnet, route),
                "route": route,
            })
    catalog.sort(key=lambda family: family["route_sha256"])
    if not catalog:
        raise ValueError("insufficient multi-signal route families")
    return catalog


def partition_route_families(catalog, split_weights):
    """Assign every canonical family once using stable weighted partitions."""
    splits = ("train", "validation", "test")
    if set(split_weights) != set(splits) or any(float(split_weights[s]) <= 0 for s in splits):
        raise ValueError("route family split must define positive train/validation/test weights")
    if len(catalog) < len(splits):
        raise ValueError("insufficient route families for disjoint splits")
    total_weight = sum(float(split_weights[s]) for s in splits)
    counts = {split: 1 for split in splits}
    remaining = len(catalog) - len(splits)
    raw = {split: remaining * float(split_weights[split]) / total_weight for split in splits}
    for split in splits:
        counts[split] += int(raw[split])
    leftover = len(catalog) - sum(counts.values())
    order = sorted(splits, key=lambda split: (-(raw[split] - int(raw[split])), split))
    for split in order[:leftover]:
        counts[split] += 1

    partitions = {}
    offset = 0
    for split in splits:
        partitions[split] = [dict(family) for family in catalog[offset:offset + counts[split]]]
        offset += counts[split]
    return partitions


def generate_routes(roadnet, seed, route_count, min_signals):
    """Sample seeded routes from the stable canonical boundary OD catalog."""
    if route_count < 0 or min_signals < 0:
        raise ValueError("route_count and min_signals must be non-negative")
    catalog = build_route_catalog(roadnet, min_signals)
    rng = random.Random(seed)
    return [list(rng.choice(catalog)["route"]) for _ in range(route_count)]


def _vehicle_family(seed, count, motorcycle_ratio):
    if not 0.0 <= motorcycle_ratio <= 1.0:
        raise ValueError("motorcycle_ratio must be between zero and one")
    rng = random.Random(seed + 104729)
    return [
        "motorbike" if rng.random() < motorcycle_ratio else "car"
        for _ in range(count)
    ]


def _sample_families(pool, seed, count):
    rng = random.Random(seed)
    shuffled = list(pool)
    rng.shuffle(shuffled)
    selected = shuffled[:min(count, len(shuffled))]
    while len(selected) < count:
        selected.append(rng.choice(pool))
    return selected


def _scheduled_departures(flow_row):
    if flow_row["startTime"] > flow_row["endTime"]:
        return 0
    return 1 + int((flow_row["endTime"] - flow_row["startTime"])
                   // flow_row["interval"])


def _profile(config, scenario):
    bins = config["regimes"][scenario]["profile_bins"]
    if not bins or bins[0]["start"] != 0 or bins[-1]["end"] != config["horizon_seconds"]:
        raise ValueError("temporal profile must cover the complete horizon")
    if any(bins[index]["end"] != bins[index + 1]["start"]
           for index in range(len(bins) - 1)):
        raise ValueError("temporal profile bins must be contiguous")
    normal_counts = [float(item["source_vehicle_count"])
                     for item in config["regimes"]["normal"]["profile_bins"]]
    normal_mean = sum(normal_counts) / len(normal_counts)
    output = []
    for item in bins:
        count = float(item["source_vehicle_count"])
        if count <= 0 or item["end"] <= item["start"]:
            raise ValueError("temporal profile counts and durations must be positive")
        enriched = dict(item)
        enriched["interval_seconds"] = round(
            float(config["reference_interval_seconds"]) * normal_mean / count, 6
        )
        output.append(enriched)
    return output


def build_flow_cases(roadnet, config, include_catalog=False):
    """Build all seeded split/regime CityFlow cases from resolved inputs."""
    regimes = config["regimes"]
    if set(regimes) != {"normal", "am_peak", "pm_peak"}:
        raise ValueError("normal regime is required")
    catalog = build_route_catalog(
        roadnet, int(config["min_controlled_signals_per_route"])
    )
    partitions = partition_route_families(catalog, config["route_family_split"])
    partitioned_catalog = []
    for split in ("train", "validation", "test"):
        for family in partitions[split]:
            record = dict(family)
            record["split"] = split
            partitioned_catalog.append(record)
    normal_total = sum(item["source_vehicle_count"]
                       for item in regimes["normal"]["profile_bins"])

    cases = []
    for split in ("train", "validation", "test"):
        split_config = config.get("splits", {}).get(split, {})
        demand_seeds = split_config.get("demand_seeds", [])
        sim_seeds = split_config.get("sim_seeds", [])
        if len(demand_seeds) != len(sim_seeds):
            raise ValueError("demand and simulation seeds must be paired")
        for demand_seed, sim_seed in zip(demand_seeds, sim_seeds):
            sampled = _sample_families(
                partitions[split], demand_seed, int(config["route_count"])
            )
            routes = [family["route"] for family in sampled]
            vehicle_kinds = _vehicle_family(
                demand_seed, len(routes), float(config["motorcycle_ratio"])
            )
            histogram = Counter(
                count_controlled_signals(roadnet, route) for route in routes
            )
            for scenario, regime in regimes.items():
                profile = _profile(config, scenario)
                flow = []
                bin_summaries = []
                scheduled_vehicle_counts = {"motorbike": 0, "car": 0}
                for bin_index, profile_bin in enumerate(profile):
                    interval = profile_bin["interval_seconds"]
                    stagger_rng = random.Random(
                        int(demand_seed) * 1009
                        + sum(ord(char) for char in scenario) * 31
                        + bin_index
                    )
                    bin_rows = []
                    for route, kind in zip(routes, vehicle_kinds):
                        offset_bound = max(1, int(interval))
                        row = {
                            "vehicle": dict(VEHICLE_TEMPLATES[kind]),
                            "route": list(route),
                            "interval": interval,
                            "startTime": int(profile_bin["start"]) + stagger_rng.randrange(offset_bound),
                            "endTime": int(profile_bin["end"]) - 1,
                        }
                        bin_rows.append(row)
                        scheduled_vehicle_counts[kind] += _scheduled_departures(row)
                    flow.extend(bin_rows)
                    bin_summary = dict(profile_bin)
                    bin_summary["streams"] = len(bin_rows)
                    bin_summary["scheduled"] = sum(_scheduled_departures(row) for row in bin_rows)
                    bin_summaries.append(bin_summary)
                family_hashes = sorted({family["route_sha256"] for family in sampled})
                family_ids = sorted({family["route_family_id"] for family in sampled})
                cases.append(
                    {
                        "case_id": "%s_%s_demand%s" % (split, scenario, demand_seed),
                        "split": split,
                        "scenario": scenario,
                        "demand_seed": demand_seed,
                        "sim_seed": sim_seed,
                        "scale": sum(item["source_vehicle_count"] for item in regime["profile_bins"]) / float(normal_total),
                        "flow": flow,
                        "flow_streams": len(flow),
                        "scheduled_vehicles": sum(scheduled_vehicle_counts.values()),
                        "scheduled_vehicle_counts": scheduled_vehicle_counts,
                        "scheduled_departures_by_bin": bin_summaries,
                        "temporal_profile": profile,
                        "route_family_ids": family_ids,
                        "route_family_hashes": family_hashes,
                        "route_signal_histogram": {
                            str(signal_count): histogram[signal_count]
                            for signal_count in sorted(histogram)
                        },
                        "data_source_label": config["demand_label"],
                    }
                )
    validate_disjoint_splits(cases)
    if include_catalog:
        return cases, partitioned_catalog
    return cases
