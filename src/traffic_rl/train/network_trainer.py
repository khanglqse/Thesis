"""Balanced multi-case training for the neighbor-aware phase DDQN."""
import json
import os
import time

import numpy as np

from traffic_rl.agents.dqn import NStepAccumulator
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.checkpoint_selection import choose_checkpoint, score_validation
from traffic_rl.sim.phase_encoder import FEATURES
from traffic_rl.train.case_sampler import BalancedCaseSampler
from traffic_rl.train.network_replay import NetworkReplayBuffer


def _write_json(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
    os.replace(temporary, path)


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


def _validation_rows(env_factory, cases, horizon_seconds, net, config):
    rows = []
    fixed_duration = config.get("baseline", {}).get("fixed_green_duration", 40)
    action_interval = config.get("simulation", {}).get("action_interval", 10)
    for case in cases:
        candidate_env = env_factory(case, horizon_seconds)
        try:
            candidate = _rollout(candidate_env, net,
                                 action_interval=action_interval)
        finally:
            _close(candidate_env)
        baseline_env = env_factory(case, horizon_seconds)
        try:
            baseline = _rollout(
                baseline_env, net, fixed_green_duration=fixed_duration,
                action_interval=action_interval)
        finally:
            _close(baseline_env)
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


def _checkpoint_contract(manifest, config, max_green):
    preprocessing = manifest["preprocessing"]
    model = config["model"]
    return {
        "obs_schema_version": 2,
        "feature_order": list(FEATURES),
        "feature_dim": int(model["feature_dim"]),
        "hidden": int(model["hidden"]),
        "count_norm": float(preprocessing["count_norm"]),
        "capacity_norm": float(preprocessing["capacity_norm"]),
        "max_green": int(max_green),
        "action_contract": "phase_rows_with_boolean_mask_v1",
        "network_sha256": manifest["network"]["sha256"],
    }


def train_network(env_factory, manifest, config, output_dir):
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
    resolved = json.loads(json.dumps(config))
    resolved["manifest_protocol_version"] = manifest["protocol_version"]
    resolved["network_sha256"] = manifest["network"]["sha256"]
    _write_json(os.path.join(output_dir, "resolved-config.json"), resolved)

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
    start_time = time.time()

    for episode in range(int(run["episodes"])):
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
                contract = _checkpoint_contract(manifest, config, max_green)
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
            info = {}
            while not done:
                masks = env.action_masks()
                epsilon = _epsilon(decisions, config["exploration"])
                actions = {}
                feature_batch = np.asarray(
                    [observations[agent_id] for agent_id in env.agent_ids])
                mask_batch = np.asarray(
                    [masks[agent_id] for agent_id in env.agent_ids])
                greedy = np.argmax(
                    network.q_values(feature_batch, mask_batch), axis=1)
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
                if len(replay) >= int(optimizer["train_start"]):
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
            simulated_seconds += float(info.get("step", run["horizon_seconds"]))
            episode_log.append({
                "episode": episode + 1,
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "agent_count": len(env.agent_ids),
                "simulated_seconds": float(info.get("step", 0)),
                "mean_reward": (float(np.mean(rewards_log)) if rewards_log else 0.0),
                "mean_loss": (float(np.mean(losses)) if losses else None),
                "phase_switches": info.get("phase_switches"),
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
                network, config)
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
    except ValueError:
        selected = None
    final_network = (PhaseScoringDDQN.load_bundle(
        os.path.join(checkpoints_dir, selected), contract)
                     if selected is not None else network)
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
        finally:
            _close(env)

    wall_time = time.time() - start_time
    coverage = replay.coverage()
    summary = {
        "episode_regimes": [row["scenario"] for row in episode_log],
        "episode_agent_counts": [row["agent_count"] for row in episode_log],
        "decisions": decisions,
        "updates": updates,
        "simulated_seconds": simulated_seconds,
        "wall_time_seconds": wall_time,
        "simulated_seconds_per_second": (
            simulated_seconds / wall_time if wall_time > 0 else None),
        "updates_per_second": updates / wall_time if wall_time > 0 else None,
        "validation_wall_time_seconds": validation_seconds,
        "selected_checkpoint": selected,
        "checkpoint_reload": reload_verification,
    }
    _write_json(os.path.join(output_dir, "train-log.json"), episode_log)
    _write_json(os.path.join(output_dir, "validation.json"), validation_log)
    _write_json(os.path.join(output_dir, "replay-coverage.json"), coverage)
    _write_json(os.path.join(output_dir, "summary.json"), summary)
    return summary
