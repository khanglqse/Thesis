"""Parse a CityFlow roadnet.json into convenient lookups for env + flow generation.

NOTE: must stay importable under Python 3.6 (the CityFlow Docker image), so no
`from __future__ import annotations`. The `dataclasses` backport is pip-installed
in the container (see Makefile cf-test / the run_fixed_time invocation).
"""
import json
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RoadNet:
    intersections: List[dict]
    roads: List[dict]
    _by_id: Dict[str, dict]
    _road_by_id: Dict[str, dict]
    _next: Dict[str, List[str]]

    @classmethod
    def load(cls, path: str) -> "RoadNet":
        with open(path) as f:
            data = json.load(f)
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
        return cls(data["intersections"], data["roads"], by_id, road_by_id, nxt)

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
        return {
            "schema_version": 1,
            "selectable_phases": selectable,
            "transition_phases": sorted(transition_phases),
            "transitions_after": transitions_after,
            "errors": sorted(set(errors)),
        }

    def transition_sequence(self, inter_id, from_phase, to_phase):
        contract = self.phase_contract(inter_id)
        if contract["errors"]:
            raise ValueError("; ".join(contract["errors"]))
        if from_phase not in contract["selectable_phases"] \
                or to_phase not in contract["selectable_phases"]:
            raise ValueError("transition endpoints must be selectable greens")
        if from_phase == to_phase:
            return []
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
            "transitions_after": {
                inter_id: contract["transitions_after"]
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
