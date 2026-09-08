"""Parse a CityFlow roadnet.json into convenient lookups for env + flow generation.

NOTE: must stay importable under Python 3.6 (the CityFlow Docker image), so no
`from __future__ import annotations`. The `dataclasses` backport is pip-installed
in the container (see Makefile cf-test / the run_fixed_time invocation).
"""
import json
import hashlib
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

    def phase_contract(self, inter_id: str, transition_max_seconds=6.0):
        """Classify selectable greens and the transition after each green.

        Converter-generated yellow phases may retain a short subset (or duplicate)
        of the preceding/next green's movements. Empty phases are transitions too.
        A non-empty short phase is classified as a transition only when its
        movements are a subset of an adjacent long green, so a short but distinct
        traffic movement is never silently re-labelled.
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
        return {
            "schema_version": 1,
            "selectable_phases": selectable,
            "transition_phases": sorted(transition_phases),
            "transitions_after": transitions_after,
            "transitions": directed,
            "phase_roles": phase_roles,
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
        for phase_index in transitions:
            if 0 <= phase_index < phase_count \
                    and isinstance(min_green, (int, float)) \
                    and self.phase_movement_pairs(inter_id, phase_index) \
                    and float(self._lightphases(inter_id)[phase_index].get(
                        "time", 0)) >= float(min_green):
                errors.append(
                    "intersection {} transition phase {} is selectable by rule".format(
                        inter_id, phase_index))
        allowed_roles = set(("selectable_green", "compound_service",
                             "clearance_yellow", "all_red"))
        semantics = record.get("phase_semantics", [])
        phase_roles = {}
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
            duration = semantic.get("duration_seconds")
            if duration != self._lightphases(inter_id)[phase_index].get("time"):
                errors.append("intersection {} phase {} duration mismatch".format(
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
            "errors": sorted(set(errors)),
        }

    def phase_role(self, inter_id, phase_index):
        """Return the explicit service/clearance role for one lightphase."""
        contract = self.phase_contract(inter_id)
        if contract["errors"]:
            raise ValueError("; ".join(contract["errors"]))
        return contract["phase_roles"][phase_index]

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

    def upstream_neighbors(self, inter_id: str) -> List[str]:
        """Signalized intersections that feed traffic INTO inter_id.

        A road incoming to inter_id (endIntersection == inter_id) starts at some
        upstream intersection; if that upstream node is itself signalized it is an
        upstream neighbour. Used by the neighbour-coordinated ("CoLight-lite") state
        so an agent can anticipate approaching demand — the signal Max-Pressure lacks.
        """
        sig = set(self.signalized_ids())
        out: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            road = self._road_by_id[road_id]
            if road["endIntersection"] == inter_id:
                up = road["startIntersection"]
                if up != inter_id and up in sig and up not in out:
                    out.append(up)
        return out

    def downstream_neighbors(self, inter_id: str) -> List[str]:
        """Signalized intersections reached directly from ``inter_id``."""
        sig = set(self.signalized_ids())
        out: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            road = self._road_by_id[road_id]
            if road["startIntersection"] == inter_id:
                downstream = road["endIntersection"]
                if downstream != inter_id and downstream in sig and downstream not in out:
                    out.append(downstream)
        return out
