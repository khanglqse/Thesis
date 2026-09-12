"""Train-only macro SMDP learning and validation-only residual pilots."""
import json
import os
import time

import numpy as np

from traffic_rl.agents.schedule_residual import (
    MACRO_FEATURES, MAX_MACROS, POLICY_INPUT_SCHEMA, CRITIC_UNITS,
    ResidualDDQN, ScheduleResidualController, macro_reward)
from traffic_rl.train.case_sampler import BalancedCaseSampler
from traffic_rl.train.network_replay import NetworkReplayBuffer
from traffic_rl.train.network_trainer import (
    _assert_rollout_complete, _close, _file_sha256, _load_precomputed_tuning,
    _rollout, _tracked_tree_attestation, _tuning_binding, _validate_precomputed_tuning,
    _verify_training_foundation, _default_foundation_verifier, _write_json,
    canonical_json_sha256)


OPERATIONAL_MODE = {
    "input": "declared_time_of_day",
    "normal": "exact_executed_fixed25_from_reset",
    "peaks": "raw_greedy_prevalidated_macro",
    "forbidden_features": ["case_id", "learning_seed", "demand_seed",
                           "simulator_seed", "filename", "future_flow"],
}


def operational_time_of_day(case):
    mode = case.get("scenario")
    if mode not in ("normal", "am_peak", "pm_peak"):
        raise ValueError("unknown declared operational time-of-day mode")
    if case.get("operational_time_of_day") != mode:
        raise ValueError("operational time-of-day declaration mismatch")
    return mode


