"""Multi-agent traffic-signal env over a duck-typed engine.

Actions are GREEN-phase choices (0..G_i-1). The env maps each to the real
lightphase index, enforces min-green, and inserts the all-red phase for
yellow_time engine-steps on a switch. Reward is signed max-pressure.

3.6-safe: no `from __future__ import annotations`.
"""
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.intersection import (
    IntersectionState, apply_switch_penalty, make_reward)


class MultiAgentTrafficEnv:
    def __init__(self, roadnet, engine, action_interval=10, max_steps=3600,
                 yellow_time=3, min_green=10, count_norm=10.0,
                 reward_type="pressure", state_mode="basic",
                 sim_step_seconds=1.0, maximum_red=180,
                 switch_penalty=0.05, encoder=None):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.yellow_time = yellow_time
        self.min_green = min_green
        self.maximum_red = maximum_red
        self.switch_penalty = float(switch_penalty)
        self.reward_type = reward_type
        self.state_mode = state_mode
        self.sim_step_seconds = float(sim_step_seconds)
        self._reward_fn = make_reward(reward_type)
        self.agent_ids = roadnet.signalized_ids()
        self.encoder = (encoder if encoder is not None else
                        ObservationEncoder(roadnet, count_norm=count_norm,
                                           state_mode=state_mode))
        self._green_phases = {a: roadnet.green_phases(a) for a in self.agent_ids}
        self._all_red = {a: roadnet.all_red_phase(a) for a in self.agent_ids}
        self.states = {
            a: IntersectionState(a, roadnet.incoming_lanes(a),
                                 roadnet.outgoing_lanes(a),
                                 num_phases=len(self._green_phases[a]))
            for a in self.agent_ids
        }
        self.num_actions = {a: len(self._green_phases[a]) for a in self.agent_ids}
        self.obs_dim = getattr(self.encoder, "obs_dim", 12)
        self._green = {a: 0 for a in self.agent_ids}       # current green INDEX
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._elapsed_green = {a: 0.0 for a in self.agent_ids}
        self._time_since_service = {
            a: [0.0] * len(self._green_phases[a]) for a in self.agent_ids}
        self._phase_switches = 0
        self._intergreen_vehicle_seconds = 0.0
        self._has_reset = False
        self._t = 0
        self._queue_integral_vehicle_seconds = 0.0

    # --- introspection used by controllers/runner ---
    def action_masks(self):
        masks = {}
        for a in self.agent_ids:
            mask = self._base_action_mask(a)
            if not self._has_reset:
                masks[a] = mask
                continue
            overdue = []
            if self.maximum_red is not None:
                overdue = [idx for idx, elapsed in
                           enumerate(self._time_since_service[a])
                           if elapsed >= float(self.maximum_red)]
            if overdue:
                forced = max(overdue,
                             key=lambda idx: self._time_since_service[a][idx])
                mask[:] = False
                mask[forced] = True
            elif self._elapsed_green[a] < float(self.min_green):
                mask[:] = False
                mask[self._green[a]] = True
            masks[a] = mask
        return masks

    def _base_action_mask(self, inter_id):
        if hasattr(self.encoder, "action_mask"):
            return self.encoder.action_mask(inter_id).copy()
        import numpy as np
        mask = np.zeros(self.encoder.max_green, dtype=np.bool_)
        mask[:self.num_actions[inter_id]] = True
        return mask

    def current_waiting_counts(self):
        return self.engine.lane_waiting_counts()

    # --- lifecycle ---
    def reset(self):
        self.engine.reset()
        self._green = {a: 0 for a in self.agent_ids}
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._elapsed_green = {a: 0.0 for a in self.agent_ids}
        self._time_since_service = {
            a: [0.0] * len(self._green_phases[a]) for a in self.agent_ids}
        self._phase_switches = 0
        self._intergreen_vehicle_seconds = 0.0
        self._has_reset = True
        self._t = 0
        self._queue_integral_vehicle_seconds = 0.0
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][0])
        return self._observations()

    def _observations(self):
        counts = self.engine.lane_vehicle_counts()
        waiting = self.engine.lane_waiting_counts()
        if hasattr(self.encoder, "encode_all"):
            return {a: self.encoder.encode_all(
                a, counts, waiting, self._green[a], self._elapsed_green[a],
                self._time_since_service[a])[0] for a in self.agent_ids}
        # ats state needs queued counts too (running = all - queued).
        waiting = waiting if self.state_mode == "ats" else None
        return {a: self.encoder.encode(a, counts, self._green[a], waiting)
                for a in self.agent_ids}

    def _engine_steps(self, n, clearing=None):
        clearing = set(clearing or [])
        for _ in range(n):
            self.engine.step()
            self._t += 1
            elapsed = self.sim_step_seconds
            for a in self.agent_ids:
                timers = self._time_since_service[a]
                for phase_idx in range(len(timers)):
                    timers[phase_idx] += elapsed
                if a in clearing:
                    self._intergreen_vehicle_seconds += elapsed
                else:
                    self._elapsed_green[a] += elapsed
                    timers[self._green[a]] = 0.0
            waiting = (self.engine.true_lane_waiting_counts()
                       if hasattr(self.engine, "true_lane_waiting_counts")
                       else self.engine.lane_waiting_counts())
            self._queue_integral_vehicle_seconds += (
                float(sum(waiting.values())) * self.sim_step_seconds)
        for a in self.agent_ids:
            self._since_switch[a] += n * self.sim_step_seconds

    def step(self, actions):
        # decide switches (respecting min-green + validity)
        switching = {}
        for a, choice in actions.items():
            choice = int(choice)
            mask = self.action_masks()[a]
            if 0 <= choice < self.num_actions[a] and mask[choice] \
                    and choice != self._green[a]:
                switching[a] = choice

        # yellow / all-red transition for switching agents
        if switching and self.yellow_time > 0:
            for a in switching:
                ar = self._all_red[a]
                if ar is not None:
                    self.engine.set_tl_phase(a, ar)
                self._elapsed_green[a] = 0.0
            self._engine_steps(self.yellow_time, clearing=switching)
            green_steps = self.action_interval - self.yellow_time
        else:
            green_steps = self.action_interval

        # commit new greens
        for a, choice in switching.items():
            self._green[a] = choice
            self._since_switch[a] = 0
        self._phase_switches += len(switching)
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][self._green[a]])

        if green_steps > 0:
            self._engine_steps(green_steps)

        waiting = self.engine.lane_waiting_counts()
        rewards = {a: apply_switch_penalty(
            self._reward_fn(self.states[a], waiting), a in switching,
            self.switch_penalty) for a in self.agent_ids}
        done = self._t >= self.max_steps
        # Metric uses GROUND-TRUTH queue (== waiting for a real engine; unperturbed under
        # PerturbedEngine) so sensor-noise robustness measures true performance, not the
        # noisy sensor. Reward/observation stay on the perturbed path above.
        true_waiting = (self.engine.true_lane_waiting_counts()
                        if hasattr(self.engine, "true_lane_waiting_counts") else waiting)
        per_agent_queue = {
            a: float(sum(true_waiting.get(lane, 0.0)
                         for lane in self.states[a].incoming_lanes))
            for a in self.agent_ids}
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": self.engine.vehicle_count(),
            "total_queue": float(sum(true_waiting.values())),
            "queue_integral_vehicle_seconds": self._queue_integral_vehicle_seconds,
            "step": self._t,
            "phase_switches": self._phase_switches,
            "intergreen_vehicle_seconds": self._intergreen_vehicle_seconds,
            "max_red_seconds": max(
                [max(values) for values in self._time_since_service.values()] or [0.0]),
            "per_agent_queue": per_agent_queue,
        }
        return self._observations(), rewards, done, info
