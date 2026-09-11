"""Schedule-anchored macro Double DQN and auditable execution controller."""
import math
import os

import numpy as np

from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.sim.phase_encoder import FEATURES
from traffic_rl.sim.schedule_residual import ShadowSignal, compile_block, signal_state


MACRO_FEATURES = (["source_" + key for key in FEATURES]
                  + ["target_" + key for key in FEATURES]
                  + ["boundary_fraction", "shift_fraction", "is_baseline"])
MAX_MACROS = 59
CRITIC_UNITS = {
    "vehicle_seconds_per_unit": 100000.0,
    "sign": "negative_cost",
    "raw_objective": "queue_integral_vehicle_seconds",
    "components": ["network_queue_integral_vehicle_seconds", "pending_integral_vehicle_seconds"],
    "excluded": ["future_unreleased_vehicles"],
}
POLICY_INPUT_SCHEMA = {
    "learned_features": MACRO_FEATURES,
    "operational_context": {"time_of_day": ["normal", "am_peak", "pm_peak"]},
    "runtime_signals": ["current_signal_state", "elapsed_seconds"],
    "excluded_features": ["case_id", "learning_seed", "demand_seed",
                          "simulator_seed", "filename", "future_flow"],
}


def select_macro(scores, mask, min_score_margin=0.0):
    scores = np.asarray(scores)
    mask = np.asarray(mask, dtype=np.bool_)
    if scores.ndim != 1 or scores.shape != mask.shape or not mask[0]:
        raise ValueError("macro scores/mask require an available baseline")
    margin = float(min_score_margin)
    if not np.isfinite(margin) or margin < 0.0:
        raise ValueError("macro score margin must be finite and nonnegative")
    if not np.all(np.isfinite(scores[mask])):
        return 0, "nonfinite_scores"
    best = int(np.argmax(np.where(mask, scores, -np.inf)))
    if best == 0 or scores[best] <= scores[0] + margin:
        reason = "baseline_margin" if best != 0 and margin > 0.0 else "baseline_tie_or_best"
        return 0, reason
    return best, "learned_macro"


def macro_reward(before, after):
    totals = []
    for metrics in (before, after):
        total = float(metrics["queue_integral_vehicle_seconds"])
        network = float(metrics["network_queue_integral_vehicle_seconds"])
        pending = float(metrics["pending_integral_vehicle_seconds"])
        if not all(math.isfinite(value) and value >= 0 for value in (total, network, pending)) \
                or not math.isclose(total, network + pending, rel_tol=1e-10, abs_tol=1e-6):
            raise ValueError("network plus pending integral does not match objective")
        totals.append(total)
    if totals[1] < totals[0]:
        raise ValueError("queue integral decreased inside a macro")
    return -(totals[1] - totals[0])


def smdp_targets(rewards, next_values, dones, durations, gamma):
    # Replay retains the exact physical reward. Only the critic's numerical
    # units change; multiplying all returns by a positive constant preserves
    # action ordering and the underlying traffic objective.
    rewards = (np.asarray(rewards, dtype=np.float64)
               / CRITIC_UNITS["vehicle_seconds_per_unit"])
    durations = np.asarray(durations, dtype=np.float64)
    done = np.asarray(dones, dtype=np.bool_)
    if np.any(durations <= 0) or not 0 <= gamma <= 1:
        raise ValueError("invalid SMDP duration or gamma")
    future = np.where(done, 0.0, np.asarray(next_values, dtype=np.float64))
    targets = rewards + np.power(float(gamma), durations / 300.0) * future
    if not np.all(np.isfinite(targets)):
        raise ValueError("nonfinite SMDP target")
    return targets


