"""Executed fixed-time shadow and bounded, fully rejoining signal macros.

The shadow uses the production signal automaton with an empty traffic engine.
It receives no demand, traffic state, case identifier, or simulator seed. All
commands are compiled before acting and checked against the actual masks.
Python 3.6 compatible for the pinned CityFlow runtime.
"""
import copy

import numpy as np

from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv


def signal_state(env, node):
    """Complete future-relevant signal state, independent of traffic state."""
    return {
        "green": env._green[node],
        "active_lightphase": env._active_lightphase[node],
        "elapsed_green": env._elapsed_green[node],
        "since_switch": env._since_switch[node],
        "pending_transition": copy.deepcopy(env._pending_transitions[node]),
        "phase_service_timers": list(env._time_since_service[node]),
        "movement_service_timers": [
            [list(pair), elapsed] for pair, elapsed in
            sorted(env._movement_time_since_service[node].items())],
    }


class _NodeRoadnet(object):
    def __init__(self, roadnet, node):
        self.roadnet = roadnet
        self.node = node

    def signalized_ids(self):
        return [self.node]

    def __getattr__(self, name):
        return getattr(self.roadnet, name)


class EmptySignalEngine(object):
    """Traffic-free engine: its only state is the signal exposure timeline."""
    def reset(self):
        self.phases = {}

    def step(self):
        pass

    def set_tl_phase(self, node, phase):
        self.phases[node] = phase

    def lane_vehicle_counts(self):
        return {}

    def lane_waiting_counts(self):
        return {}

    def vehicle_count(self):
        return 0

    def average_travel_time(self):
        return 0.0


class _EmptyEncoder(object):
    def __init__(self, count):
        self.max_green = count

    def action_mask(self, node):
        return np.ones(self.max_green, dtype=np.bool_)

    def encode(self, *args):
        return np.zeros(1, dtype=np.float32)


def audit_timelines(reference, candidate):
    if len(reference) != len(candidate):
        raise ValueError("signal timelines must cover the same horizon")
    audit = {"observed_seconds": len(reference),
             "phase_definition": "lightphase_exposed_during_simulator_step",
             "service_definition": "movement_time_since_service_divergence"}
    keys = {
        "phase": (),
        "service": ("movement_service_timers",),
        "state": tuple(reference[0]["state"]) if reference else (),
    }
    for label, fields in keys.items():
        differing = []
        for ref, actual in zip(reference, candidate):
            if ref["second"] != actual["second"]:
                raise ValueError("signal timeline timestamps differ")
            mismatch = (ref["served_lightphase"] != actual["served_lightphase"]
                        if label == "phase" else
                        any(ref["state"][key] != actual["state"][key] for key in fields))
            if mismatch:
                differing.append(ref["second"])
        audit[label + "_divergence_seconds"] = len(differing)
        audit["last_" + label + "_divergence_second"] = (
            differing[-1] if differing else None)
    return audit


