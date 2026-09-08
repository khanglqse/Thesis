"""Audit and demand tooling for the versioned Hai Chau CityFlow dataset."""

from collections import Counter, deque
import heapq
import math
import random
import statistics
from xml.etree import ElementTree

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import (
    canonical_sha256,
    sha256_file,
    validate_disjoint_splits,
)


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


def _sumo_signal_logics(path):
    """Return the phase records for every tracked SUMO traffic-light logic."""
    logics = {}
    for logic in ElementTree.parse(str(path)).getroot().findall("tlLogic"):
        logic_id = logic.get("id")
        if not logic_id or logic_id in logics:
            raise ValueError("SUMO signal logic identifiers must be unique")
        phases = []
        for phase in logic.findall("phase"):
            try:
                duration = float(phase.get("duration"))
            except (TypeError, ValueError):
                raise ValueError("SUMO phase duration is invalid for %s" % logic_id)
            if duration <= 0 or duration != int(duration) or not phase.get("state"):
                raise ValueError("SUMO phase semantics are invalid for %s" % logic_id)
            phases.append({"duration": int(duration), "state": phase.get("state")})
        if not phases:
            raise ValueError("SUMO signal logic %s has no phases" % logic_id)
        logics[logic_id] = phases
    return logics


def _source_logic_id(agent_id, logics):
    candidates = [candidate for candidate in (agent_id, "GS_" + agent_id)
                  if candidate in logics]
    if len(candidates) != 1:
        raise ValueError(
            "agent %s must map to exactly one SUMO tlLogic by exact/GS_ identifier"
            % agent_id
        )
    return candidates[0]


def _phase_movements(roadnet, agent_id, phase):
    road_links = roadnet._by_id[agent_id].get("roadLinks", [])
    movements = []
    for road_link_index in phase.get("availableRoadLinks", []):
        if (not isinstance(road_link_index, int) or road_link_index < 0
                or road_link_index >= len(road_links)):
            raise ValueError("phase movement references invalid roadLink")
        road_link = road_links[road_link_index]
        lane_links = [
            [lane_link.get("startLaneIndex"), lane_link.get("endLaneIndex")]
            for lane_link in road_link.get("laneLinks", [])
        ]
        if not lane_links:
            raise ValueError("phase movement has no laneLinks")
        movements.append({
            "road_link_index": road_link_index,
            "start_road": road_link.get("startRoad"),
            "end_road": road_link.get("endRoad"),
            "lane_links": lane_links,
        })
    return movements


def _source_role(state, movements, duration, min_green_seconds):
    lower = state.lower()
    if "y" in lower:
        return "clearance_yellow"
    if "g" in lower:
        if not movements:
            raise ValueError("SUMO green phase has no CityFlow movement")
        if duration >= min_green_seconds:
            return "selectable_green"
        return "compound_service"
    if set(lower) == {"r"} and not movements:
        return "all_red"
    raise ValueError("SUMO state cannot be assigned a fail-closed phase role")


def _synthetic_source_indices(agent_id, phases, source_phases, repair):
    """Validate and map the one documented split-green normalization."""
    if (repair.get("type") != "split_single_action_by_road_link"
            or repair.get("intersection_id") != agent_id
            or repair.get("modeling_status") != "synthetic_engineering_normalization"
            or repair.get("source_evidence") != "unknown_not_recorded"):
        raise ValueError("unsupported phase repair for %s" % agent_id)
    before = repair.get("before")
    after = repair.get("after")
    if after != phases or not isinstance(before, list) or len(before) != 3:
        raise ValueError("synthetic phase repair does not match canonical plan")
    if ([item.get("time") for item in before]
            != [item["duration"] for item in source_phases]):
        raise ValueError("synthetic phase repair does not match SUMO durations")
    if (len(after) != 4 or after[1] != before[1] or after[3] != before[2]
            or before[0].get("time") != after[0].get("time") + after[2].get("time")
            or set(before[0].get("availableRoadLinks", []))
            != set(after[0].get("availableRoadLinks", []))
            | set(after[2].get("availableRoadLinks", []))
            or set(after[0].get("availableRoadLinks", []))
            & set(after[2].get("availableRoadLinks", []))):
        raise ValueError("synthetic split-green transformation is invalid")
    return [0, 1, 0, 2]


