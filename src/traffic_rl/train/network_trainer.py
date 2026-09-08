"""Balanced multi-case training for the neighbor-aware phase DDQN."""
import json
import hashlib
import importlib.util
import os
import subprocess
import time

import numpy as np

from traffic_rl.agents.dqn import NStepAccumulator
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.checkpoint_selection import (
    choose_checkpoint, choose_reporting_checkpoint, score_validation)
from traffic_rl.sim.phase_encoder import FEATURES
from traffic_rl.train.case_sampler import BalancedCaseSampler
from traffic_rl.train.network_replay import NetworkReplayBuffer


def _write_json(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
    os.replace(temporary, path)


def canonical_json_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _git_sha(root):
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root,
            stderr=subprocess.STDOUT).decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _default_foundation_verifier(root, manifest):
    verifier_path = os.path.join(
        os.path.abspath(root), "scripts", "verify_haichau_foundation.py")
    try:
        spec = importlib.util.spec_from_file_location(
            "_traffic_rl_haichau_foundation_verifier", verifier_path)
        if spec is None or spec.loader is None:
            raise ImportError("cannot create module spec for %s" % verifier_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verify_foundation = module.verify_foundation
    except (AttributeError, ImportError, IOError) as exc:
        raise ValueError("foundation verifier is unavailable: %s" % exc)
    return verify_foundation(root, manifest)


def _verify_training_foundation(root, manifest, verifier):
    evidence = verifier(root, manifest)
    if not isinstance(evidence, dict) or evidence.get("status") != "verified":
        raise ValueError("foundation verifier did not return verified status")
    expected = {
        "network_sha256": manifest.get("network", {}).get("sha256"),
        "generator_config_sha256": manifest.get("generator_config_sha256"),
        "runtime_digest": manifest.get("runtime", {}).get("base_image_digest"),
    }
    for field, value in expected.items():
        if not value or evidence.get(field) != value:
            raise ValueError("foundation verification %s mismatch" % field)
    return evidence


def resolve_training_config(config, mode, learning_seed):
    """Resolve one immutable run tier without mutating the loaded YAML value."""
    if mode not in config.get("tiers", {}):
        raise ValueError("unknown training mode: %s" % mode)
    resolved = json.loads(json.dumps(config))
    resolved["mode"] = mode
    resolved["learning_seed"] = int(learning_seed)
    resolved["run"] = dict(resolved["tiers"][mode])
    return resolved


def _epsilon(decisions, exploration):
    start = float(exploration["epsilon_start"])
    end = float(exploration["epsilon_end"])
    decay = max(1, int(exploration["epsilon_decay_decisions"]))
    fraction = min(1.0, float(decisions) / decay)
    return start + fraction * (end - start)


def _close(env):
    if hasattr(env, "close"):
        env.close()


def _assert_rollout_complete(info, horizon_seconds, label):
    if int(info.get("step", -1)) != int(horizon_seconds):
        raise ValueError("%s did not complete required horizon" % label)
    queue_integral = info.get("queue_integral_vehicle_seconds")
    if queue_integral is None or not np.isfinite(float(queue_integral)):
        raise ValueError("%s has invalid queue integral" % label)


def _rollout(env, net, fixed_green_duration=None, action_interval=10):
    observations = env.reset()
    done = False
    info = {}
    decision = 0
    while not done:
        masks = env.action_masks()
        actions = {}
        if fixed_green_duration is None:
            feature_batch = np.asarray(
                [observations[agent_id] for agent_id in env.agent_ids])
            mask_batch = np.asarray(
                [masks[agent_id] for agent_id in env.agent_ids])
            greedy = np.argmax(net.q_values(feature_batch, mask_batch), axis=1)
            actions = {agent_id: int(greedy[index])
                       for index, agent_id in enumerate(env.agent_ids)}
        else:
            for agent_id in env.agent_ids:
                phase_count = env.num_actions[agent_id]
                requested = int(decision * action_interval
                                / float(fixed_green_duration)) % phase_count
                if not masks[agent_id][requested]:
                    requested = int(np.flatnonzero(masks[agent_id])[0])
                actions[agent_id] = requested
        observations, _, done, info = env.step(actions)
        decision += 1
    return info


def _tune_fixed_time(env_factory, cases, horizon_seconds, config, binding):
    baseline = config.get("baseline", {})
    if baseline.get("controller") != "validation_tuned_fixed":
        raise ValueError("baseline controller must be validation_tuned_fixed")
    durations = baseline.get("search_green_durations", [])
    if not durations or any(int(value) <= 0 for value in durations):
        raise ValueError("baseline search_green_durations must be positive")
    action_interval = config.get("simulation", {}).get("action_interval", 10)
    candidates = []
    for duration in sorted(set(int(value) for value in durations)):
        rows = []
        for case in cases:
            env = env_factory(case, horizon_seconds)
            try:
                info = _rollout(env, None, fixed_green_duration=duration,
                                action_interval=action_interval)
            finally:
                _close(env)
            _assert_rollout_complete(
                info, horizon_seconds, "fixed-time tuning %s" % case["case_id"])
            rows.append({
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "queue_integral_vehicle_seconds": float(
                    info["queue_integral_vehicle_seconds"]),
                "completion_rate": info.get("completion_rate"),
            })
        mean_queue = sum(row["queue_integral_vehicle_seconds"]
                         for row in rows) / len(rows)
        candidates.append({"fixed_green_duration": duration,
                           "mean_queue_integral_vehicle_seconds": mean_queue,
                           "rows": rows})
    selected = min(candidates, key=lambda row: (
        row["mean_queue_integral_vehicle_seconds"],
        row["fixed_green_duration"]))
    result = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "search_space": {"fixed_green_duration": sorted(
            set(int(value) for value in durations))},
        "selected": {"fixed_green_duration": selected["fixed_green_duration"]},
        "candidates": candidates,
        "binding": binding,
    }
    result["tuning_sha256"] = canonical_json_sha256(result)
    return result


