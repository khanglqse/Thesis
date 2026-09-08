"""Audit and demand tooling for the versioned Hai Chau CityFlow dataset."""

from traffic_rl.network.roadnet import RoadNet


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