def build_phase_contract(roadnet, dataset_id, roadnet_sha256, min_green_seconds,
                         sumo_network_path, sumo_network_record, repairs):
    """Derive policy and transition roles from hash-bound SUMO state strings."""
    if not dataset_id or len(roadnet_sha256) != 64 or min_green_seconds <= 0:
        raise ValueError("phase contract identity and min green are required")
    if (not isinstance(sumo_network_record, dict)
            or set(sumo_network_record) != {"path", "sha256"}
            or sha256_file(sumo_network_path) != sumo_network_record["sha256"]):
        raise ValueError("phase contract SUMO source identity mismatch")
    if not isinstance(repairs, list):
        raise ValueError("phase contract repairs must be a list")
    repair_by_agent = {}
    for repair in repairs:
        agent_id = repair.get("intersection_id") if isinstance(repair, dict) else None
        if not agent_id or agent_id in repair_by_agent:
            raise ValueError("phase contract repair identities must be unique")
        repair_by_agent[agent_id] = repair
    logics = _sumo_signal_logics(sumo_network_path)
    agents = {}
    for agent_id in sorted(roadnet.signalized_ids()):
        phases = roadnet._lightphases(agent_id)
        for phase_index, phase in enumerate(phases):
            duration = phase.get("time")
            if (isinstance(duration, bool)
                    or not isinstance(duration, (int, float))
                    or duration <= 0):
                raise ValueError(
                    "phase %s:%d has invalid duration" % (agent_id, phase_index)
                )
        source_tl_logic_id = _source_logic_id(agent_id, logics)
        source_phases = logics[source_tl_logic_id]
        repair = repair_by_agent.pop(agent_id, None)
        if repair is None:
            if len(source_phases) != len(phases):
                raise ValueError("agent %s phase count differs from SUMO source" % agent_id)
            source_indices = list(range(len(phases)))
            source_alignment = "exact_phase_order_duration_and_state"
        else:
            source_indices = _synthetic_source_indices(
                agent_id, phases, source_phases, repair
            )
            source_alignment = "synthetic_engineering_normalization"

        semantics = []
        for phase_index, phase in enumerate(phases):
            source_index = source_indices[phase_index]
            source_phase = source_phases[source_index]
            duration = phase["time"]
            if repair is None and duration != source_phase["duration"]:
                raise ValueError("agent %s phase duration differs from SUMO source" % agent_id)
            movements = _phase_movements(roadnet, agent_id, phase)
            role = _source_role(
                source_phase["state"], movements, duration, min_green_seconds
            )
            semantics.append({
                "phase_index": phase_index,
                "duration_seconds": duration,
                "source_phase_index": source_index,
                "source_state": source_phase["state"],
                "role": role,
                "movements": movements,
            })
        selectable = [item["phase_index"] for item in semantics
                      if item["role"] == "selectable_green"]
        if len(selectable) < 2:
            raise ValueError(
                "intersection %s has fewer than two selectable green phases"
                % agent_id
            )
        selectable_set = set(selectable)
        transition = [index for index in range(len(phases))
                      if index not in selectable_set]
        compounds = [item["phase_index"] for item in semantics
                     if item["role"] == "compound_service"]
        transitions = {}
        for source in selectable:
            phase_index = (source + 1) % len(phases)
            sequence = []
            while phase_index not in selectable_set:
                sequence.append([phase_index, phases[phase_index]["time"]])
                phase_index = (phase_index + 1) % len(phases)
            if not sequence:
                raise ValueError(
                    "intersection %s has no transition after selectable phase %d"
                    % (agent_id, source)
                )
            transitions[str(source)] = {
                str(target): [list(step) for step in sequence]
                for target in selectable if target != source
            }
        agents[agent_id] = {
            "source_tl_logic_id": source_tl_logic_id,
            "source_alignment": source_alignment,
            "selectable_phases": selectable,
            "compound_phases": compounds,
            "transition_phases": transition,
            "phase_semantics": semantics,
            "transitions": transitions,
        }
    if repair_by_agent:
        raise ValueError("phase repairs reference non-agent intersections")
    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "roadnet_sha256": roadnet_sha256,
        "source_sumo_network": dict(sumo_network_record),
        "id_mapping_rule": "exact CityFlow intersection id, otherwise GS_ prefix",
        "role_vocabulary": {
            "selectable_green": "movement-serving policy action compatible with min_green",
            "compound_service": "movement-serving source stage shorter than min_green; transition-only",
            "clearance_yellow": "source state contains yellow; transition-only lost time",
            "all_red": "source state is all red; transition-only lost time",
        },
        "derivation": {
            "algorithm": "sumo_tllogic_phase_roles_v2",
            "min_green_seconds": min_green_seconds,
            "selectable_rule": (
                "SUMO state has green and no yellow, CityFlow phase serves movement, "
                "and declared duration is min-green compatible"
            ),
            "compound_rule": (
                "SUMO state has green and no yellow and serves movement, but declared "
                "duration is shorter than min-green; preserve only inside transitions"
            ),
            "clearance_rule": (
                "any SUMO state containing yellow is clearance_yellow even when its "
                "CityFlow conversion retains permitted movements"
            ),
            "all_red_rule": (
                "SUMO state contains only red and CityFlow permits no movement"
            ),
            "transition_rule": (
                "preserve every non-selectable phase after a selectable source "
                "in cyclic plan order until the next selectable phase; use that "
                "source-exit sequence for every directed switch"
            ),
        },
        "limitations": {
            "source_signal_states": (
                "tracked SUMO tlLogic state strings, bound by source_sumo_network hash"
            ),
            "synthetic_normalization": (
                "intersection 5896811072 splits one source action into two policy "
                "actions exactly as declared by the provenance repair"
            ),
        },
        "agents": agents,
    }