def validate_config(config):
    if config.get("schema_version") != 1 or config.get("controller_family") != "schedule_residual_ddqn":
        raise ValueError("invalid schedule residual config")
    if config.get("macro") != {"duration_seconds": 300, "shift_seconds": 10,
                               "baseline_green_seconds": 25}:
        raise ValueError("residual macro contract drift")
    if config.get("reward") != {"type": "negative_network_queue_plus_pending_integral"}:
        raise ValueError("residual reward contract drift")
    if config.get("operational_mode") != OPERATIONAL_MODE:
        raise ValueError("operational time-of-day input contract drift")
    if config.get("critic_units") != CRITIC_UNITS:
        raise ValueError("critic unit contract drift")
    safety = config.get("safety", {})
    if not isinstance(safety, dict) or set(safety) - {"min_score_margin"}:
        raise ValueError("residual safety config drift")
    margin = float(safety.get("min_score_margin", 0.0))
    if not np.isfinite(margin) or margin < 0.0:
        raise ValueError("residual safety margin must be finite and nonnegative")
    mode, run = config.get("mode"), config.get("run", {})
    if mode == "pilot":
        if run != {"episodes": 4, "horizon_seconds": 3600, "eval_every": 2} \
                or config.get("learning_seed") != 11:
            raise ValueError("pilot protocol requires seed11,4 full-hour episodes,eval2/4")
    elif mode == "smoke":
        if run != {"episodes": 2, "horizon_seconds": 600, "eval_every": 2}:
            raise ValueError("smoke protocol requires 2 episodes of600s,eval2")
    elif mode == "final":
        if (run != {"episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
                or config.get("learning_seed") not in (12, 13, 14, 15, 16)):
            raise ValueError("final residual protocol requires seeds12-16,12 full-hour episodes,eval4/8/12")
        pilot = config.get("pilot_selection")
        release = config.get("final_release")
        binding = release.get("selection") if isinstance(release, dict) else None
        if (not isinstance(pilot, dict) or not isinstance(binding, dict)
                or binding.get("schema_version") != 1
                or binding.get("decision_type") != "haichau_residual_pilot_selection"
                or binding.get("controller_family") != "schedule_residual_ddqn"
                or binding.get("test_split_accessed") is not False
                or pilot.get("decision_type") != binding["decision_type"]
                or pilot.get("selected_checkpoint") != binding.get("selected_checkpoint")
                or pilot.get("training_step") != binding.get("training_step")
                or pilot.get("test_split_accessed") is not False):
            raise ValueError("final residual selection binding is invalid")
        selected = binding.get("selected_config")
        artifacts = binding.get("checkpoint_artifacts")
        if (not isinstance(selected, dict) or not isinstance(selected.get("path"), str)
                or not isinstance(selected.get("sha256"), str)
                or len(selected["sha256"]) != 64
                or not isinstance(artifacts, dict)
                or not isinstance(artifacts.get("weights_sha256"), str)
                or len(artifacts["weights_sha256"]) != 64
                or not isinstance(binding.get("training_step"), int)
                or binding["training_step"] <= 0
                or not isinstance(binding.get("selected_checkpoint"), str)):
            raise ValueError("final residual selection binding is incomplete")
    else:
        raise ValueError("unknown residual mode")


def training_cases(manifest):
    cases = [case for case in manifest["cases"] if case.get("split") == "train"
             and case.get("scenario") in ("am_peak", "pm_peak")]
    if set(case["scenario"] for case in cases) != {"am_peak", "pm_peak"}:
        raise ValueError("residual training requires both declared peak regimes")
    return cases


def _integrals(env):
    return {"queue_integral_vehicle_seconds": env._queue_integral_vehicle_seconds,
            "network_queue_integral_vehicle_seconds": env._network_queue_integral_vehicle_seconds,
            "pending_integral_vehicle_seconds": env._pending_integral_vehicle_seconds}


def run_macro_episode(env, network, time_of_day, epsilon=0.0, seed=0,
                      zero_residual=False, catalog=None, transition_callback=None,
                      min_score_margin=0.0):
    """Execute one episode; learning callbacks receive completed 300s macros."""
    controller = ScheduleResidualController(env, network, time_of_day,
            epsilon=epsilon, seed=seed, zero_residual=zero_residual, catalog=catalog,
            min_score_margin=min_score_margin)
    try:
        return _execute_macro_episode(env, controller, transition_callback)
    finally:
        # Do not leave a controller<->environment cycle or mutate the previous
        # episode's returned audit if a caller reuses this environment.
        env.signal_observer = controller._prior_observer


def _execute_macro_episode(env, controller, transition_callback):
    time_of_day, zero_residual = controller.time_of_day, controller.zero_residual
    observations = env.reset()
    controller.reset()
    done, info = False, {}
    macro_rewards = []
    while not done:
        start = env._t
        before = _integrals(env)
        first_actions = controller.act({"observations": observations})
        snapshots = {node: (controller.block_features[node].copy(),
                           controller.block_actions[node])
                     for node in controller.block_features}
        observations, _, done, info = env.step(first_actions)
        while env._t % 300:
            observations, _, done, info = env.step(
                controller.act({"observations": observations}))
        reward = macro_reward(before, info)
        reward_record = {
            "block_start_second": start, "duration_seconds": env._t - start,
            "raw_objective_vehicle_seconds": -reward,
            "raw_reward_vehicle_seconds": reward,
            "scaled_reward": reward / CRITIC_UNITS["vehicle_seconds_per_unit"],
            "network_queue_vehicle_seconds": (info["network_queue_integral_vehicle_seconds"]
                                               - before["network_queue_integral_vehicle_seconds"]),
            "entry_pending_vehicle_seconds": (info["pending_integral_vehicle_seconds"]
                                               - before["pending_integral_vehicle_seconds"]),
        }
        macro_rewards.append(reward_record)
        if transition_callback is not None:
            if time_of_day == "normal" or zero_residual:
                raise ValueError("normal/reference episodes cannot enter learning replay")
            next_options = ({} if done else
                            controller.macro_observations(observations, env._t))
            for node, (features, action) in snapshots.items():
                if done:
                    next_features = np.zeros_like(features)
                    next_mask = np.zeros(MAX_MACROS, np.bool_)
                    next_mask[0] = True
                else:
                    next_features, next_mask = next_options[node]
                transition_callback({"features": features, "action": action,
                    "reward": reward, "next_features": next_features,
                    "raw_objective_vehicle_seconds": -reward,
                    "scaled_reward": reward_record["scaled_reward"],
                    "next_mask": next_mask, "done": done,
                    "duration_seconds": env._t - start, "scenario": time_of_day,
                    "node": node})
    result = dict(info)
    result["policy_audit"] = controller.finalize()
    result["macro_rewards"] = macro_rewards
    return result


def _summary_metrics(info):
    return {key: info.get(key) for key in (
        "queue_integral_vehicle_seconds", "network_queue_integral_vehicle_seconds",
        "pending_integral_vehicle_seconds", "completion_rate", "insertion_rate",
        "phase_switches", "max_red_seconds", "step", "scheduled", "due",
        "inserted", "arrived", "running", "pending")}


def _bound_checkpoint(directory, output_dir):
    return {"contract_path": os.path.relpath(os.path.join(directory, "contract.json"), output_dir),
            "contract_sha256": _file_sha256(os.path.join(directory, "contract.json")),
            "weights_path": os.path.relpath(os.path.join(directory, "weights.npz"), output_dir),
            "weights_sha256": _file_sha256(os.path.join(directory, "weights.npz"))}


def train_residual(env_factory, manifest, config, output_dir, foundation_root,
                   baseline_tuning_artifact, foundation_verifier=None):
    validate_config(config)
    attestation = _tracked_tree_attestation(foundation_root)
    verification = _verify_training_foundation(foundation_root, manifest,
        foundation_verifier or _default_foundation_verifier)
    train = training_cases(manifest)
    validation = [case for case in manifest["cases"] if case.get("split") == "validation"]
    if len(validation) != 6 or set(case["scenario"] for case in validation) != {"normal", "am_peak", "pm_peak"}:
        raise ValueError("residual validation requires six declared validation cases")
    for case in train + validation:
        operational_time_of_day(case)
    tuning, provenance = _load_precomputed_tuning(baseline_tuning_artifact)
    baseline_config = {"baseline": config["baseline"], "simulation": manifest["simulation"]}
    _validate_precomputed_tuning(tuning,
        _tuning_binding(manifest, validation, 3600, baseline_config), baseline_config, validation)
    if tuning["selected"]["fixed_green_duration"] != 25:
        raise ValueError("residual reference must match validation-selected fixed25")
    if os.path.exists(output_dir):
        raise ValueError("residual output directory already exists; runs are immutable")
    os.makedirs(output_dir)
    started = time.time()
    status_path = os.path.join(output_dir, "status.json")
    _write_json(status_path, {"status": "partial", "reason": "run in progress"})
    resolved = dict(config)
    resolved.update({"source_tree": attestation, "manifest_sha256": canonical_json_sha256(manifest),
                     "baseline_tuning_sha256": tuning["tuning_sha256"]})
    _write_json(os.path.join(output_dir, "resolved-config.json"), resolved)
    run_manifest = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
        "mode": config["mode"], "learning_seed": config["learning_seed"],
        "manifest_sha256": canonical_json_sha256(manifest),
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "runtime": manifest["runtime"], "code_commit": attestation["git_commit"],
        "source_tree": attestation, "foundation_verification": verification,
        "training_case_ids": [case["case_id"] for case in train],
        "validation_case_ids": [case["case_id"] for case in validation],
        "test_split_accessed": False,
        "operational_mode": {"input": "declared_time_of_day",
            "operational_mode_source": "preregistered_time_of_day",
            "source_manifest_field": "cases[].operational_time_of_day",
            "allowed_values": ["normal", "am_peak", "pm_peak"],
            "inference_inputs": ["current_phase_rows", "current_signal_state", "elapsed_seconds"],
            "case_id_seed_filename_future_flow_features": False}}
    run_manifest["policy_input_schema"] = POLICY_INPUT_SCHEMA
    _write_json(os.path.join(output_dir, "run-manifest.json"), run_manifest)
    _write_json(os.path.join(output_dir, "baseline-tuning.json"), tuning)
    model, optimizer = config["model"], config["optimizer"]
    net = ResidualDDQN(len(MACRO_FEATURES), model["hidden"], model["lr"],
                        config["learning_seed"], grad_clip=optimizer["grad_clip"],
                        huber_delta=optimizer["huber_delta"])
    # Start with an exact baseline tie; interventions first arise from explicit,
    # logged training exploration and then learned value differences.
    net.W3[:] = 0
    net.b3[:] = 0
    net.sync_target()
    replay = NetworkReplayBuffer(optimizer["buffer_capacity"], MAX_MACROS,
                                  len(MACRO_FEATURES), config["learning_seed"])
    catalog = {}
    horizon = config["run"]["horizon_seconds"]
    if config["mode"] == "smoke":
        validation = [next(case for case in validation if case["scenario"] == regime)
                      for regime in ("normal", "am_peak", "pm_peak")]
    baseline_rows = {}
    updates, losses, episodes, checkpoint_records = [0], [], [], []

    def receive(transition):
        replay.add(transition["features"], transition["action"], transition["reward"],
                   transition["next_features"], transition["done"], transition["next_mask"],
                   transition["scenario"])
        # Update once per complete network macro, after every node contributed.
        if len(replay) >= optimizer["train_start"] and transition["node"] == agent_ids[-1]:
            for _ in range(optimizer["updates_per_macro"]):
                batch = replay.sample(optimizer["batch_size"])
                loss = net.train_macro_step(batch["features"], batch["actions"], batch["rewards"],
                    batch["next_features"], batch["dones"], batch["next_masks"],
                    np.full(len(batch["actions"]), 300), model["gamma_per_macro"])
                if not np.isfinite(loss):
                    raise ValueError("nonfinite residual training loss")
                losses.append(loss)
                updates[0] += 1
                if updates[0] % optimizer["target_sync"] == 0:
                    net.sync_target()

    sampler = BalancedCaseSampler(train, config["learning_seed"])
    try:
        for episode in range(1, config["run"]["episodes"] + 1):
            case = sampler.next_case()
            env = env_factory(case, horizon)
            agent_ids = env.agent_ids
            if list(agent_ids) != list(manifest["network"]["agent_ids"]):
                raise ValueError("training environment signal IDs differ from manifest")
            epsilon = config["exploration"]["epsilon"]
            print("residual training episode %d/%d %s" % (
                episode, config["run"]["episodes"], case["case_id"]), flush=True)
            try:
                result = run_macro_episode(env, net, operational_time_of_day(case), epsilon=epsilon,
                    seed=config["learning_seed"] * 1000 + episode,
                    catalog=catalog, transition_callback=receive,
                    min_score_margin=config.get("safety", {}).get("min_score_margin", 0.0))
                _assert_rollout_complete(result, horizon, "residual training")
            finally:
                _close(env)
            record = {"episode": episode, "case_id": case["case_id"], "scenario": case["scenario"],
                      "optimizer_updates": updates[0], "metrics": _summary_metrics(result),
                      "macro_rewards": result["macro_rewards"],
                      "policy_audit": result["policy_audit"]}
            episodes.append(record)
            _write_json(os.path.join(output_dir, "learning-curve.json"), episodes)
            if episode % config["run"]["eval_every"]:
                continue
            contract = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
                "feature_dim": len(MACRO_FEATURES), "feature_order": MACRO_FEATURES,
                "hidden_size": model["hidden"], "max_macros": MAX_MACROS,
                "macro": config["macro"], "normal_policy": "exact_executed_fixed25_from_reset",
                "critic_units": config["critic_units"],
                "policy_input_schema": POLICY_INPUT_SCHEMA,
                "peak_policy": "raw_greedy_prevalidated_macro_with_baseline_tie_break",
                "network_sha256": manifest["network"]["sha256"],
                "phase_contract_sha256": manifest["phase_contract"]["sha256"],
                "simulation": manifest["simulation"], "normalization": manifest["preprocessing"],
                "code_commit": attestation["git_commit"], "training_step": episode,
                "learning_seed": config["learning_seed"], "mode": config["mode"],
                "training_config_sha256": canonical_json_sha256(config),
                "baseline_tuning_sha256": tuning["tuning_sha256"]}
            directory = os.path.join(output_dir, "checkpoints", "step-%04d" % episode)
            net.save_bundle(directory, contract)
            loaded = ResidualDDQN.load_bundle(directory, contract)
            probe = np.random.RandomState(730).randn(5, MAX_MACROS, len(MACRO_FEATURES)).astype(np.float32)
            probe_mask = np.ones((5, MAX_MACROS), np.bool_)
            if not np.array_equal(net.q_values(probe, probe_mask), loaded.q_values(probe, probe_mask)):
                raise ValueError("checkpoint reload scores differ")
            rows = []
            for index, case in enumerate(validation):
                print("residual validation step%d case%d/%d %s" % (
                    episode, index + 1, len(validation), case["case_id"]), flush=True)
                if case["case_id"] not in baseline_rows:
                    env = env_factory(case, horizon)
                    try:
                        baseline = run_macro_episode(env, loaded, operational_time_of_day(case),
                            zero_residual=True, catalog=catalog)
                        _assert_rollout_complete(baseline, horizon, "forced macro0 counterfactual")
                    finally:
                        _close(env)
                    baseline_rows[case["case_id"]] = baseline
                    if config["mode"] == "smoke":
                        env = env_factory(case, horizon)
                        try:
                            fixed = _rollout(env, None, fixed_green_duration=25)
                        finally:
                            _close(env)
                        for field in ("queue_integral_vehicle_seconds", "completion_rate", "insertion_rate"):
                            if fixed.get(field) != baseline.get(field):
                                raise ValueError("forced macro0 differs from fresh fixed25: " + field)
                baseline = baseline_rows[case["case_id"]]
                env = env_factory(case, horizon)
                try:
                    candidate = run_macro_episode(
                        env, loaded, operational_time_of_day(case), catalog=catalog,
                        min_score_margin=config.get("safety", {}).get(
                            "min_score_margin", 0.0))
                    _assert_rollout_complete(candidate, horizon, "residual validation")
                finally:
                    _close(env)
                rows.append({"case_id": case["case_id"], "scenario": case["scenario"],
                    "horizon_seconds": horizon, "baseline": _summary_metrics(baseline),
                    "candidate": _summary_metrics(candidate), "policy_audit": candidate["policy_audit"],
                    "candidate_macro_rewards": candidate["macro_rewards"],
                    "baseline_macro_rewards": baseline["macro_rewards"],
                    "baseline_policy": "forced_macro0_counterfactual",
                    "baseline_policy_audit": baseline["policy_audit"],
                    "counterfactual_weight_independence": "macro0 never evaluates network",
                    "operational_mode_source": "preregistered_time_of_day",
                    "source_manifest_field": "cases[].operational_time_of_day",
                    "operational_time_of_day": operational_time_of_day(case)})
            artifact = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
                "mode": config["mode"], "learning_seed": config["learning_seed"],
                "training_step": episode, "checkpoint": _bound_checkpoint(directory, output_dir),
                "rows": rows, "reload_score_identity": True}
            relative = "validation-step-%04d.json" % episode
            _write_json(os.path.join(output_dir, relative), artifact)
            checkpoint_records.append({"training_step": episode, "validation_path": relative,
                                       "checkpoint": artifact["checkpoint"]})
        if updates[0] == 0:
            raise ValueError("residual run made no optimizer updates")
        if _tracked_tree_attestation(foundation_root) != attestation:
            raise ValueError("source tree changed during residual training")
        summary = {"schema_version": 1, "controller_family": "schedule_residual_ddqn",
            "mode": config["mode"], "learning_seed": config["learning_seed"],
            "episodes": len(episodes), "optimizer_updates": updates[0],
            "replay_coverage": replay.coverage(), "checkpoints": checkpoint_records,
            "mean_training_loss": float(np.mean(losses)), "wall_time_seconds": time.time() - started,
            "test_split_accessed": False,
            "selection": ("requires_preregistered_final_residual_selector"
                          if config["mode"] == "final" else
                          "requires_preregistered_residual_selector")}
        _write_json(os.path.join(output_dir, "summary.json"), summary)
        hashes = {}
        for parent, _, files in os.walk(output_dir):
            for name in files:
                path = os.path.join(parent, name)
                if name != "status.json" and "runtime-configs" not in path:
                    hashes[os.path.relpath(path, output_dir)] = _file_sha256(path)
        status = {"status": "complete", "source_tree": attestation,
                  "artifact_sha256": hashes}
        if config["mode"] == "final":
            status.update({"eligible_for_test_evaluation": False,
                           "reason": "final must pass preregistered per-seed selector"})
        else:
            status.update({"eligible_for_final": False,
                           "reason": "pilot must pass preregistered selector"})
        _write_json(status_path, status)
        return summary
    except Exception as exc:
        _write_json(status_path, {"status": "failed", "reason": str(exc), "source_tree": attestation})
        raise