class ResidualDDQN(PhaseScoringDDQN):
    controller_family = "schedule_residual_ddqn"

    @staticmethod
    def _validate_critic_contract(contract):
        if contract.get("critic_units") != CRITIC_UNITS:
            raise ValueError("checkpoint critic unit contract mismatch")

    def save_bundle(self, directory, contract):
        self._validate_critic_contract(contract)
        super(ResidualDDQN, self).save_bundle(directory, contract)
        path = os.path.join(directory, "weights.npz")
        with np.load(path) as source:
            arrays = {key: source[key].copy() for key in source.files}
        arrays["meta_critic_vehicle_seconds_per_unit"] = np.asarray(
            CRITIC_UNITS["vehicle_seconds_per_unit"], np.float64)
        np.savez(path, **arrays)

    @classmethod
    def load_bundle(cls, directory, expected_contract):
        cls._validate_critic_contract(expected_contract)
        with np.load(os.path.join(directory, "weights.npz")) as source:
            field = "meta_critic_vehicle_seconds_per_unit"
            if field not in source.files or float(source[field]) != CRITIC_UNITS["vehicle_seconds_per_unit"]:
                raise ValueError("checkpoint weights critic unit mismatch")
        return super(ResidualDDQN, cls).load_bundle(directory, expected_contract)

    def train_macro_step(self, features, actions, rewards, next_features,
                         dones, next_masks, durations, gamma):
        features = np.asarray(features, dtype=np.float32)
        actions = np.asarray(actions, dtype=np.int64)
        batch, macros, _ = features.shape
        q, cache = self._scores(features, self._online())
        online_next, _ = self._scores(next_features, self._online())
        next_actions = np.argmax(np.where(next_masks, online_next, -np.inf), axis=1)
        target_next, _ = self._scores(next_features, self._target())
        targets = smdp_targets(rewards, target_next[np.arange(batch), next_actions],
                               dones, durations, gamma)
        difference = q[np.arange(batch), actions] - targets
        absolute = np.abs(difference)
        quadratic = np.minimum(absolute, self.huber_delta)
        loss = float(np.mean(.5 * quadratic ** 2
                             + self.huber_delta * (absolute - quadratic)))
        gradient = np.zeros((batch, macros), dtype=np.float32)
        gradient[np.arange(batch), actions] = np.clip(
            difference, -self.huber_delta, self.huber_delta) / batch
        self._adam_step(self._backprop(gradient.reshape(-1, 1), cache))
        return loss