def validate_phase_contract(roadnet, contract, dataset_id, roadnet_sha256,
                            min_green_seconds, sumo_network_path,
                            sumo_network_record, repairs):
    """Reject any phase contract that differs from deterministic derivation."""
    expected = build_phase_contract(
        roadnet, dataset_id, roadnet_sha256, min_green_seconds,
        sumo_network_path, sumo_network_record, repairs
    )
    if contract != expected:
        raise ValueError("phase contract differs from deterministic phase plan roles")
    return expected


def audit_network(path, phase_contract=None, min_green_seconds=20,
                  sumo_network_path=None, sumo_network_record=None, repairs=None):
    """Return deterministic graph counts and all detected phase-reference errors."""
    roadnet = RoadNet.load(str(path))
    road_by_id = roadnet._road_by_id
    intersection_ids = set(roadnet._by_id)
    agents = sorted(roadnet.signalized_ids())
    agent_set = set(agents)
    selectable_phase_counts = {agent_id: 0 for agent_id in agents}
    transition_phase_counts = {agent_id: 0 for agent_id in agents}
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
        if intersection_id in agent_set:
            phases = traffic_light.get("lightphases", [])
            selectable_phase_counts[intersection_id] = sum(
                1 for phase in phases
                if phase.get("availableRoadLinks")
                and isinstance(phase.get("time"), (int, float))
                and not isinstance(phase.get("time"), bool)
                and phase["time"] >= min_green_seconds
            )
            transition_phase_counts[intersection_id] = (
                len(phases) - selectable_phase_counts[intersection_id]
            )
            if selectable_phase_counts[intersection_id] < 2:
                errors.append(
                    "intersection %s has fewer than two selectable green phases"
                    % intersection_id
                )

    if phase_contract is not None:
        try:
            validated_contract = validate_phase_contract(
                roadnet,
                phase_contract,
                phase_contract.get("dataset_id"),
                sha256_file(path),
                min_green_seconds,
                sumo_network_path,
                sumo_network_record,
                repairs,
            )
            selectable_phase_counts = {
                agent_id: len(validated_contract["agents"][agent_id]["selectable_phases"])
                for agent_id in agents
            }
            transition_phase_counts = {
                agent_id: len(validated_contract["agents"][agent_id]["transition_phases"])
                for agent_id in agents
            }
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            errors.append("phase contract: %s" % error)

    signal_adjacency = roadnet.signal_adjacency()
    edges = [tuple(edge) for edge in signal_adjacency["directed_edges"]]
    return {
        "roads": len(roadnet.roads),
        "lanes": sum(len(road.get("lanes", [])) for road in roadnet.roads),
        "intersections": len(roadnet.intersections),
        "controlled_signals": len(agents),
        "selectable_green_phases": sum(selectable_phase_counts.values()),
        "transition_phases": sum(transition_phase_counts.values()),
        "agent_selectable_phase_counts": selectable_phase_counts,
        "agent_ids": agents,
        "directed_signal_edges": [list(edge) for edge in edges],
        "weak_components": signal_adjacency["stats"]["weak_components"],
        "signal_adjacency": signal_adjacency,
        "signal_adjacency_sha256": canonical_sha256(signal_adjacency),
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


def controlled_signal_ids(roadnet, route):
    """Return the stable controlled-intersection set crossed by a route."""
    controlled = set(roadnet.signalized_ids())
    return sorted({
        roadnet._road_by_id[road_id]["endIntersection"]
        for road_id in route
        if road_id in roadnet._road_by_id
        and roadnet._road_by_id[road_id]["endIntersection"] in controlled
    })


def route_length_meters(roadnet, route):
    """Measure a CityFlow route from its projected road polylines."""
    total = 0.0
    for road_id in route:
        road = roadnet._road_by_id[road_id]
        points = road.get("points", [])
        length = sum(
            math.hypot(float(end["x"]) - float(start["x"]),
                       float(end["y"]) - float(start["y"]))
            for start, end in zip(points, points[1:])
        )
        # Small unit fixtures omit geometry. The fallback preserves a positive,
        # deterministic edge cost without making claims about physical length.
        total += length if length > 0 else 1.0
    return total


def _shortest_path_tree(roadnet, start):
    """Return deterministic metric-shortest paths from one boundary road."""
    initial = route_length_meters(roadnet, [start])
    costs = {start: initial}
    previous = {}
    pending = [(initial, start)]
    while pending:
        cost, road_id = heapq.heappop(pending)
        if costs.get(road_id) != cost:
            continue
        for next_road in sorted(roadnet.next_roads(road_id)):
            if next_road not in roadnet._road_by_id:
                continue
            next_cost = cost + route_length_meters(roadnet, [next_road])
            if (next_road not in costs or next_cost < costs[next_road]
                    or (next_cost == costs[next_road]
                        and road_id < previous.get(next_road, road_id + "\uffff"))):
                costs[next_road] = next_cost
                previous[next_road] = road_id
                heapq.heappush(pending, (next_cost, next_road))
    paths = {}
    for target in costs:
        route = [target]
        while route[-1] != start:
            route.append(previous[route[-1]])
        paths[target] = list(reversed(route))
    return paths


def _shortest_route(roadnet, start, target):
    path = _shortest_path_tree(roadnet, start).get(target)
    return path if path is not None and len(path) > 1 else None


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


def _route_family(roadnet, route, derivation, shortest_length, coverage_target=None):
    route_hash = canonical_sha256(route)
    length = route_length_meters(roadnet, route)
    record = {
        "route_family_id": "rf_" + route_hash,
        "route_sha256": route_hash,
        "origin_road": route[0],
        "destination_road": route[-1],
        "controlled_signals": count_controlled_signals(roadnet, route),
        "controlled_signal_ids": controlled_signal_ids(roadnet, route),
        "road_count": len(route),
        "route_length_meters": round(length, 6),
        "shortest_od_length_meters": round(shortest_length, 6),
        "stretch_ratio": round(length / shortest_length, 6),
        "derivation": derivation,
        "route": route,
    }
    if coverage_target is not None:
        record["coverage_target_signal_id"] = coverage_target
    return record


def _route_has_repeated_intersection(roadnet, route):
    intersections = [roadnet._road_by_id[road_id]["startIntersection"]
                     for road_id in route]
    intersections.append(roadnet._road_by_id[route[-1]]["endIntersection"])
    return len(intersections) != len(set(intersections))


def _supplemental_signal_routes(roadnet, signal_id, min_signals, entries,
                                exits, trees, known_hashes, count,
                                max_stretch_ratio):
    """Choose short, simple boundary routes constrained through one signal."""
    incoming = sorted(
        road["id"] for road in roadnet.roads
        if road.get("endIntersection") == signal_id
    )
    candidates = {}
    for entry in entries:
        entry_tree = trees[entry]
        for anchor in incoming:
            prefix = entry_tree.get(anchor)
            anchor_tree = trees.get(anchor, {})
            if prefix is None:
                continue
            for exit_road in exits:
                suffix = anchor_tree.get(exit_road)
                shortest = entry_tree.get(exit_road)
                if suffix is None or shortest is None:
                    continue
                route = prefix + suffix[1:]
                route_hash = canonical_sha256(route)
                if (route_hash in known_hashes or route_hash in candidates
                        or signal_id not in controlled_signal_ids(roadnet, route)
                        or _route_has_repeated_intersection(roadnet, route)
                        or not route_is_valid(roadnet, route, min_signals)):
                    continue
                length = route_length_meters(roadnet, route)
                shortest_length = route_length_meters(roadnet, shortest)
                stretch = length / shortest_length
                if stretch <= max_stretch_ratio:
                    candidates[route_hash] = (
                        stretch, length, entry, exit_road, route, shortest_length
                    )
    ordered = sorted(candidates.values(), key=lambda item: item[:4])
    selected = []
    used_od = set()
    # Distinct ODs are preferred so coverage routes do not create one artificial
    # origin/destination hotspot. A second pass fills only if the graph requires it.
    for allow_repeated_od in (False, True):
        for _, _, entry, exit_road, route, shortest_length in ordered:
            od = (entry, exit_road)
            if not allow_repeated_od and od in used_od:
                continue
            route_hash = canonical_sha256(route)
            if route_hash in {item["route_sha256"] for item in selected}:
                continue
            selected.append(_route_family(
                roadnet, route, "coverage_constrained_metric_shortest",
                shortest_length, signal_id
            ))
            used_od.add(od)
            if len(selected) == count:
                return selected
    return selected


def build_route_catalog(roadnet, min_signals, required_signal_ids=None,
                        minimum_route_families_per_signal=0,
                        max_stretch_ratio=1.25):
    """Build metric-shortest OD routes plus bounded signal-coverage routes."""
    entries = sorted(roadnet.entry_roads())
    virtual = {i["id"] for i in roadnet.intersections if i.get("virtual")}
    exits = sorted(r["id"] for r in roadnet.roads
                   if r.get("endIntersection") in virtual)
    if (isinstance(minimum_route_families_per_signal, bool)
            or not isinstance(minimum_route_families_per_signal, int)
            or minimum_route_families_per_signal < 0
            or isinstance(max_stretch_ratio, bool)
            or not isinstance(max_stretch_ratio, (int, float))
            or max_stretch_ratio < 1.0):
        raise ValueError("route coverage settings are invalid")
    controlled = set(roadnet.signalized_ids())
    required = sorted(set(required_signal_ids or []))
    unknown = sorted(set(required) - controlled)
    if unknown:
        raise ValueError("route coverage references unknown controlled signals: %s" % unknown)
    trees = {start: _shortest_path_tree(roadnet, start) for start in entries}
    catalog = []
    for entry in entries:
        for exit_road in exits:
            route = trees[entry].get(exit_road)
            if (route is None or _route_has_repeated_intersection(roadnet, route)
                    or not route_is_valid(roadnet, route, min_signals)):
                continue
            length = route_length_meters(roadnet, route)
            catalog.append(_route_family(
                roadnet, route, "metric_shortest_boundary_od", length
            ))
    known_hashes = {family["route_sha256"] for family in catalog}
    for signal_id in required:
        existing_count = sum(
            signal_id in family["controlled_signal_ids"] for family in catalog
        )
        needed = max(0, minimum_route_families_per_signal - existing_count)
        if not needed:
            continue
        for road in roadnet.roads:
            if road.get("endIntersection") == signal_id and road["id"] not in trees:
                trees[road["id"]] = _shortest_path_tree(roadnet, road["id"])
        additions = _supplemental_signal_routes(
            roadnet, signal_id, min_signals, entries, exits, trees,
            known_hashes, needed, max_stretch_ratio
        )
        catalog.extend(additions)
        known_hashes.update(family["route_sha256"] for family in additions)
    catalog.sort(key=lambda family: family["route_sha256"])
    if not catalog:
        raise ValueError("insufficient multi-signal route families")
    missing = sorted(set(required) - {
        signal_id for family in catalog
        for signal_id in family["controlled_signal_ids"]
    })
    insufficient = sorted(
        signal_id for signal_id in required
        if sum(signal_id in family["controlled_signal_ids"] for family in catalog) < 3
    )
    if missing or insufficient:
        raise ValueError(
            "plausible boundary routes cannot cover required controlled signals; "
            "inactive=%s fewer_than_three_families=%s" % (missing, insufficient)
        )
    return catalog


def _covered_signals(families):
    return {
        signal_id for family in families
        for signal_id in family.get("controlled_signal_ids", [])
    }


def partition_route_families(catalog, split_weights, required_signal_ids=None):
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

    required = set(required_signal_ids or [])
    partitions = {split: [] for split in splits}
    unassigned = {family["route_sha256"]: family for family in catalog}
    if required:
        absent = sorted(required - _covered_signals(catalog))
        if absent:
            raise ValueError("route partition cannot cover controlled signals: %s" % absent)
        for split_index, split in enumerate(splits):
            uncovered = set(required)
            future_splits = len(splits) - split_index - 1
            while uncovered:
                signal_counts = Counter(
                    signal_id for family in unassigned.values()
                    for signal_id in set(family["controlled_signal_ids"]) & required
                )
                candidates = []
                for family in unassigned.values():
                    gains = set(family["controlled_signal_ids"]) & uncovered
                    if not gains:
                        continue
                    covered_required = set(family["controlled_signal_ids"]) & required
                    if any(signal_counts[signal_id] <= future_splits
                           for signal_id in covered_required):
                        continue
                    candidates.append((
                        -len(gains),
                        family["stretch_ratio"],
                        family["route_length_meters"],
                        family["route_sha256"],
                        family,
                    ))
                if not candidates:
                    raise ValueError(
                        "route partition cannot preserve per-split coverage; "
                        "split=%s inactive=%s" % (split, sorted(uncovered))
                    )
                family = min(candidates)[-1]
                partitions[split].append(dict(family))
                del unassigned[family["route_sha256"]]
                uncovered.difference_update(family["controlled_signal_ids"])

    ordered_remaining = [family for family in catalog
                         if family["route_sha256"] in unassigned]
    offset = 0
    for split in splits:
        needed = counts[split] - len(partitions[split])
        if needed < 0:
            raise ValueError("route coverage seed exceeds weighted split capacity")
        partitions[split].extend(
            dict(family) for family in ordered_remaining[offset:offset + needed]
        )
        offset += needed
    if offset != len(ordered_remaining):
        raise ValueError("route partition accounting mismatch")
    if required:
        inactive = {
            split: sorted(required - _covered_signals(partitions[split]))
            for split in splits
        }
        if any(inactive.values()):
            raise ValueError("route partition coverage failed: %s" % inactive)
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


def _sample_families(pool, seed, count, required_signal_ids=None):
    if not pool and count:
        raise ValueError("cannot sample routes from an empty partition")
    rng = random.Random(seed)
    shuffled = list(pool)
    rng.shuffle(shuffled)
    required = set(required_signal_ids or [])
    selected = []
    uncovered = set(required)
    while uncovered:
        candidates = [family for family in shuffled if family not in selected]
        candidates = [
            family for family in candidates
            if set(family.get("controlled_signal_ids", [])) & uncovered
        ]
        if not candidates or len(selected) >= count:
            raise ValueError(
                "route sample cannot cover controlled signals; inactive=%s count=%s"
                % (sorted(uncovered), count)
            )
        family = max(
            candidates,
            key=lambda item: len(set(item["controlled_signal_ids"]) & uncovered)
        )
        selected.append(family)
        uncovered.difference_update(family["controlled_signal_ids"])
    selected.extend(
        family for family in shuffled
        if family not in selected and len(selected) < count
    )
    while len(selected) < count:
        selected.append(rng.choice(pool))
    return selected


def _coverage_config(roadnet, config):
    contract = config.get("route_coverage")
    if contract is None:
        return {
            "required": [],
            "minimum_route_families_per_signal": 0,
            "max_route_stretch_ratio": 1.25,
            "require_each_split": False,
            "require_each_case": False,
        }
    expected = {
        "required_controlled_signals", "minimum_route_families_per_signal",
        "max_route_stretch_ratio", "require_each_split", "require_each_case",
    }
    if not isinstance(contract, dict) or set(contract) != expected:
        raise ValueError("route_coverage contract schema mismatch")
    requested = contract["required_controlled_signals"]
    if requested == "all":
        required = sorted(roadnet.signalized_ids())
    elif isinstance(requested, list) and all(isinstance(item, str) for item in requested):
        required = sorted(set(requested))
    else:
        raise ValueError("required_controlled_signals must be all or a list")
    if (not isinstance(contract["require_each_split"], bool)
            or not isinstance(contract["require_each_case"], bool)):
        raise ValueError("route coverage gates must be boolean")
    minimum = contract["minimum_route_families_per_signal"]
    if (isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0):
        raise ValueError("minimum route families per signal must be a non-negative integer")
    if contract["require_each_split"] and required and minimum < 3:
        raise ValueError(
            "minimum route families per signal must be at least three for disjoint splits"
        )
    return {
        "required": required,
        "minimum_route_families_per_signal": minimum,
        "max_route_stretch_ratio": contract["max_route_stretch_ratio"],
        "require_each_split": contract["require_each_split"],
        "require_each_case": contract["require_each_case"],
    }


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
    coverage = _coverage_config(roadnet, config)
    catalog = build_route_catalog(
        roadnet,
        int(config["min_controlled_signals_per_route"]),
        required_signal_ids=coverage["required"],
        minimum_route_families_per_signal=coverage["minimum_route_families_per_signal"],
        max_stretch_ratio=coverage["max_route_stretch_ratio"],
    )
    partitions = partition_route_families(
        catalog,
        config["route_family_split"],
        coverage["required"] if coverage["require_each_split"] else None,
    )
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
                partitions[split], demand_seed, int(config["route_count"]),
                coverage["required"] if coverage["require_each_case"] else None,
            )
            routes = [family["route"] for family in sampled]
            vehicle_kinds = _vehicle_family(
                demand_seed, len(routes), float(config["motorcycle_ratio"])
            )
            histogram = Counter(
                count_controlled_signals(roadnet, route) for route in routes
            )
            active_signal_ids = sorted(_covered_signals(sampled))
            inactive_signal_ids = sorted(
                set(coverage["required"]) - set(active_signal_ids)
            )
            if coverage["require_each_case"] and inactive_signal_ids:
                raise ValueError(
                    "case route coverage failed; split=%s demand_seed=%s inactive=%s"
                    % (split, demand_seed, inactive_signal_ids)
                )
            route_lengths = [family["route_length_meters"] for family in sampled]
            unique_ods = {
                (family["origin_road"], family["destination_road"])
                for family in sampled
            }
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
                        "active_controlled_signal_ids": active_signal_ids,
                        "active_controlled_signals": len(active_signal_ids),
                        "inactive_controlled_signal_ids": inactive_signal_ids,
                        "unique_origin_destination_pairs": len(unique_ods),
                        "route_length_meters": {
                            "minimum": round(min(route_lengths), 6),
                            "median": round(statistics.median(route_lengths), 6),
                            "mean": round(statistics.mean(route_lengths), 6),
                            "maximum": round(max(route_lengths), 6),
                        },
                        "data_source_label": config["demand_label"],
                    }
                )
    validate_disjoint_splits(cases)
    if include_catalog:
        return cases, partitioned_catalog
    return cases


