"""Multi-agent traffic-signal environment over a duck-typed engine.

`engine` must provide: reset(), step(), set_tl_phase(id, phase),
lane_vehicle_counts(), lane_waiting_counts(), vehicle_count(),
average_travel_time(). The real one is CityFlowEngine; tests use a fake.

Must stay importable under Python 3.6 (CityFlow Docker image): no
`from __future__ import annotations`.
"""
from typing import Dict, List, Tuple

import numpy as np

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.intersection import IntersectionState, pressure_reward


class MultiAgentTrafficEnv:
    def __init__(self, roadnet, engine, action_interval=10, max_steps=3600):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.agent_ids = roadnet.signalized_ids()  # type: List[str]
        self.states = {
            aid: IntersectionState(
                inter_id=aid,
                incoming_lanes=roadnet.incoming_lanes(aid),
                outgoing_lanes=roadnet.outgoing_lanes(aid),
                num_phases=roadnet.num_phases(aid),
            )
            for aid in self.agent_ids
        }  # type: Dict[str, IntersectionState]
        self._phase = {aid: 0 for aid in self.agent_ids}  # type: Dict[str, int]
        self._t = 0

    def obs_dims(self):
        return {aid: s.obs_dim() for aid, s in self.states.items()}

    def reset(self):
        self.engine.reset()
        self._phase = {aid: 0 for aid in self.agent_ids}
        self._t = 0
        return self._observations()

    def _observations(self):
        counts = self.engine.lane_vehicle_counts()
        return {
            aid: self.states[aid].observation(counts, self._phase[aid])
            for aid in self.agent_ids
        }

    def step(self, actions):
        for aid, phase in actions.items():
            self._phase[aid] = phase
            self.engine.set_tl_phase(aid, phase)
        for _ in range(self.action_interval):
            self.engine.step()
            self._t += 1
        waiting = self.engine.lane_waiting_counts()
        rewards = {aid: pressure_reward(self.states[aid], waiting) for aid in self.agent_ids}
        done = self._t >= self.max_steps
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": self.engine.vehicle_count(),
            "step": self._t,
        }
        return self._observations(), rewards, done, info