class ShadowSignal(object):
    def __init__(self, roadnet, node, action_interval=10, min_green=20,
                 maximum_red=180, green_duration=25):
        self.roadnet = roadnet
        self.node = node
        self.action_interval = int(action_interval)
        self.min_green = min_green
        self.maximum_red = maximum_red
        self.green_duration = green_duration
        self._references = {}

    def _env(self, horizon):
        count = len(self.roadnet.green_phases(self.node))
        return MultiAgentTrafficEnv(
            _NodeRoadnet(self.roadnet, self.node), EmptySignalEngine(),
            encoder=_EmptyEncoder(count), max_steps=horizon,
            action_interval=self.action_interval, min_green=self.min_green,
            maximum_red=self.maximum_red)

    def _controller(self, env):
        return FixedTimeController(env.num_actions, self.green_duration,
                                   self.action_interval)

    def reference(self, start, duration):
        key = (int(start), int(duration))
        if key in self._references:
            return self._references[key]
        if start < 0 or duration <= 0 or start % self.action_interval \
                or duration % self.action_interval:
            raise ValueError("shadow interval must align to decision ticks")
        env = self._env(start + duration)
        env.reset()
        controller = self._controller(env)
        commands, trace = [], []
        while env._t < start:
            env.step(controller.act({"action_masks": env.action_masks()}))
        initial = signal_state(env, self.node)
        # Keep a traffic-free automaton clone at the exact anchor. Never infer
        # its state from nominal cycle length: startup and service timers matter.
        anchor = copy.deepcopy(env, {id(env.roadnet): env.roadnet,
                                     id(env.encoder): env.encoder})
        env.signal_observer = lambda observed: trace.append({
            "second": observed._t, "state": signal_state(observed, self.node),
            "served_lightphase": observed._last_step_lightphases[self.node]})
        while env._t < start + duration:
            actions = controller.act({"action_masks": env.action_masks()})
            commands.append(actions[self.node])
            env.step(actions)
        result = {"initial_state": initial, "terminal_state": signal_state(env, self.node),
                  "commands": commands, "trace": trace, "anchor": anchor}
        self._references[key] = result
        return result

    def release_reference(self, start, duration):
        """Drop a completed cached trace after its terminal anchor was checked."""
        self._references.pop((int(start), int(duration)), None)

    def execute(self, reference, commands):
        anchor = reference["anchor"]
        env = copy.deepcopy(anchor, {id(anchor.roadnet): anchor.roadnet,
                                     id(anchor.encoder): anchor.encoder})
        trace = []
        env.signal_observer = lambda observed: trace.append({
            "second": observed._t, "state": signal_state(observed, self.node),
            "served_lightphase": observed._last_step_lightphases[self.node]})
        illegal = []
        for command in commands:
            if not env.action_masks()[self.node][command]:
                illegal.append(env._t)
            env.step({self.node: command})
        return {"trace": trace, "terminal_state": signal_state(env, self.node),
                "illegal_requests": len(illegal), "illegal_seconds": illegal}

    def nominal_with_override(self, duration, overrides):
        env = self._env(duration)
        env.reset()
        controller = self._controller(env)
        trace = []
        disagreements = 0
        env.signal_observer = lambda observed: trace.append({
            "second": observed._t, "state": signal_state(observed, self.node),
            "served_lightphase": observed._last_step_lightphases[self.node]})
        while env._t < duration:
            actions = controller.act({"action_masks": env.action_masks()})
            if env._t in overrides:
                disagreements += int(actions[self.node] != overrides[env._t])
                actions[self.node] = overrides[env._t]
            env.step(actions)
        return {"trace": trace, "explicit_overrides": len(overrides),
                "masked_reference_disagreements": disagreements}


def compile_block(shadow, start, duration=300, shift_seconds=10):
    if duration != 300 or shift_seconds != 10 or shadow.action_interval != 10:
        raise ValueError("residual contract requires 300s blocks and +/-10s shifts")
    ref = shadow.reference(start, duration)
    commands = ref["commands"]
    templates = [{"macro_id": 0, "boundary_second": None, "shift_seconds": 0,
                  "commands": list(commands), "illegal_requests": 0,
                  "terminal_state": ref["terminal_state"],
                  "audit": audit_timelines(ref["trace"], ref["trace"])}]
    rejected = []
    for index in range(1, len(commands)):
        if commands[index] == commands[index - 1]:
            continue
        for direction in (-1, 1):
            modified = list(commands)
            changed_index = index - 1 if direction < 0 else index
            modified[changed_index] = commands[index if direction < 0 else index - 1]
            run = shadow.execute(ref, modified)
            candidate = {"boundary_second": start + index * 10,
                         "shift_seconds": direction * shift_seconds}
            if run["illegal_requests"]:
                candidate["reason"] = "illegal_request"
                candidate["illegal_seconds"] = run["illegal_seconds"]
                rejected.append(candidate)
            elif run["terminal_state"] != ref["terminal_state"]:
                candidate["reason"] = "terminal_state_mismatch"
                rejected.append(candidate)
            else:
                candidate.update({"macro_id": len(templates), "commands": modified,
                                  "illegal_requests": 0,
                                  "terminal_state": run["terminal_state"],
                                  "audit": audit_timelines(ref["trace"], run["trace"])})
                # Changes to a request already held by minimum-green are not
                # residual interventions and must not satisfy activity gates.
                if candidate["audit"]["phase_divergence_seconds"] == 0:
                    candidate["reason"] = "no_executed_change"
                    rejected.append(candidate)
                else:
                    templates.append(candidate)
    return {"start_second": start, "duration_seconds": duration,
            "initial_state": ref["initial_state"],
            "terminal_state": ref["terminal_state"],
            "templates": templates, "rejected": rejected}