def _validation_rows(env_factory, cases, horizon_seconds, net, config,
                     fixed_duration):
    rows = []
    action_interval = config.get("simulation", {}).get("action_interval", 10)
    for case in cases:
        candidate_env = env_factory(case, horizon_seconds)
        try:
            candidate = _rollout(candidate_env, net,
                                 action_interval=action_interval)
        finally:
            _close(candidate_env)
        _assert_rollout_complete(
            candidate, horizon_seconds, "candidate validation %s" % case["case_id"])
        baseline_env = env_factory(case, horizon_seconds)
        try:
            baseline = _rollout(
                baseline_env, net, fixed_green_duration=fixed_duration,
                action_interval=action_interval)
        finally:
            _close(baseline_env)
        _assert_rollout_complete(
            baseline, horizon_seconds, "baseline validation %s" % case["case_id"])
        row = {
            "case_id": case["case_id"],
            "scenario": case["scenario"],
            "demand_seed": case.get("demand_seed"),
            "sim_seed": case.get("sim_seed"),
            "candidate_queue": float(candidate["queue_integral_vehicle_seconds"]),
            "baseline_queue": float(baseline["queue_integral_vehicle_seconds"]),
            "fresh_candidate": True,
            "fresh_baseline": True,
        }
        if candidate.get("completion_rate") is not None \
                and baseline.get("completion_rate") is not None:
            row["candidate_completion"] = float(candidate["completion_rate"])
            row["baseline_completion"] = float(baseline["completion_rate"])
        rows.append(row)
    return rows


