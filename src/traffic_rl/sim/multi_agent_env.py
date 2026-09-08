"""Multi-agent traffic-signal env over a duck-typed engine.

Actions are selectable GREEN-phase choices (0..G_i-1). The env maps each to
the real lightphase index, enforces min-green, and executes the roadnet's
declared transition phases for their declared durations. Reward is signed
max-pressure.

3.6-safe: no `from __future__ import annotations`.
"""
import math

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.intersection import (
    IntersectionState, apply_switch_penalty, make_reward)


class MultiAgentTrafficEnv:
    def __init__(self, roadnet, engine, action_interval=10, max_steps=3600,
                 yellow_time=3, min_green=10, count_norm=10.0,
                 reward_type="pressure", state_mode="basic",
                 sim_step_seconds=1.0, maximum_red=180,
                 switch_penalty=0.05, encoder=None, queue_weight=1.0,
                 downstream_block_weight=0.0):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.yellow_time = yellow_time
        self.min_green = min_green
        self.maximum_red = maximum_red
        self.switch_penalty = float(switch_penalty)
        self.queue_weight = float(queue_weight)
        self.downstream_block_weight = float(downstream_block_weight)
        self.reward_type = reward_type
        self.state_mode = state_mode
        self.sim_step_seconds = float(sim_step_seconds)
        self._reward_fn = make_reward(reward_type)
        self.agent_ids = roadnet.signalized_ids()
        self.encoder = (encoder if encoder is not None else
                        ObservationEncoder(roadnet, count_norm=count_norm,
                                           state_mode=state_mode))
        self._green_phases = {a: roadnet.green_phases(a) for a in self.agent_ids}
        self._phase_contracts = {a: roadnet.phase_contract(a) for a in self.agent_ids}
        self._phase_roles = {
            a: self._phase_contracts[a]["phase_roles"] for a in self.agent_ids}
        contract_errors = []
        for contract in self._phase_contracts.values():
            contract_errors.extend(contract["errors"])
        if contract_errors:
            raise ValueError("invalid phase-role contract: %s" %
                             "; ".join(contract_errors))
        self._transition_paths = {}
        for a in self.agent_ids:
            for source_index, source_phase in enumerate(self._green_phases[a]):
                for target_index, target_phase in enumerate(self._green_phases[a]):
                    self._transition_paths[(a, source_index, target_index)] = (
                        roadnet.transition_sequence(a, source_phase, target_phase))
        self.states = {
            a: IntersectionState(a, roadnet.incoming_lanes(a),
                                 roadnet.outgoing_lanes(a),
                                 num_phases=len(self._green_phases[a]))
            for a in self.agent_ids
        }
        self.num_actions = {a: len(self._green_phases[a]) for a in self.agent_ids}
        self._maximum_red_trigger = {}
        for a in self.agent_ids:
            transition_total = sum(
                sum(duration for _, duration in
                    self._transition_paths[(a, source, (source + 1) % self.num_actions[a])])
                for source in range(self.num_actions[a])) * self.sim_step_seconds
            required_red = ((self.num_actions[a] - 1) * float(self.min_green)
                            + transition_total)
            decision = float(self.action_interval) * self.sim_step_seconds
            green = float(self.min_green)
            cycle_service_budget = sum(
                math.ceil((sum(duration for _, duration in
                    self._transition_paths[(a, source, (
                        source + 1) % self.num_actions[a])])
                    * self.sim_step_seconds + green) / decision) * decision
                for source in range(self.num_actions[a]))
            safe_required_red = cycle_service_budget
            if self.maximum_red is not None \
                    and float(self.maximum_red) < max(required_red,
                                                      safe_required_red):
                raise ValueError(
                    "maximum_red is infeasible for {}: {} < {}".format(
                        a, self.maximum_red,
                        max(required_red, safe_required_red)))
            if self.maximum_red is not None:
                self._maximum_red_trigger[a] = max(
                    0.0, float(self.maximum_red)
                    - cycle_service_budget - decision)
        self.obs_dim = getattr(self.encoder, "obs_dim", 12)
        self._green = {a: 0 for a in self.agent_ids}       # current green INDEX
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._elapsed_green = {a: 0.0 for a in self.agent_ids}
        self._time_since_service = {
            a: [0.0] * len(self._green_phases[a]) for a in self.agent_ids}
        self._phase_movements = {
            a: [set(roadnet.phase_movement_pairs(a, phase))
                for phase in self._green_phases[a]]
            for a in self.agent_ids}
        self._service_pairs_by_phase = {
            a: {phase_index: set(roadnet.phase_service_movement_pairs(
                    a, phase_index))
                for phase_index, role in self._phase_roles[a].items()
                if role in ("selectable_green", "compound_service")}
            for a in self.agent_ids}
        self._service_movements = {
            a: {movement for movements in self._service_pairs_by_phase[a].values()
                for movement in movements}
            for a in self.agent_ids}
        self._movement_time_since_service = {
            a: {movement: 0.0 for movement in self._service_movements[a]}
            for a in self.agent_ids}
        self._active_lightphase = {
            a: self._green_phases[a][0] for a in self.agent_ids}
        self._pending_transitions = {a: None for a in self.agent_ids}
        self._phase_switches = 0
        self._intergreen_vehicle_seconds = 0.0
        self._has_reset = False
        self._seen_vehicle_ids = None
        self._active_vehicle_ids = None
        self._t = 0
        self._queue_integral_vehicle_seconds = 0.0
        self._episode_max_red_seconds = 0.0

    # --- introspection used by controllers/runner ---
    def action_masks(self):
        masks = {}
        for a in self.agent_ids:
            mask = self._base_action_mask(a)
            if not self._has_reset:
                masks[a] = mask
                continue
            if self._pending_transitions[a] is not None:
                mask[:] = False
                mask[self._green[a]] = True
            elif self._elapsed_green[a] < float(self.min_green):
                mask[:] = False
                mask[self._green[a]] = True
            else:
                movement_due = (self.maximum_red is not None
                                and any(elapsed >= self._maximum_red_trigger[a]
                                        for elapsed in
                                        self._movement_time_since_service[a].values()))
                overdue = []
                if self.maximum_red is not None:
                    overdue = [idx for idx, elapsed in
                               enumerate(self._time_since_service[a])
                               if idx != self._green[a]
                               and elapsed >= self._maximum_red_trigger[a]]
                if movement_due:
                    forced = (self._green[a] + 1) % self.num_actions[a]
                    mask[:] = False
                    mask[forced] = True
                elif overdue:
                    forced = max(overdue,
                                 key=lambda idx: self._time_since_service[a][idx])
                    mask[:] = False
                    mask[forced] = True
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
        self._movement_time_since_service = {
            a: {movement: 0.0 for movement in self._service_movements[a]}
            for a in self.agent_ids}
        self._active_lightphase = {
            a: self._green_phases[a][0] for a in self.agent_ids}
        self._pending_transitions = {a: None for a in self.agent_ids}
        self._phase_switches = 0
        self._intergreen_vehicle_seconds = 0.0
        self._has_reset = True
        if hasattr(self.engine, "vehicle_ids"):
            self._active_vehicle_ids = set(self.engine.vehicle_ids())
            self._seen_vehicle_ids = set(self._active_vehicle_ids)
        else:
            self._active_vehicle_ids = None
            self._seen_vehicle_ids = None
        self._t = 0
        self._queue_integral_vehicle_seconds = 0.0
        self._episode_max_red_seconds = 0.0
        for a in self.agent_ids:
            self._set_phase(a, self._green_phases[a][0])
        return self._observations()

    def _set_phase(self, inter_id, phase_index):
        self.engine.set_tl_phase(inter_id, phase_index)
        self._active_lightphase[inter_id] = phase_index

    def _refresh_phase_service_timers(self, inter_id):
        movement_timers = self._movement_time_since_service[inter_id]
        self._time_since_service[inter_id] = [
            max([movement_timers[movement] for movement in movements] or [0.0])
            for movements in self._phase_movements[inter_id]]

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

    def _engine_steps(self, n, clearing=None, transitioning=None):
        clearing = set(clearing or [])
        transitioning = set(transitioning or [])
        for _ in range(n):
            self.engine.step()
            self._t += 1
            if self._seen_vehicle_ids is not None:
                self._active_vehicle_ids = set(self.engine.vehicle_ids())
                self._seen_vehicle_ids.update(self._active_vehicle_ids)
            elapsed = self.sim_step_seconds
            for a in self.agent_ids:
                movement_timers = self._movement_time_since_service[a]
                for movement in movement_timers:
                    movement_timers[movement] += elapsed
                phase_index = self._active_lightphase[a]
                role = self._phase_roles[a][phase_index]
                if role in ("selectable_green", "compound_service"):
                    for movement in self._service_pairs_by_phase[a][phase_index]:
                        if movement in movement_timers:
                            movement_timers[movement] = 0.0
                if a in clearing:
                    self._intergreen_vehicle_seconds += elapsed
                if a not in transitioning:
                    self._elapsed_green[a] += elapsed
                self._refresh_phase_service_timers(a)
            self._episode_max_red_seconds = max(
                self._episode_max_red_seconds,
                max([max(values.values()) for values in
                     self._movement_time_since_service.values()
                     if values] or [0.0]))
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
        valid_masks = self.action_masks()
        for a, choice in actions.items():
            choice = int(choice)
            mask = valid_masks[a]
            if 0 <= choice < self.num_actions[a] and mask[choice] \
                    and choice != self._green[a]:
                switching[a] = choice

        # Start accepted transitions. A sequence may span multiple policy
        # intervals; while pending, its signal exposes only the source action
        # and ignores new requests until every declared transition completes.
        for a, choice in switching.items():
            path = self._transition_paths[(a, self._green[a], choice)]
            self._pending_transitions[a] = {
                "target": choice,
                "sequence": [[phase, duration] for phase, duration in path],
                "index": 0,
                "remaining": path[0][1],
                "phase_set": False,
            }
            self._elapsed_green[a] = 0.0

        self._phase_switches += len(switching)
        steps = min(int(self.action_interval), max(0, self.max_steps - self._t))
        for _ in range(steps):
            clearing = set()
            transitioning = set()
            for a in self.agent_ids:
                pending = self._pending_transitions[a]
                if pending is None:
                    continue
                transitioning.add(a)
                if not pending["phase_set"]:
                    phase_index = pending["sequence"][pending["index"]][0]
                    self._set_phase(a, phase_index)
                    pending["phase_set"] = True
                role = self._phase_roles[a][self._active_lightphase[a]]
                if role in ("clearance_yellow", "all_red"):
                    clearing.add(a)
            self._engine_steps(1, clearing=clearing,
                               transitioning=transitioning)
            for a in list(transitioning):
                pending = self._pending_transitions[a]
                pending["remaining"] -= 1
                if pending["remaining"] > 0:
                    continue
                pending["index"] += 1
                if pending["index"] < len(pending["sequence"]):
                    pending["remaining"] = pending["sequence"][
                        pending["index"]][1]
                    pending["phase_set"] = False
                    continue
                choice = pending["target"]
                self._green[a] = choice
                self._since_switch[a] = 0
                self._set_phase(a, self._green_phases[a][choice])
                self._pending_transitions[a] = None

        waiting = self.engine.lane_waiting_counts()
        rewards = {}
        for a in self.agent_ids:
            outgoing = self.states[a].outgoing_lanes
            downstream_queue = (float(sum(waiting.get(lane, 0.0)
                                          for lane in outgoing)) / len(outgoing)
                                if outgoing else 0.0)
            objective = (self.queue_weight * self._reward_fn(self.states[a], waiting)
                         - self.downstream_block_weight * downstream_queue)
            rewards[a] = apply_switch_penalty(
                objective, a in switching, self.switch_penalty)
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
        active_vehicles = self.engine.vehicle_count()
        arrived = None
        if self._seen_vehicle_ids is not None:
            active_vehicles = len(self._active_vehicle_ids)
            arrived = len(self._seen_vehicle_ids - self._active_vehicle_ids)
        elif hasattr(self.engine, "finished_vehicle_count"):
            arrived = self.engine.finished_vehicle_count()
        completion_rate = None
        if arrived is not None and active_vehicles + arrived > 0:
            completion_rate = float(arrived) / (active_vehicles + arrived)
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": active_vehicles,
            "active_vehicles": active_vehicles,
            "arrived": arrived,
            "completion_rate": completion_rate,
            "total_queue": float(sum(true_waiting.values())),
            "queue_integral_vehicle_seconds": self._queue_integral_vehicle_seconds,
            "step": self._t,
            "phase_switches": self._phase_switches,
            "intergreen_vehicle_seconds": self._intergreen_vehicle_seconds,
            "current_max_red_seconds": max(
                [max(values.values()) for values in
                 self._movement_time_since_service.values() if values] or [0.0]),
            "max_red_seconds": self._episode_max_red_seconds,
            "maximum_red_trigger_seconds": dict(self._maximum_red_trigger),
            "per_agent_queue": per_agent_queue,
        }
        return self._observations(), rewards, done, info