def build_route_coverage_provenance(roadnet, config, catalog, cases):
    """Summarize the route-generation gates bound into the experiment manifest."""
    coverage = _coverage_config(roadnet, config)
    required = set(coverage["required"])
    lengths = [family["route_length_meters"] for family in catalog]
    by_split = {}
    for split in ("train", "validation", "test"):
        families = [family for family in catalog if family["split"] == split]
        active = _covered_signals(families)
        by_split[split] = {
            "active_controlled_signal_ids": sorted(active),
            "active_controlled_signals": len(active),
            "inactive_required_signal_ids": sorted(required - active),
            "route_families": len(families),
            "unique_origin_destination_pairs": len({
                (family["origin_road"], family["destination_road"])
                for family in families
            }),
        }
    per_case = {
        case["case_id"]: {
            "active_controlled_signals": case["active_controlled_signals"],
            "inactive_required_signal_ids": case["inactive_controlled_signal_ids"],
            "unique_origin_destination_pairs": case["unique_origin_destination_pairs"],
        }
        for case in cases
    }
    inactive_catalog = sorted(required - _covered_signals(catalog))
    if inactive_catalog:
        raise ValueError("route coverage provenance has inactive signals: %s" % inactive_catalog)
    return {
        "schema_version": 1,
        "required_controlled_signal_ids": sorted(required),
        "required_controlled_signals": len(required),
        "catalog_active_controlled_signal_ids": sorted(_covered_signals(catalog)),
        "catalog_inactive_required_signal_ids": inactive_catalog,
        "base_route_algorithm": "deterministic_metric_shortest_boundary_od",
        "supplemental_route_algorithm": (
            "deterministic_simple_boundary_route_constrained_through_signal"
        ),
        "minimum_route_families_per_signal": coverage["minimum_route_families_per_signal"],
        "maximum_supplemental_stretch_ratio": coverage["max_route_stretch_ratio"],
        "loop_rule": "no repeated road or intersection in any route family",
        "partition_rule": "disjoint weighted partitions seeded by required-signal set cover",
        "case_sampling_rule": "seeded required-signal set cover then seeded family sample",
        "require_each_split": coverage["require_each_split"],
        "require_each_case": coverage["require_each_case"],
        "split_coverage": by_split,
        "case_coverage": per_case,
        "catalog_statistics": {
            "route_families": len(catalog),
            "unique_origin_destination_pairs": len({
                (family["origin_road"], family["destination_road"])
                for family in catalog
            }),
            "alternative_route_families": sum(
                family["derivation"] == "coverage_constrained_metric_shortest"
                for family in catalog
            ),
            "route_length_meters": {
                "minimum": round(min(lengths), 6),
                "median": round(statistics.median(lengths), 6),
                "mean": round(statistics.mean(lengths), 6),
                "maximum": round(max(lengths), 6),
            },
        },
    }