def _checkpoint_contract(manifest, config, max_green, tuning, verification):
    preprocessing = manifest["preprocessing"]
    model = config["model"]
    manifest_sha256 = canonical_json_sha256(manifest)
    network_sha256 = manifest["network"]["sha256"]
    phase_contract_sha256 = manifest["phase_contract"]["sha256"]
    generator_config_sha256 = manifest["generator_config_sha256"]
    return {
        "controller_family": "neighbor_phase_ddqn",
        "obs_schema_version": 2,
        "feature_order": list(FEATURES),
        "feature_dim": int(model["feature_dim"]),
        "hidden_size": int(model["hidden"]),
        "normalization": {
            "count_norm": float(preprocessing["count_norm"]),
            "capacity_norm": float(preprocessing["capacity_norm"]),
        },
        "action_contract": {
            "type": "phase_rows",
            "version": 1,
            "mask_type": "boolean_selectable_green_rows",
            "padding_actions_selectable": False,
        },
        "network_compatibility": {
            "network_sha256": network_sha256,
            "phase_contract_sha256": phase_contract_sha256,
            "generator_config_sha256": generator_config_sha256,
            "manifest_sha256": manifest_sha256,
        },
        # Flat aliases remain for readers of pre-release training artifacts.
        "hidden": int(model["hidden"]),
        "count_norm": float(preprocessing["count_norm"]),
        "capacity_norm": float(preprocessing["capacity_norm"]),
        "max_green": int(max_green),
        "phase_contract_schema_version": 1,
        "phase_contract_sha256": phase_contract_sha256,
        "network_sha256": network_sha256,
        "manifest_sha256": manifest_sha256,
        "generator_config_sha256": generator_config_sha256,
        "runtime": manifest["runtime"],
        "baseline_tuning_sha256": tuning["tuning_sha256"],
        "foundation_verification": verification,
    }