class ScheduleResidualController(object):
    name = "schedule_residual_ddqn"

    def __init__(self, env, network, time_of_day, epsilon=0.0, seed=0,
                 zero_residual=False, catalog=None, min_score_margin=0.0):
        if time_of_day not in ("normal", "am_peak", "pm_peak"):
            raise ValueError("time_of_day must be declared normal, am_peak, or pm_peak")
        if env.action_interval != 10 or env.sim_step_seconds != 1 \
                or env.max_steps % 300:
            raise ValueError("macro runtime requires 10s actions, 1s steps, 300s blocks")
        if not 0 <= epsilon <= 1:
            raise ValueError("epsilon must be in [0, 1]")
        self.env, self.network = env, network
        self.time_of_day = time_of_day
        self.epsilon, self.zero_residual = float(epsilon), bool(zero_residual)
        self.min_score_margin = float(min_score_margin)
        if not np.isfinite(self.min_score_margin) or self.min_score_margin < 0.0:
            raise ValueError("macro score margin must be finite and nonnegative")
        self.rng = np.random.RandomState(seed)
        self.catalog = {} if catalog is None else catalog
        self.shadows = {node: ShadowSignal(env.roadnet, node,
                        action_interval=env.action_interval, min_green=env.min_green,
                        maximum_red=env.maximum_red) for node in env.agent_ids}
        self._prior_observer = env.signal_observer
        env.signal_observer = self._observe
        self.reset()

    def reset(self):
        self.block_start = None
        self.chosen = {}
        self.expected = {}
        self.references = {}
        self.block_features, self.block_masks, self.block_actions = {}, {}, {}
        self.audit = {key: 0 for key in (
            "observed_node_seconds", "phase_divergence_seconds", "service_divergence_seconds",
            "state_divergence_seconds", "nonzero_macros", "illegal_requests",
            "anchor_violations", "unlogged_divergence_seconds", "resync_successes")}
        self.audit.update({"time_of_day": self.time_of_day, "macro_events": [],
                           "nonzero_macro_nodes": [], "abstentions": {},
                           "phase_definition": "lightphase_exposed_during_simulator_step",
                           "service_definition": "movement_time_since_service_divergence"})
        self._active_nodes = set()

    def _block(self, node, start):
        key = (node, start, self.env.min_green, self.env.maximum_red)
        if key not in self.catalog:
            self.catalog[key] = compile_block(self.shadows[node], start)
        return self.catalog[key]

    def _features(self, observation, block):
        phases = np.asarray(observation, dtype=np.float32)
        if phases.ndim != 2 or phases.shape[1] < len(FEATURES):
            raise ValueError("residual requires phase-row observations")
        rows = np.zeros((MAX_MACROS, len(MACRO_FEATURES)), np.float32)
        mask = np.zeros(MAX_MACROS, np.bool_)
        for item in block["templates"]:
            index = item["macro_id"]
            if index == 0:
                source = target = phases[:self.env.num_actions[block["node"]], :12].mean(axis=0)
                descriptor = [0, 0, 1]
            else:
                tick = (item["boundary_second"] - block["start_second"]) // 10
                baseline = block["templates"][0]["commands"]
                source = phases[baseline[tick - 1], :12]
                target = phases[baseline[tick], :12]
                descriptor = [tick / 30.0, item["shift_seconds"] / 10.0, 0]
            rows[index] = np.concatenate((source, target, descriptor))
            mask[index] = True
        return rows, mask

    def _anchor_check(self):
        if self.block_start is None:
            return
        for node in self.env.agent_ids:
            if signal_state(self.env, node) != self.references[node]["terminal_state"]:
                self.audit["anchor_violations"] += 1
                raise ValueError("residual terminal signal anchor mismatch at " + node)
            self.audit["resync_successes"] += 1

    def macro_observations(self, observations, start):
        result = {}
        for node in self.env.agent_ids:
            block = self._block(node, start)
            block["node"] = node
            result[node] = self._features(observations[node], block)
        return result

    def _start_block(self, observations):
        self._anchor_check()
        if self.block_start is not None:
            # The terminal anchor above is the last consumer that needs the
            # completed trace.  Release its deepcopy and per-second timeline
            # before replacing it with the next block's reference.
            for node in self.env.agent_ids:
                self.shadows[node].release_reference(self.block_start, 300)
        self.block_start = self.env._t
        for node in self.env.agent_ids:
            shadow = self.shadows[node]
            ref = shadow.reference(self.block_start, 300)
            self.references[node] = ref
            if signal_state(self.env, node) != ref["initial_state"]:
                self.audit["anchor_violations"] += 1
                raise ValueError("residual initial signal anchor mismatch at " + node)
            if self.time_of_day == "normal" or self.zero_residual:
                choice = 0
                reason = ("normal_exact_reference" if self.time_of_day == "normal"
                          else "zero_residual_diagnostic")
                template = {"macro_id": 0, "commands": ref["commands"],
                            "boundary_second": None, "shift_seconds": 0}
                self.expected[node] = ref["trace"]
            else:
                block = self._block(node, self.block_start)
                block["node"] = node
                features, mask = self._features(observations[node], block)
                if not np.all(np.isfinite(features)):
                    choice, reason = 0, "nonfinite_observations"
                elif self.rng.rand() < self.epsilon:
                    choice = int(self.rng.choice(np.flatnonzero(mask)))
                    reason = "training_exploration" if choice else "exploration_baseline"
                else:
                    choice, reason = select_macro(
                        self.network.q_values(features, mask)[0], mask,
                        self.min_score_margin)
                template = block["templates"][choice]
                self.block_features[node], self.block_masks[node] = features, mask
                self.block_actions[node] = choice
                self.expected[node] = (ref["trace"] if choice == 0 else
                                       shadow.execute(ref, template["commands"])["trace"])
            self.chosen[node] = template
            if choice:
                self.audit["nonzero_macros"] += 1
                self._active_nodes.add(node)
            else:
                counts = self.audit["abstentions"]
                counts[reason] = counts.get(reason, 0) + 1
            self.audit["macro_events"].append({
                "node": node, "block_start_second": self.block_start,
                "macro_id": choice, "reason": reason,
                "boundary_second": template["boundary_second"],
                "shift_seconds": template["shift_seconds"]})

    def act(self, context):
        if self.env._t % 300 == 0:
            self._start_block(context["observations"])
        tick = (self.env._t - self.block_start) // 10
        masks = self.env.action_masks()
        actions = {}
        for node in self.env.agent_ids:
            command = self.chosen[node]["commands"][tick]
            if not masks[node][command]:
                self.audit["illegal_requests"] += 1
                raise ValueError("compiled residual command became illegal at " + node)
            actions[node] = command
        return actions

    def _observe(self, env):
        index = env._t - self.block_start - 1
        for node in env.agent_ids:
            state = signal_state(env, node)
            ref = self.references[node]["trace"][index]["state"]
            self.audit["observed_node_seconds"] += 1
            self.audit["state_divergence_seconds"] += int(state != ref)
            self.audit["phase_divergence_seconds"] += int(
                env._last_step_lightphases[node]
                != self.references[node]["trace"][index]["served_lightphase"])
            self.audit["service_divergence_seconds"] += int(state["movement_service_timers"] != ref["movement_service_timers"])
            self.audit["unlogged_divergence_seconds"] += int(
                state != self.expected[node][index]["state"]
                or env._last_step_lightphases[node]
                != self.expected[node][index]["served_lightphase"])
        if self._prior_observer is not None:
            self._prior_observer(env)

    def finalize(self):
        self._anchor_check()
        self.audit["nonzero_macro_nodes"] = sorted(self._active_nodes)
        return self.audit
