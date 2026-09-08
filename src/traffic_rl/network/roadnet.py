"""Parse a CityFlow roadnet.json into convenient lookups for env + flow generation.

NOTE: must stay importable under Python 3.6 (the CityFlow Docker image), so no
`from __future__ import annotations`. The `dataclasses` backport is pip-installed
in the container (see Makefile cf-test / the run_fixed_time invocation).
"""
import json
import hashlib
import heapq
import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RoadNet:
    intersections: List[dict]
    roads: List[dict]
    _by_id: Dict[str, dict]
    _road_by_id: Dict[str, dict]
    _next: Dict[str, List[str]]
    _phase_contract_data: object = None
    _signal_adjacency_data: object = None

    @classmethod
    def load(cls, path: str, phase_contract_path=None,
             require_phase_contract=False,
             expected_phase_contract_sha256=None) -> "RoadNet":
        with open(path) as f:
            data = json.load(f)
        contract_data = None
        if phase_contract_path is not None:
            contract_digest = hashlib.sha256()
            with open(phase_contract_path, "rb") as source:
                contract_digest.update(source.read())
            if expected_phase_contract_sha256 is not None \
                    and contract_digest.hexdigest() != expected_phase_contract_sha256:
                raise ValueError("phase contract artifact sha256 mismatch")
            with open(phase_contract_path) as source:
                contract_data = json.load(source)
            digest = hashlib.sha256()
            with open(path, "rb") as source:
                digest.update(source.read())
            if contract_data.get("roadnet_sha256") != digest.hexdigest():
                raise ValueError("phase contract roadnet_sha256 mismatch")
        elif require_phase_contract:
            raise ValueError("explicit phase contract is required")
        by_id = {i["id"]: i for i in data["intersections"]}
        road_by_id = {r["id"]: r for r in data["roads"]}
        # Build road->road adjacency from every intersection's roadLinks.
        nxt: Dict[str, List[str]] = {r["id"]: [] for r in data["roads"]}
        for inter in data["intersections"]:
            for link in inter.get("roadLinks", []):
                start, end = link["startRoad"], link["endRoad"]
                # setdefault guards against roadLinks referencing a road not in
                # data["roads"] (possible with converter artifacts on large nets).
                if end not in nxt.setdefault(start, []):
                    nxt[start].append(end)
        roadnet = cls(data["intersections"], data["roads"], by_id, road_by_id,
                      nxt, contract_data)
        if contract_data is not None:
            audit = roadnet.phase_contract_audit()
            if audit["errors"]:
                raise ValueError("invalid explicit phase contract: %s" %
                                 json.dumps(audit["errors"], sort_keys=True))
        return roadnet

    def signalized_ids(self) -> List[str]:
        # A real controllable signal has >1 phase. The CityFlow converter emits a
        # trivial single-phase trafficLight for every non-signalized junction;
        # those are excluded so they don't become bogus agents.
        return [
            i["id"] for i in self.intersections
            if not i.get("virtual") and i.get("trafficLight")
            and len(i["trafficLight"].get("lightphases", [])) > 1
        ]

    def num_phases(self, inter_id: str) -> int:
        return len(self._by_id[inter_id]["trafficLight"]["lightphases"])

    def _lane_ids(self, road_id: str) -> List[str]:
        road = self._road_by_id[road_id]
        return [f"{road_id}_{idx}" for idx in range(len(road["lanes"]))]

    def incoming_lanes(self, inter_id: str) -> List[str]:
        lanes: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            if self._road_by_id[road_id]["endIntersection"] == inter_id:
                lanes.extend(self._lane_ids(road_id))
        return lanes

    def outgoing_lanes(self, inter_id: str) -> List[str]:
        lanes: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            if self._road_by_id[road_id]["startIntersection"] == inter_id:
                lanes.extend(self._lane_ids(road_id))
        return lanes

    def next_roads(self, road_id: str) -> List[str]:
        return self._next.get(road_id, [])

    def _lightphases(self, inter_id: str) -> List[dict]:
        return self._by_id[inter_id]["trafficLight"]["lightphases"]

    def green_phases(self, inter_id: str) -> List[int]:
        """Policy-selectable green phases from the explicit phase-role contract."""
        return self.phase_contract(inter_id)["selectable_phases"]

    def all_red_phase(self, inter_id: str):
        """First all-red / yellow lightphase index (empty availableRoadLinks), or None."""
        for idx, ph in enumerate(self._lightphases(inter_id)):
            if not ph.get("availableRoadLinks"):
                return idx
        return None

    def phase_movements(self, inter_id: str, phase_idx: int):
        """Deduped (incoming_lanes, outgoing_lanes) served by a lightphase."""
        inter = self._by_id[inter_id]
        road_links = inter["roadLinks"]
        ph = self._lightphases(inter_id)[phase_idx]
        inc, out = [], []
        for rl_idx in ph.get("availableRoadLinks", []):
            rl = road_links[rl_idx]
            for ll in rl["laneLinks"]:
                il = "{}_{}".format(rl["startRoad"], ll["startLaneIndex"])
                ol = "{}_{}".format(rl["endRoad"], ll["endLaneIndex"])
                if il not in inc:
                    inc.append(il)
                if ol not in out:
                    out.append(ol)
        return inc, out

    def phase_movement_pairs(self, inter_id: str, phase_idx: int):
        """Deduplicated lane-to-lane movement pairs served by a phase."""
        inter = self._by_id[inter_id]
        phase = self._lightphases(inter_id)[phase_idx]
        pairs = []
        for road_link_index in phase.get("availableRoadLinks", []):
            road_link = inter["roadLinks"][road_link_index]
            for lane_link in road_link.get("laneLinks", []):
                pair = (
                    "{}_{}".format(road_link["startRoad"],
                                   lane_link["startLaneIndex"]),
                    "{}_{}".format(road_link["endRoad"],
                                   lane_link["endLaneIndex"]),
                )
                if pair not in pairs:
                    pairs.append(pair)
        return pairs

    def phase_movement_records(self, inter_id, phase_idx):
        """Canonical road-link movement records used by phase provenance."""
        inter = self._by_id[inter_id]
        phase = self._lightphases(inter_id)[phase_idx]
        records = []
        for road_link_index in phase.get("availableRoadLinks", []):
            road_link = inter["roadLinks"][road_link_index]
            records.append({
                "road_link_index": road_link_index,
                "start_road": road_link["startRoad"],
                "end_road": road_link["endRoad"],
                "lane_links": [[lane_link["startLaneIndex"],
                                lane_link["endLaneIndex"]]
                               for lane_link in road_link.get("laneLinks", [])],
            })
        return records

    def phase_contract(self, inter_id: str, transition_max_seconds=6.0):
        """Classify selectable greens and the transition after each green.

        This deterministic fallback exists for unit fixtures without SUMO source
        states. It treats a short non-empty subset stage as compound service and
        an empty stage as all-red. Production callers load the hash-bound explicit
        contract, which distinguishes compound service, yellow, and all-red.
        """
        if self._phase_contract_data is not None:
            return self._explicit_phase_contract(inter_id)
        phases = self._lightphases(inter_id)
        movements = [set(self.phase_movement_pairs(inter_id, index))
                     for index in range(len(phases))]
        long_greens = [index for index, phase in enumerate(phases)
                       if movements[index]
                       and float(phase.get("time", 0)) > transition_max_seconds]
        transition_phases = []
        for index, phase in enumerate(phases):
            if not movements[index]:
                transition_phases.append(index)
                continue
            duration = float(phase.get("time", 0))
            if duration > transition_max_seconds:
                continue
            adjacent = ((index - 1) % len(phases), (index + 1) % len(phases))
            if any(neighbor in long_greens
                   and movements[index].issubset(movements[neighbor])
                   for neighbor in adjacent):
                transition_phases.append(index)

        selectable = [index for index in range(len(phases))
                      if movements[index] and index not in transition_phases]
        errors = []
        if len(selectable) < 2:
            errors.append("intersection {} has fewer than two selectable greens".format(
                inter_id))
        transitions_after = {}
        selectable_set = set(selectable)
        transition_set = set(transition_phases)
        for source in selectable:
            sequence = []
            cursor = (source + 1) % len(phases)
            while cursor != source and cursor not in selectable_set:
                if cursor not in transition_set:
                    break
                duration = phases[cursor].get("time")
                if not isinstance(duration, (int, float)) or duration <= 0 \
                        or int(duration) != duration:
                    errors.append(
                        "intersection {} transition phase {} has invalid duration".format(
                            inter_id, cursor))
                    break
                sequence.append((cursor, int(duration)))
                cursor = (cursor + 1) % len(phases)
            if not sequence:
                errors.append(
                    "intersection {} selectable phase {} has no transition path".format(
                        inter_id, source))
            transitions_after[str(source)] = sequence
        directed = {
            str(source): {
                str(target): list(transitions_after[str(source)])
                for target in selectable if target != source}
            for source in selectable}
        phase_roles = {
            index: ("selectable_green" if index in selectable_set
                    else "compound_service" if movements[index]
                    else "all_red")
            for index in range(len(phases))}
        phase_semantics = {
            index: {"phase_index": index,
                    "duration_seconds": phases[index].get("time"),
                    "role": phase_roles[index],
                    "movements": self.phase_movement_records(inter_id, index)}
            for index in range(len(phases))}
        return {
            "schema_version": 1,
            "selectable_phases": selectable,
            "transition_phases": sorted(transition_phases),
            "transitions_after": transitions_after,
            "transitions": directed,
            "phase_roles": phase_roles,
            "phase_semantics": phase_semantics,
            "errors": sorted(set(errors)),
        }

    def _explicit_phase_contract(self, inter_id):
        data = self._phase_contract_data
        errors = []
        if data.get("schema_version") != 1:
            errors.append("phase contract schema_version must be 1")
        min_green = data.get("derivation", {}).get("min_green_seconds")
        if not isinstance(min_green, (int, float)) or min_green <= 0:
            errors.append("phase contract derivation min_green_seconds is invalid")
        agents = data.get("agents", {})
        expected_agents = set(self.signalized_ids())
        actual_agents = set(agents)
        if actual_agents != expected_agents:
            errors.append("phase contract agent IDs differ from roadnet")
        record = agents.get(inter_id, {})
        selectable = record.get("selectable_phases", [])
        transitions = record.get("transition_phases", [])
        compound = record.get("compound_phases", [])
        phase_count = self.num_phases(inter_id)
        all_indices = selectable + transitions
        if len(selectable) < 2:
            errors.append("intersection {} has fewer than two selectable greens".format(
                inter_id))
        if sorted(all_indices) != list(range(phase_count)) \
                or len(set(all_indices)) != len(all_indices):
            errors.append("intersection {} phase roles do not partition plan".format(
                inter_id))
        for phase_index in selectable:
            if phase_index < 0 or phase_index >= phase_count \
                    or not self.phase_movement_pairs(inter_id, phase_index):
                errors.append("intersection {} selectable phase {} is invalid".format(
                    inter_id, phase_index))
            elif isinstance(min_green, (int, float)) \
                    and float(self._lightphases(inter_id)[phase_index].get(
                        "time", 0)) < float(min_green):
                errors.append(
                    "intersection {} selectable phase {} is shorter than min_green".format(
                        inter_id, phase_index))
        allowed_roles = set(("selectable_green", "compound_service",
                             "clearance_yellow", "all_red"))
        semantics = record.get("phase_semantics", [])
        phase_roles = {}
        phase_semantics = {}
        if len(semantics) != phase_count:
            errors.append("intersection {} phase_semantics length mismatch".format(
                inter_id))
        for semantic in semantics:
            phase_index = semantic.get("phase_index")
            role = semantic.get("role")
            if not isinstance(phase_index, int) or not 0 <= phase_index < phase_count:
                errors.append("intersection {} phase semantic index is invalid".format(
                    inter_id))
                continue
            if role not in allowed_roles:
                errors.append("intersection {} phase {} role is invalid".format(
                    inter_id, phase_index))
                continue
            if phase_index in phase_roles:
                errors.append("intersection {} phase semantic is duplicated".format(
                    inter_id))
            phase_roles[phase_index] = role
            phase_semantics[phase_index] = semantic
            duration = semantic.get("duration_seconds")
            if duration != self._lightphases(inter_id)[phase_index].get("time"):
                errors.append("intersection {} phase {} duration mismatch".format(
                    inter_id, phase_index))
            if semantic.get("movements") != self.phase_movement_records(
                    inter_id, phase_index):
                errors.append("intersection {} phase {} movements mismatch".format(
                    inter_id, phase_index))
            source_state = semantic.get("source_state", "")
            if not isinstance(source_state, str):
                source_state = ""
            duration_valid = (isinstance(duration, (int, float))
                              and not isinstance(duration, bool))
            if role == "selectable_green" and (
                    "g" not in source_state.lower()
                    or "y" in source_state.lower()):
                errors.append("intersection {} phase {} green semantics invalid".format(
                    inter_id, phase_index))
            if role == "compound_service" and (
                    not semantic.get("movements")
                    or not isinstance(min_green, (int, float))
                    or not duration_valid
                    or duration >= min_green
                    or "g" not in source_state.lower()
                    or "y" in source_state.lower()):
                errors.append("intersection {} phase {} compound semantics invalid".format(
                    inter_id, phase_index))
            if role == "clearance_yellow" and "y" not in source_state.lower():
                errors.append("intersection {} phase {} yellow semantics invalid".format(
                    inter_id, phase_index))
            if role == "all_red" and (semantic.get("movements")
                                       or set(source_state.lower()) - set("r")):
                errors.append("intersection {} phase {} all-red semantics invalid".format(
                    inter_id, phase_index))
        semantic_selectable = sorted(
            index for index, role in phase_roles.items()
            if role == "selectable_green")
        semantic_compound = sorted(
            index for index, role in phase_roles.items()
            if role == "compound_service")
        semantic_transitions = sorted(
            index for index, role in phase_roles.items()
            if role != "selectable_green")
        if semantic_selectable != sorted(selectable):
            errors.append("intersection {} selectable phase semantics mismatch".format(
                inter_id))
        if semantic_compound != sorted(compound):
            errors.append("intersection {} compound phase semantics mismatch".format(
                inter_id))
        if semantic_transitions != sorted(transitions):
            errors.append("intersection {} transition phase semantics mismatch".format(
                inter_id))
        mapping = record.get("transitions", {})
        normalized = {}
        for source in selectable:
            targets = mapping.get(str(source), {})
            normalized[str(source)] = {}
            expected_chain = []
            cursor = (source + 1) % phase_count
            while cursor not in set(selectable):
                phase = self._lightphases(inter_id)[cursor]
                duration = phase.get("time")
                expected_chain.append((cursor, duration))
                cursor = (cursor + 1) % phase_count
            for target in selectable:
                if target == source:
                    continue
                raw = targets.get(str(target))
                if raw is None:
                    errors.append(
                        "intersection {} transition {}->{} is missing".format(
                            inter_id, source, target))
                    continue
                sequence = [tuple(item) for item in raw]
                if sequence != expected_chain or not sequence:
                    errors.append(
                        "intersection {} transition {}->{} differs from plan".format(
                            inter_id, source, target))
                for phase_index, duration in sequence:
                    if phase_index not in transitions or not isinstance(duration, int) \
                            or duration <= 0:
                        errors.append(
                            "intersection {} transition {}->{} is invalid".format(
                                inter_id, source, target))
                normalized[str(source)][str(target)] = sequence
        return {
            "schema_version": 1,
            "selectable_phases": list(selectable),
            "transition_phases": list(transitions),
            "compound_phases": list(compound),
            "transitions": normalized,
            "phase_roles": phase_roles,
            "phase_semantics": phase_semantics,
            "errors": sorted(set(errors)),
        }

    def phase_role(self, inter_id, phase_index):
        """Return the explicit service/clearance role for one lightphase."""
        contract = self.phase_contract(inter_id)
        if contract["errors"]:
            raise ValueError("; ".join(contract["errors"]))
        return contract["phase_roles"][phase_index]

    def phase_service_movement_pairs(self, inter_id, phase_index):
        """Lane pairs served according to the hash-bound phase semantics."""
        contract = self.phase_contract(inter_id)
        if contract["errors"]:
            raise ValueError("; ".join(contract["errors"]))
        semantic = contract["phase_semantics"][phase_index]
        pairs = []
        for movement in semantic["movements"]:
            for start_lane, end_lane in movement["lane_links"]:
                pair = ("{}_{}".format(movement["start_road"], start_lane),
                        "{}_{}".format(movement["end_road"], end_lane))
                if pair not in pairs:
                    pairs.append(pair)
        return pairs

    def transition_sequence(self, inter_id, from_phase, to_phase):
        contract = self.phase_contract(inter_id)
        if contract["errors"]:
            raise ValueError("; ".join(contract["errors"]))
        if from_phase not in contract["selectable_phases"] \
                or to_phase not in contract["selectable_phases"]:
            raise ValueError("transition endpoints must be selectable greens")
        if from_phase == to_phase:
            return []
        if "transitions" in contract:
            return list(contract["transitions"][str(from_phase)][str(to_phase)])
        return list(contract["transitions_after"][str(from_phase)])

    def phase_contract_audit(self):
        """Return a stable, serializable summary for foundation verification."""
        contracts = {inter_id: self.phase_contract(inter_id)
                     for inter_id in self.signalized_ids()}
        return {
            "schema_version": 1,
            "signal_count": len(contracts),
            "selectable_phases": {
                inter_id: contract["selectable_phases"]
                for inter_id, contract in contracts.items()},
            "transition_phases": {
                inter_id: contract["transition_phases"]
                for inter_id, contract in contracts.items()},
            "transitions": {
                inter_id: contract["transitions"]
                for inter_id, contract in contracts.items()},
            "phase_roles": {
                inter_id: contract["phase_roles"]
                for inter_id, contract in contracts.items()},
            "errors": {inter_id: contract["errors"]
                       for inter_id, contract in contracts.items()
                       if contract["errors"]},
        }

    def entry_roads(self) -> List[str]:
        """Roads starting at a virtual (boundary) intersection — flow spawn points."""
        virtual = {i["id"] for i in self.intersections if i.get("virtual")}
        return [r["id"] for r in self.roads if r["startIntersection"] in virtual]

    @staticmethod
    def _distribution(values):
        """Stable nearest-rank summary for manifest graph provenance."""
        ordered = sorted(values)
        if not ordered:
            return {key: None for key in ("min", "p50", "p75", "p90", "p95", "max")}

        def percentile(fraction):
            index = max(0, int(math.ceil(fraction * len(ordered))) - 1)
            return ordered[index]

        return {
            "min": ordered[0],
            "p50": percentile(0.50),
            "p75": percentile(0.75),
            "p90": percentile(0.90),
            "p95": percentile(0.95),
            "max": ordered[-1],
        }

    def _road_length(self, road_id):
        points = self._road_by_id[road_id].get("points", [])
        return sum(
            math.hypot(float(target["x"]) - float(source["x"]),
                       float(target["y"]) - float(source["y"]))
            for source, target in zip(points, points[1:])
        )

    def _nearest_controlled_corridor(self, source, outgoing_road,
                                     controlled, virtual, permitted_next):
        """Shortest valid corridor from one signal outlet to the next signal."""
        distance = self._road_length(outgoing_road)
        initial = (distance, 1, (outgoing_road,))
        pending = [initial]
        best = {outgoing_road: initial}
        selected = None
        while pending:
            candidate = heapq.heappop(pending)
            corridor_distance, road_hops, road_path = candidate
            road_id = road_path[-1]
            if candidate != best.get(road_id):
                continue
            if selected is not None and corridor_distance > selected[0]:
                break
            boundary = self._road_by_id[road_id]["endIntersection"]
            if boundary in controlled:
                # A loop back to the source still reaches a controlled boundary;
                # it is not allowed to pass through and search beyond it.
                if boundary != source:
                    resolved = (corridor_distance, road_hops, road_path, boundary)
                    if selected is None or resolved < selected:
                        selected = resolved
                continue
            if boundary in virtual:
                continue
            for next_road in permitted_next.get(road_id, []):
                if next_road in road_path:
                    continue
                next_candidate = (
                    corridor_distance + self._road_length(next_road),
                    road_hops + 1,
                    road_path + (next_road,),
                )
                if next_candidate < best.get(
                        next_road, (float("inf"), float("inf"), ())):
                    best[next_road] = next_candidate
                    heapq.heappush(pending, next_candidate)
        if selected is None:
            return None
        corridor_distance, road_hops, road_path, target = selected
        return {
            "source": source,
            "target": target,
            "outgoing_road": outgoing_road,
            "road_path": list(road_path),
            "intermediate_intersections": [
                self._road_by_id[road_id]["endIntersection"]
                for road_id in road_path[:-1]
            ],
            "road_hops": road_hops,
            "distance_coordinate_units": round(corridor_distance, 6),
        }

    def signal_adjacency(self):
        """Directed nearest-signal graph following permitted vehicle movements.

        Each permitted outgoing road at a controlled signal contributes at most
        one shortest corridor. Traversal may cross non-signalized junctions, but
        stops at the first controlled signal or virtual boundary. This avoids an
        arbitrary road-hop cutoff (OSM segmentation is non-uniform) and excludes
        longer alternative detours from the policy's one-hop receptive field.
        """
        if self._signal_adjacency_data is not None:
            return self._signal_adjacency_data
        controlled_ids = sorted(self.signalized_ids())
        controlled = set(controlled_ids)
        virtual = {item["id"] for item in self.intersections if item.get("virtual")}
        permitted_next = {road_id: [] for road_id in self._road_by_id}
        for intersection in self.intersections:
            for road_link in intersection.get("roadLinks", []):
                start = road_link.get("startRoad")
                end = road_link.get("endRoad")
                if (start in self._road_by_id and end in self._road_by_id
                        and road_link.get("laneLinks")
                        and end not in permitted_next[start]):
                    permitted_next[start].append(end)
        for road_id in permitted_next:
            permitted_next[road_id].sort()

        corridors = []
        for source in controlled_ids:
            outgoing = sorted({
                road_link.get("endRoad")
                for road_link in self._by_id[source].get("roadLinks", [])
                if road_link.get("laneLinks")
                and road_link.get("endRoad") in self._road_by_id
                and self._road_by_id[road_link["endRoad"]].get(
                    "startIntersection") == source
            })
            for outgoing_road in outgoing:
                corridor = self._nearest_controlled_corridor(
                    source, outgoing_road, controlled, virtual, permitted_next)
                if corridor is not None:
                    corridors.append(corridor)
        corridors.sort(key=lambda item: (
            item["source"], item["target"], item["distance_coordinate_units"],
            item["road_hops"], item["outgoing_road"], item["road_path"]))

        # Multiple physical outlet roads can reach the same next signal. The
        # policy graph keeps one directed edge and records every outlet corridor.
        edge_by_pair = {}
        for corridor in corridors:
            pair = (corridor["source"], corridor["target"])
            rank = (corridor["distance_coordinate_units"],
                    corridor["road_hops"], corridor["outgoing_road"],
                    corridor["road_path"])
            current = edge_by_pair.get(pair)
            if current is None or rank < current[0]:
                edge_by_pair[pair] = (rank, corridor)
        edges = [dict(edge_by_pair[pair][1]) for pair in sorted(edge_by_pair)]
        directed_edges = [[item["source"], item["target"]] for item in edges]
        upstream = {node_id: [] for node_id in controlled_ids}
        downstream = {node_id: [] for node_id in controlled_ids}
        for source, target in directed_edges:
            downstream[source].append(target)
            upstream[target].append(source)
        for mapping in (upstream, downstream):
            for node_id in mapping:
                mapping[node_id].sort()
        covered = {node_id for node_id in controlled_ids
                   if upstream[node_id] or downstream[node_id]}

        # Weak components describe coverage without erasing edge direction.
        undirected = {node_id: set() for node_id in controlled_ids}
        for source, target in directed_edges:
            undirected[source].add(target)
            undirected[target].add(source)
        remaining = set(controlled_ids)
        components = 0
        while remaining:
            components += 1
            pending = [min(remaining)]
            remaining.remove(pending[0])
            while pending:
                node_id = pending.pop()
                unseen = undirected[node_id] & remaining
                remaining.difference_update(unseen)
                pending.extend(sorted(unseen, reverse=True))

        self._signal_adjacency_data = {
            "schema_version": 1,
            "policy": {
                "directed": True,
                "selection": (
                    "shortest_permitted_path_to_first_controlled_signal_"
                    "per_outgoing_road"),
                "traversal": "roadLinks_with_nonempty_laneLinks",
                "stop_boundaries": ["controlled_signal", "virtual_intersection"],
                "distance_metric": "sum_road_polyline_euclidean_coordinate_units",
                "maximum_distance_coordinate_units": None,
                "maximum_road_hops": None,
                "cycle_policy": "simple_road_paths_only",
                "tie_break": "distance_then_hops_then_road_ids_then_target_id",
                "rationale": (
                    "Select one nearest reachable controlled signal per physical "
                    "outlet; do not enumerate longer detours. No fixed hop cutoff "
                    "is used because OSM road segmentation is non-uniform."),
            },
            "directed_edges": directed_edges,
            "edges": edges,
            "corridors": corridors,
            "upstream": upstream,
            "downstream": downstream,
            "stats": {
                "controlled_signals": len(controlled_ids),
                "covered_signals": len(covered),
                "isolated_signals": len(controlled_ids) - len(covered),
                "directed_edges": len(edges),
                "outgoing_corridors": len(corridors),
                "weak_components": components,
                "distance_coordinate_units": self._distribution([
                    item["distance_coordinate_units"] for item in edges]),
                "road_hops": self._distribution([
                    item["road_hops"] for item in edges]),
            },
        }
        return self._signal_adjacency_data

    def upstream_neighbors(self, inter_id: str) -> List[str]:
        """Signalized intersections that feed traffic INTO inter_id.

        A road incoming to inter_id (endIntersection == inter_id) starts at some
        upstream intersection; if that upstream node is itself signalized it is an
        upstream neighbour. Used by the neighbour-coordinated ("CoLight-lite") state
        so an agent can anticipate approaching demand — the signal Max-Pressure lacks.
        """
        return list(self.signal_adjacency()["upstream"][inter_id])

    def downstream_neighbors(self, inter_id: str) -> List[str]:
        """Signalized intersections reached directly from ``inter_id``."""
        return list(self.signal_adjacency()["downstream"][inter_id])