def _train_network_impl(env_factory, manifest, config, output_dir,
                        foundation_root, verification, run_start_time,
                        foundation_verification_seconds):
    """Train without opening the manifest's locked test split."""
    if manifest.get("protocol_version") != 2:
        raise ValueError("Hai Chau manifest protocol_version must be 2")
    if config.get("schema_version") != 2:
        raise ValueError("Hai Chau training config schema_version must be 2")
    train_cases = [case for case in manifest.get("cases", [])
                   if case.get("split") == "train"]
    validation_cases = [case for case in manifest.get("cases", [])
                        if case.get("split") == "validation"]
    required_regimes = set(("normal", "am_peak", "pm_peak"))
    for split_name, cases in (("train", train_cases),
                              ("validation", validation_cases)):
        regimes = set(case.get("scenario") for case in cases)
        if regimes != required_regimes:
            raise ValueError("%s cases must cover normal/am_peak/pm_peak" % split_name)

    run = config["run"]
    model_config = config["model"]
    optimizer = config["optimizer"]
    learning_seed = int(config["learning_seed"])
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    checkpoints_dir = os.path.join(output_dir, "checkpoints")
    if not os.path.isdir(checkpoints_dir):
        os.makedirs(checkpoints_dir)
    _write_json(os.path.join(output_dir, "status.json"), {
        "status": "partial", "reason": "run in progress"})
    manifest_sha256 = canonical_json_sha256(manifest)
    validation_case_hashes = {
        case["case_id"]: case.get("flow_sha256") for case in validation_cases}
    tuning_binding = {
        "manifest_sha256": manifest_sha256,
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime": manifest["runtime"],
        "validation_case_hashes": validation_case_hashes,
    }
    tuning_start = time.time()
    tuning = _tune_fixed_time(
        env_factory, validation_cases, int(run["horizon_seconds"]), config,
        tuning_binding)
    tuning_seconds = time.time() - tuning_start
    fixed_duration = tuning["selected"]["fixed_green_duration"]
    _write_json(os.path.join(output_dir, "baseline-tuning.json"), tuning)
    resolved = json.loads(json.dumps(config))
    resolved["manifest_protocol_version"] = manifest["protocol_version"]
    resolved["network_sha256"] = manifest["network"]["sha256"]
    resolved["manifest_sha256"] = manifest_sha256
    resolved["generator_config_sha256"] = manifest["generator_config_sha256"]
    resolved["runtime"] = manifest["runtime"]
    resolved["baseline_tuning_sha256"] = tuning["tuning_sha256"]
    _write_json(os.path.join(output_dir, "resolved-config.json"), resolved)
    _write_json(os.path.join(output_dir, "run-manifest.json"), {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "foundation_verification": verification,
        "code_commit": _git_sha(foundation_root),
        "learning_seed": learning_seed,
    })

    rng = np.random.RandomState(learning_seed)
    sampler = BalancedCaseSampler(train_cases, seed=learning_seed)
    network = None
    replay = None
    contract = None
    decisions = 0
    updates = 0
    simulated_seconds = 0.0
    episode_log = []
    validation_log = {}
    validation_seconds = 0.0
    training_start_time = time.time()

    for episode in range(int(run["episodes"])):
        episode_start = time.time()
        case = sampler.next_case()
        env = env_factory(case, int(run["horizon_seconds"]))
        try:
            observations = env.reset()
            first_agent = env.agent_ids[0]
            max_green, feature_dim = observations[first_agent].shape
            if network is None:
                if feature_dim != int(model_config["feature_dim"]):
                    raise ValueError("environment feature_dim differs from config")
                network = PhaseScoringDDQN(
                    feature_dim, hidden=int(model_config["hidden"]),
                    lr=float(model_config["lr"]), seed=learning_seed,
                    grad_clip=optimizer.get("grad_clip"),
                    huber_delta=optimizer.get("huber_delta", 1.0))
                replay = NetworkReplayBuffer(
                    int(optimizer["buffer_capacity"]), max_green, feature_dim,
                    seed=learning_seed)
                contract = _checkpoint_contract(
                    manifest, config, max_green, tuning, verification)
            elif observations[first_agent].shape != (contract["max_green"],
                                                       contract["feature_dim"]):
                raise ValueError("environment observation shape drifted across cases")
            expected_agents = manifest["network"].get("controlled_signals")
            if expected_agents is not None and len(env.agent_ids) != int(expected_agents):
                raise ValueError("environment controlled signal count mismatch")

            accumulators = {
                agent_id: NStepAccumulator(int(model_config.get("n_step", 1)),
                                           float(model_config["gamma"]))
                for agent_id in env.agent_ids}
            done = False
            losses = []
            rewards_log = []
            inference_seconds = 0.0
            info = {}
            while not done:
                masks = env.action_masks()
                epsilon = _epsilon(decisions, config["exploration"])
                actions = {}
                feature_batch = np.asarray(
                    [observations[agent_id] for agent_id in env.agent_ids])
                mask_batch = np.asarray(
                    [masks[agent_id] for agent_id in env.agent_ids])
                inference_start = time.time()
                greedy = np.argmax(
                    network.q_values(feature_batch, mask_batch), axis=1)
                inference_seconds += time.time() - inference_start
                for agent_index, agent_id in enumerate(env.agent_ids):
                    valid = np.flatnonzero(masks[agent_id])
                    if rng.rand() < epsilon:
                        actions[agent_id] = int(rng.choice(valid))
                    else:
                        actions[agent_id] = int(greedy[agent_index])
                next_observations, rewards, done, info = env.step(actions)
                next_masks = env.action_masks()
                for agent_id in env.agent_ids:
                    emitted = accumulators[agent_id].push(
                        observations[agent_id], actions[agent_id], rewards[agent_id],
                        next_observations[agent_id], 1.0 if done else 0.0,
                        next_masks[agent_id])
                    for transition in emitted:
                        replay.add(*(transition + (case["scenario"],)))
                observations = next_observations
                decisions += 1
                rewards_log.append(float(sum(rewards.values())) / len(rewards))
                train_start = int(run.get("train_start",
                                          optimizer["train_start"]))
                if len(replay) >= train_start:
                    batch = replay.sample(int(optimizer["batch_size"]))
                    loss = network.train_step(
                        batch["features"], batch["actions"], batch["rewards"],
                        batch["next_features"], batch["dones"],
                        batch["next_masks"],
                        gamma=float(model_config["gamma"])
                        ** int(model_config.get("n_step", 1)))
                    losses.append(loss)
                    updates += 1
                    if updates % int(optimizer["target_sync"]) == 0:
                        network.sync_target()
            _assert_rollout_complete(
                info, int(run["horizon_seconds"]),
                "training episode %d" % (episode + 1))
            simulated_seconds += float(info.get("step", run["horizon_seconds"]))
            episode_log.append({
                "episode": episode + 1,
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "demand_seed": case.get("demand_seed"),
                "sim_seed": case.get("sim_seed"),
                "flow_sha256": case.get("flow_sha256"),
                "flow_path": case.get("flow_path"),
                "route_family_hashes": case.get("route_family_hashes"),
                "agent_count": len(env.agent_ids),
                "simulated_seconds": float(info.get("step", 0)),
                "mean_reward": (float(np.mean(rewards_log)) if rewards_log else 0.0),
                "mean_loss": (float(np.mean(losses)) if losses else None),
                "phase_switches": info.get("phase_switches"),
                "queue_integral_vehicle_seconds": info.get(
                    "queue_integral_vehicle_seconds"),
                "queue_integral_vehicle_hours": (
                    float(info["queue_integral_vehicle_seconds"]) / 3600.0
                    if info.get("queue_integral_vehicle_seconds") is not None
                    else None),
                "total_queue": info.get("total_queue"),
                "arrived": info.get("arrived"),
                "active_vehicles": info.get("active_vehicles"),
                "pending": info.get("active_vehicles"),
                "completion_rate": info.get("completion_rate"),
                "average_travel_time": info.get("average_travel_time"),
                "arrived_throughput_vehicles_per_hour": (
                    float(info["arrived"]) * 3600.0 / float(info["step"])
                    if info.get("arrived") is not None and info.get("step")
                    else None),
                "max_red_seconds": info.get("max_red_seconds"),
                "intergreen_vehicle_seconds": info.get(
                    "intergreen_vehicle_seconds"),
                "wall_time_seconds": time.time() - episode_start,
                "inference_seconds": inference_seconds,
            })
            _write_json(os.path.join(output_dir, "train-log.json"), episode_log)
        finally:
            _close(env)

        if (episode + 1) % int(run["eval_every"]) == 0:
            checkpoint_id = "step-%d" % (episode + 1)
            checkpoint_dir = os.path.join(checkpoints_dir, checkpoint_id)
            network.save_bundle(checkpoint_dir, contract)
            validation_start = time.time()
            rows = _validation_rows(
                env_factory, validation_cases, int(run["horizon_seconds"]),
                network, config, fixed_duration)
            validation_seconds += time.time() - validation_start
            score = score_validation(rows)
            score["training_step"] = episode + 1
            validation_log[checkpoint_id] = {"rows": rows, "score": score}
            _write_json(os.path.join(output_dir, "validation.json"), validation_log)

    if network is None:
        raise ValueError("training produced no episodes")
    scores = {checkpoint_id: value["score"]
              for checkpoint_id, value in validation_log.items()}
    try:
        selected = choose_checkpoint(scores)
        selection_status = "eligible"
    except ValueError:
        selected = choose_reporting_checkpoint(scores)
        selection_status = "ineligible_negative_result"
    final_network = PhaseScoringDDQN.load_bundle(
        os.path.join(checkpoints_dir, selected), contract)
    final_checkpoint = os.path.join(output_dir, "checkpoint")
    final_network.save_bundle(final_checkpoint, contract)
    reloaded = PhaseScoringDDQN.load_bundle(final_checkpoint, contract)

    reload_verification = None
    if validation_cases:
        env = env_factory(validation_cases[0], int(run["horizon_seconds"]))
        try:
            reload_info = _rollout(
                env, reloaded,
                action_interval=config.get("simulation", {}).get(
                    "action_interval", 10))
            reload_verification = {
                "case_id": validation_cases[0]["case_id"],
                "completed_steps": reload_info.get("step"),
                "queue_integral_vehicle_seconds": reload_info.get(
                    "queue_integral_vehicle_seconds"),
            }
            _assert_rollout_complete(
                reload_info, int(run["horizon_seconds"]),
                "checkpoint reload")
        finally:
            _close(env)

    training_and_validation_seconds = time.time() - training_start_time
    coverage = replay.coverage()
    summary = {
        "episode_regimes": [row["scenario"] for row in episode_log],
        "episode_agent_counts": [row["agent_count"] for row in episode_log],
        "decisions": decisions,
        "updates": updates,
        "simulated_seconds": simulated_seconds,
        "wall_time_seconds": None,
        "measured_scope": (
            "foundation_verification_through_artifact_verification"),
        "foundation_verification_wall_time_seconds": (
            foundation_verification_seconds),
        "baseline_tuning_wall_time_seconds": tuning_seconds,
        "training_and_validation_wall_time_seconds": (
            training_and_validation_seconds),
        "simulated_seconds_per_second": (
            None),
        "updates_per_second": None,
        "validation_wall_time_seconds": validation_seconds,
        "selected_checkpoint": selected,
        "selection_status": selection_status,
        "checkpoint_reload": reload_verification,
    }
    if run.get("require_optimizer_updates") and updates <= 0:
        raise ValueError("run requires at least one optimizer update")
    _write_json(os.path.join(output_dir, "train-log.json"), episode_log)
    _write_json(os.path.join(output_dir, "validation.json"), validation_log)
    _write_json(os.path.join(output_dir, "replay-coverage.json"), coverage)
    _write_json(os.path.join(output_dir, "selection.json"), {
        "status": selection_status,
        "selected_checkpoint": selected,
        "eligible_for_test_evaluation": selection_status == "eligible",
        "score": scores[selected],
    })
    _write_json(os.path.join(output_dir, "summary.json"), summary)
    artifact_paths = [
        "baseline-tuning.json", "resolved-config.json", "run-manifest.json",
        "train-log.json", "validation.json", "replay-coverage.json",
        "selection.json", "summary.json", "checkpoint/contract.json",
        "checkpoint/weights.npz",
    ]
    artifact_hashes = {}
    for relative_path in artifact_paths:
        artifact_path = os.path.join(output_dir, relative_path)
        if not os.path.isfile(artifact_path):
            raise ValueError("required artifact missing: %s" % relative_path)
        artifact_hashes[relative_path] = _file_sha256(artifact_path)
    wall_time = time.time() - run_start_time
    summary["wall_time_seconds"] = wall_time
    summary["simulated_seconds_per_second"] = (
        simulated_seconds / wall_time if wall_time > 0 else None)
    summary["updates_per_second"] = (
        updates / wall_time if wall_time > 0 else None)
    _write_json(os.path.join(output_dir, "summary.json"), summary)
    artifact_hashes["summary.json"] = _file_sha256(
        os.path.join(output_dir, "summary.json"))
    _write_json(os.path.join(output_dir, "status.json"), {
        "status": ("complete" if selection_status == "eligible"
                   else "ineligible"),
        "eligible_for_test_evaluation": selection_status == "eligible",
        "artifact_sha256": artifact_hashes,
    })
    return summary


def train_network(env_factory, manifest, config, output_dir,
                  foundation_root=None, foundation_verifier=None,
                  run_started_at=None):
    """Verify the immutable foundation, then train without opening test cases."""
    run_start_time = (time.time() if run_started_at is None
                      else float(run_started_at))
    root = os.path.abspath(foundation_root or os.getcwd())
    verifier = foundation_verifier or _default_foundation_verifier
    verification_start = time.time()
    verification = _verify_training_foundation(root, manifest, verifier)
    verification_seconds = time.time() - verification_start
    try:
        return _train_network_impl(
            env_factory, manifest, config, output_dir, root, verification,
            run_start_time, verification_seconds)
    except Exception as exc:
        absolute_output = os.path.abspath(output_dir)
        if os.path.isdir(absolute_output):
            _write_json(os.path.join(absolute_output, "status.json"), {
                "status": "failed", "error_type": type(exc).__name__,
                "error": str(exc)})
        raise
