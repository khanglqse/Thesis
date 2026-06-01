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
        """Lightphase indices that actually let traffic move (non-empty availableRoadLinks)."""
        return [idx for idx, ph in enumerate(self._lightphases(inter_id))
                if ph.get("availableRoadLinks")]

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

    def entry_roads(self) -> List[str]:
        """Roads starting at a virtual (boundary) intersection — flow spawn points."""
        virtual = {i["id"] for i in self.intersections if i.get("virtual")}
        return [r["id"] for r in self.roads if r["startIntersection"] in virtual]
