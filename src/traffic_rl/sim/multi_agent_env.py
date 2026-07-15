"""Multi-agent traffic-signal env over a duck-typed engine.

Actions are GREEN-phase choices (0..G_i-1). The env maps each to the real
lightphase index, enforces min-green, and inserts the all-red phase for
yellow_time engine-steps on a switch. Reward is signed max-pressure.

3.6-safe: no `from __future__ import annotations`.
"""
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.intersection import IntersectionState, make_reward


class MultiAgentTrafficEnv:
    def __init__(self, roadnet, engine, action_interval=10, max_steps=3600,
                 yellow_time=3, min_green=10, count_norm=10.0,
                 reward_type="pressure", state_mode="basic"):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.yellow_time = yellow_time
        self.min_green = min_green
        self.reward_type = reward_type
        self.state_mode = state_mode
        self._reward_fn = make_reward(reward_type)
        self.agent_ids = roadnet.signalized_ids()
        self.encoder = ObservationEncoder(roadnet, count_norm=count_norm,
                                          state_mode=state_mode)
        self._green_phases = {a: roadnet.green_phases(a) for a in self.agent_ids}
        self._all_red = {a: roadnet.all_red_phase(a) for a in self.agent_ids}
        self.states = {
            a: IntersectionState(a, roadnet.incoming_lanes(a),
                                 roadnet.outgoing_lanes(a),
                                 num_phases=len(self._green_phases[a]))
            for a in self.agent_ids
        }
        self.num_actions = {a: len(self._green_phases[a]) for a in self.agent_ids}
        self.obs_dim = self.encoder.obs_dim
        self._green = {a: 0 for a in self.agent_ids}       # current green INDEX
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._t = 0

    # --- introspection used by controllers/runner ---
    def action_masks(self):
        return {a: self.encoder.action_mask(a) for a in self.agent_ids}

    def current_waiting_counts(self):
        return self.engine.lane_waiting_counts()

    # --- lifecycle ---
    def reset(self):
        self.engine.reset()
        self._green = {a: 0 for a in self.agent_ids}
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._t = 0
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][0])
        return self._observations()

    def _observations(self):
        counts = self.engine.lane_vehicle_counts()
        # ats state needs queued counts too (running = all - queued); fetch once.
        waiting = self.engine.lane_waiting_counts() if self.state_mode == "ats" else None
        return {a: self.encoder.encode(a, counts, self._green[a], waiting)
                for a in self.agent_ids}

    def _engine_steps(self, n):
        for _ in range(n):
            self.engine.step()
            self._t += 1
        for a in self.agent_ids:
            self._since_switch[a] += n

    def step(self, actions):
        # decide switches (respecting min-green + validity)
        switching = {}
        for a, choice in actions.items():
            choice = int(choice)
            if 0 <= choice < self.num_actions[a] and choice != self._green[a] \
                    and self._since_switch[a] >= self.min_green:
                switching[a] = choice

        # yellow / all-red transition for switching agents
        if switching and self.yellow_time > 0:
            for a in switching:
                ar = self._all_red[a]
                if ar is not None:
                    self.engine.set_tl_phase(a, ar)
            self._engine_steps(self.yellow_time)
            green_steps = self.action_interval - self.yellow_time
        else:
            green_steps = self.action_interval

        # commit new greens
        for a, choice in switching.items():
            self._green[a] = choice
            self._since_switch[a] = 0
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][self._green[a]])

        if green_steps > 0:
            self._engine_steps(green_steps)

        waiting = self.engine.lane_waiting_counts()
        rewards = {a: self._reward_fn(self.states[a], waiting) for a in self.agent_ids}
        done = self._t >= self.max_steps
        # Metric uses GROUND-TRUTH queue (== waiting for a real engine; unperturbed under
        # PerturbedEngine) so sensor-noise robustness measures true performance, not the
        # noisy sensor. Reward/observation stay on the perturbed path above.
        true_waiting = (self.engine.true_lane_waiting_counts()
                        if hasattr(self.engine, "true_lane_waiting_counts") else waiting)
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": self.engine.vehicle_count(),
            "total_queue": float(sum(true_waiting.values())),
            "step": self._t,
        }
        return self._observations(), rewards, done, info
