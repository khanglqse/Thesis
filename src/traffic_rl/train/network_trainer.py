"""Balanced multi-case training for the neighbor-aware phase DDQN."""
import json
import hashlib
import importlib.util
import math
import os
import subprocess
import time

import numpy as np

from traffic_rl.agents.dqn import NStepAccumulator, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, choose_checkpoint,
    choose_reporting_checkpoint, score_validation)
from traffic_rl.sim.phase_encoder import FEATURES
from traffic_rl.train.case_sampler import BalancedCaseSampler
from traffic_rl.train.network_replay import (
    NetworkReplayBuffer, VectorNetworkReplayBuffer)


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


def _linear_probability(decisions, total_decisions, start, end):
    fraction = min(1.0, float(decisions) / max(1, int(total_decisions)))
    return float(start) + fraction * (float(end) - float(start))


def _validated_behavior_prior(config):
    prior = config.get("behavior_prior")
    if prior is None:
        return None
    if prior.get("type") != "fixed_time_behavior_cloning":
        raise ValueError("behavior prior type must be fixed_time_behavior_cloning")
    if int(prior.get("bc_epochs", 0)) <= 0:
        raise ValueError("behavior prior bc_epochs must be positive")
    fields = ("reference_probability_start", "reference_probability_end",
              "random_probability_start", "random_probability_end")
    for field in fields:
        value = float(prior.get(field, -1.0))
        if not 0.0 <= value <= 1.0:
            raise ValueError("behavior prior probabilities must be within [0, 1]")
    if (float(prior["reference_probability_start"])
            + float(prior["random_probability_start"]) > 1.0
            or float(prior["reference_probability_end"])
            + float(prior["random_probability_end"]) > 1.0):
        raise ValueError("behavior prior reference and random probabilities exceed one")
    minimum = float(prior.get(
        "minimum_validation_reference_disagreement_rate", -1.0))
    if not 0.0 <= minimum <= 1.0:
        raise ValueError(
            "behavior prior reference disagreement rate must be within [0, 1]")
    return prior


def _behavior_clone_pretrain(env_factory, train_cases, horizon_seconds, network,
                             fixed_duration, action_interval, prior):
    losses = []
    case_rows = []
    for case in train_cases:
        case_rows.append({
            "case_id": case["case_id"], "scenario": case["scenario"],
            "flow_sha256": case.get("flow_sha256"), "decisions": 0,
            "labels": 0,
        })
    by_case = dict((row["case_id"], row) for row in case_rows)
    for _ in range(int(prior["bc_epochs"])):
        for case in train_cases:
            env = env_factory(case, horizon_seconds)
            try:
                observations = env.reset()
                teacher = FixedTimeController(
                    env.num_actions, fixed_duration, action_interval)
                done = False
                info = {}
                while not done:
                    masks = env.action_masks()
                    reference = teacher.act({"action_masks": masks})
                    features = np.asarray(
                        [observations[agent_id] for agent_id in env.agent_ids])
                    mask_batch = np.asarray(
                        [masks[agent_id] for agent_id in env.agent_ids])
                    labels = np.asarray(
                        [reference[agent_id] for agent_id in env.agent_ids],
                        dtype=np.int64)
                    losses.append(float(network.behavior_clone_step(
                        features, labels, mask_batch)))
                    observations, _, done, info = env.step(reference)
                    by_case[case["case_id"]]["decisions"] += 1
                    by_case[case["case_id"]]["labels"] += len(env.agent_ids)
                _assert_rollout_complete(
                    info, horizon_seconds,
                    "behavior cloning %s" % case["case_id"])
            finally:
                _close(env)
    return {
        "schema_version": 1,
        "teacher": "validation_tuned_fixed",
        "fixed_green_duration": int(fixed_duration),
        "bc_epochs": int(prior["bc_epochs"]),
        "updates": len(losses),
        "labels": sum(row["labels"] for row in case_rows),
        "mean_loss": float(np.mean(losses)) if losses else None,
        "source_split": "train",
        "source_case_ids": [row["case_id"] for row in case_rows],
        "train_cases": case_rows,
    }


def _close(env):
    if hasattr(env, "close"):
        env.close()


def _assert_rollout_complete(info, horizon_seconds, label):
    if int(info.get("step", -1)) != int(horizon_seconds):
        raise ValueError("%s did not complete required horizon" % label)
    queue_integral = info.get("queue_integral_vehicle_seconds")
    if queue_integral is None or not np.isfinite(float(queue_integral)):
        raise ValueError("%s has invalid queue integral" % label)


def _rollout(env, net, fixed_green_duration=None, action_interval=10,
             audit_fixed_green_duration=None):
    observations = env.reset()
    done = False
    info = {}
    fixed_controller = (None if fixed_green_duration is None else
                        FixedTimeController(env.num_actions,
                                            fixed_green_duration,
                                            action_interval))
    audit_controller = (None if audit_fixed_green_duration is None else
                        FixedTimeController(env.num_actions,
                                            audit_fixed_green_duration,
                                            action_interval))
    audit_total = 0
    audit_disagreements = 0
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
            if audit_controller is not None:
                reference = audit_controller.act({"action_masks": masks})
                audit_total += len(env.agent_ids)
                audit_disagreements += sum(
                    actions[agent_id] != reference[agent_id]
                    for agent_id in env.agent_ids)
        else:
            actions = fixed_controller.act({"action_masks": masks})
        observations, _, done, info = env.step(actions)
    if audit_controller is not None:
        info = dict(info)
        info["policy_audit"] = {
            "evaluation_policy": "raw_ddqn_greedy",
            "reference": "validation_tuned_fixed",
            "eligible_decisions": audit_total,
            "reference_disagreements": audit_disagreements,
            "reference_disagreement_rate": (
                float(audit_disagreements) / audit_total
                if audit_total else 0.0),
        }
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
            insertion_rate = info.get("insertion_rate")
            if (insertion_rate is None
                    or not math.isfinite(float(insertion_rate))
                    or not 0.0 <= float(insertion_rate) <= 1.0):
                raise ValueError("fixed-time tuning insertion rate is invalid")
            rows.append({
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "queue_integral_vehicle_seconds": float(
                    info["queue_integral_vehicle_seconds"]),
                "completion_rate": info.get("completion_rate"),
                "insertion_rate": float(insertion_rate),
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


def _tuning_binding(manifest, validation_cases, horizon_seconds, config):
    return {
        "manifest_sha256": canonical_json_sha256(manifest),
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime": manifest["runtime"],
        "validation_case_hashes": {
            case["case_id"]: case.get("flow_sha256")
            for case in validation_cases},
        "horizon_seconds": int(horizon_seconds),
        "action_interval": int(config.get("simulation", {}).get(
            "action_interval", 10)),
        "queue_objective": {
            "schema_version": 2,
            "network_queue": "per_step_waiting",
            "entry_pending": "due_not_inserted",
            "future_departures": "unreleased_excluded",
        },
    }


def _search_space(config):
    baseline = config.get("baseline", {})
    if baseline.get("controller") != "validation_tuned_fixed":
        raise ValueError("baseline controller must be validation_tuned_fixed")
    durations = baseline.get("search_green_durations", [])
    if not durations or any(int(value) <= 0 for value in durations):
        raise ValueError("baseline search_green_durations must be positive")
    return {"fixed_green_duration": sorted(set(int(value) for value in durations))}


def _load_precomputed_tuning(artifact):
    if isinstance(artifact, os.PathLike):
        artifact = os.fspath(artifact)
    if isinstance(artifact, str):
        if not os.path.isfile(artifact):
            raise ValueError("precomputed baseline tuning artifact is missing")
        try:
            with open(artifact, "r") as source:
                tuning = json.load(source)
        except (IOError, ValueError) as exc:
            raise ValueError("precomputed baseline tuning artifact is invalid: %s" % exc)
        return tuning, {
            "source_kind": "file",
            "source_path": artifact,
            "source_artifact_sha256": _file_sha256(artifact),
        }
    if isinstance(artifact, dict):
        return json.loads(json.dumps(artifact)), {
            "source_kind": "in_memory",
            "source_artifact_sha256": canonical_json_sha256(artifact),
        }
    raise ValueError("precomputed baseline tuning artifact must be a JSON file or object")


def _validate_precomputed_tuning(tuning, binding, config, validation_cases):
    if not isinstance(tuning, dict):
        raise ValueError("precomputed baseline tuning artifact must be an object")
    claimed_sha = tuning.get("tuning_sha256")
    canonical = dict((key, value) for key, value in tuning.items()
                     if key != "tuning_sha256")
    if claimed_sha != canonical_json_sha256(canonical):
        raise ValueError("precomputed baseline tuning hash drift")
    if tuning.get("schema_version") != 1 \
            or tuning.get("method") != "validation_grid_search":
        raise ValueError("precomputed baseline tuning schema is invalid")
    artifact_binding = tuning.get("binding")
    if not isinstance(artifact_binding, dict):
        raise ValueError("precomputed baseline tuning binding is invalid")
    for field in ("manifest_sha256", "network_sha256", "runtime",
                  "validation_case_hashes", "horizon_seconds",
                  "action_interval", "queue_objective"):
        if artifact_binding.get(field) != binding[field]:
            raise ValueError("precomputed baseline tuning %s drift" % field)
    if artifact_binding != binding:
        raise ValueError("precomputed baseline tuning binding drift")
    expected_search = _search_space(config)
    if tuning.get("search_space") != expected_search:
        raise ValueError("precomputed baseline tuning search space drift")
    candidates = tuning.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("precomputed baseline tuning candidates are missing")
    expected_durations = expected_search["fixed_green_duration"]
    if [candidate.get("fixed_green_duration") if isinstance(candidate, dict)
            else None for candidate in candidates] != expected_durations:
        raise ValueError("precomputed baseline tuning candidates drift")
    expected_cases = [(case["case_id"], case["scenario"])
                      for case in validation_cases]
    ranked = []
    for candidate in candidates:
        rows = candidate.get("rows")
        if not isinstance(rows, list) or [
                (row.get("case_id"), row.get("scenario"))
                if isinstance(row, dict) else None for row in rows] != expected_cases:
            raise ValueError("precomputed baseline tuning validation cases drift")
        queues = []
        for row in rows:
            try:
                queue = float(row["queue_integral_vehicle_seconds"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("precomputed baseline tuning queue is invalid")
            if not math.isfinite(queue) or queue <= 0:
                raise ValueError("precomputed baseline tuning queue is invalid")
            completion = row.get("completion_rate")
            if completion is not None and not math.isfinite(float(completion)):
                raise ValueError("precomputed baseline tuning completion is invalid")
            insertion = row.get("insertion_rate")
            if (insertion is None or not math.isfinite(float(insertion))
                    or not 0.0 <= float(insertion) <= 1.0):
                raise ValueError(
                    "precomputed baseline tuning insertion rate is invalid")
            queues.append(queue)
        mean_queue = sum(queues) / len(queues)
        try:
            reported_mean = float(candidate["mean_queue_integral_vehicle_seconds"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("precomputed baseline tuning mean is invalid")
        if not math.isfinite(reported_mean) or abs(reported_mean - mean_queue) > 1e-9:
            raise ValueError("precomputed baseline tuning mean drift")
        ranked.append((mean_queue, int(candidate["fixed_green_duration"])))
    selected = tuning.get("selected", {}).get("fixed_green_duration") \
        if isinstance(tuning.get("selected"), dict) else None
    if selected != min(ranked)[1]:
        raise ValueError("precomputed baseline tuning selection drift")


def _selected_baseline_rows(tuning, validation_cases):
    duration = tuning["selected"]["fixed_green_duration"]
    candidate = next(item for item in tuning["candidates"]
                     if item["fixed_green_duration"] == duration)
    rows = {}
    for case, baseline in zip(validation_cases, candidate["rows"]):
        rows[case["case_id"]] = baseline
    return rows


def _validation_rows(env_factory, cases, horizon_seconds, net, config,
                     fixed_duration, precomputed_baseline_rows=None):
    rows = []
    action_interval = config.get("simulation", {}).get("action_interval", 10)
    for case in cases:
        candidate_env = env_factory(case, horizon_seconds)
        try:
            candidate = _rollout(
                candidate_env, net, action_interval=action_interval,
                audit_fixed_green_duration=(
                    fixed_duration if config.get("behavior_prior") else None))
        finally:
            _close(candidate_env)
        _assert_rollout_complete(
            candidate, horizon_seconds, "candidate validation %s" % case["case_id"])
        if precomputed_baseline_rows is None:
            baseline_env = env_factory(case, horizon_seconds)
            try:
                baseline = _rollout(
                    baseline_env, net, fixed_green_duration=fixed_duration,
                    action_interval=action_interval)
            finally:
                _close(baseline_env)
            _assert_rollout_complete(
                baseline, horizon_seconds,
                "baseline validation %s" % case["case_id"])
            baseline_queue = float(baseline["queue_integral_vehicle_seconds"])
            baseline_completion = baseline.get("completion_rate")
            baseline_insertion = baseline.get("insertion_rate")
            fresh_baseline = True
            baseline_source = None
        else:
            baseline = precomputed_baseline_rows[case["case_id"]]
            baseline_queue = float(baseline["queue_integral_vehicle_seconds"])
            baseline_completion = baseline.get("completion_rate")
            baseline_insertion = baseline.get("insertion_rate")
            fresh_baseline = False
            baseline_source = "precomputed_tuning"
        row = {
            "case_id": case["case_id"],
            "scenario": case["scenario"],
            "demand_seed": case.get("demand_seed"),
            "sim_seed": case.get("sim_seed"),
            "candidate_queue": float(candidate["queue_integral_vehicle_seconds"]),
            "baseline_queue": baseline_queue,
            "fresh_candidate": True,
            "fresh_baseline": fresh_baseline,
        }
        if baseline_source is not None:
            row["baseline_source"] = baseline_source
        if candidate.get("completion_rate") is not None \
                and baseline_completion is not None:
            row["candidate_completion"] = float(candidate["completion_rate"])
            row["baseline_completion"] = float(baseline_completion)
        if candidate.get("insertion_rate") is not None \
                and baseline_insertion is not None:
            row["candidate_insertion"] = float(candidate["insertion_rate"])
            row["baseline_insertion"] = float(baseline_insertion)
        if config.get("behavior_prior"):
            row["policy_audit"] = candidate["policy_audit"]
        rows.append(row)
    return rows


def _checkpoint_contract(manifest, config, max_green, tuning, verification,
                         controller_family="neighbor_phase_ddqn",
                         feature_order=None,
                         baseline_tuning_provenance=None):
    preprocessing = manifest["preprocessing"]
    model = config["model"]
    manifest_sha256 = canonical_json_sha256(manifest)
    network_sha256 = manifest["network"]["sha256"]
    phase_contract_sha256 = manifest["phase_contract"]["sha256"]
    generator_config_sha256 = manifest["generator_config_sha256"]
    order = list(FEATURES) if feature_order is None else list(feature_order)
    action_contract = ({
        "type": "phase_rows",
        "version": 1,
        "mask_type": "boolean_selectable_green_rows",
        "padding_actions_selectable": False,
    } if controller_family == "neighbor_phase_ddqn" else {
        "type": "fixed_vector",
        "version": 1,
        "mask_type": "boolean_phase_index",
        "padding_actions_selectable": False,
        "n_actions": int(max_green),
    })
    contract = {
        "controller_family": controller_family,
        "obs_schema_version": 2,
        "feature_order": order,
        "feature_dim": len(order),
        "hidden_size": int(model["hidden"]),
        "normalization": {
            "count_norm": float(preprocessing["count_norm"]),
            "capacity_norm": float(preprocessing["capacity_norm"]),
        },
        "action_contract": action_contract,
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
        "checkpoint_eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "training_objective": {
            "reward": json.loads(json.dumps(config["reward"])),
            "temporal_aggregation": "mean_over_simulator_steps_in_action_interval",
        },
    }
    if config.get("behavior_prior") is not None:
        contract["behavior_prior"] = json.loads(json.dumps(
            config["behavior_prior"]))
    if baseline_tuning_provenance is not None:
        contract["baseline_tuning_provenance_sha256"] = (
            baseline_tuning_provenance["provenance_sha256"])
        contract["baseline_tuning_artifact_sha256"] = (
            baseline_tuning_provenance["copied_artifact_sha256"])
    return contract


def _train_network_impl(env_factory, manifest, config, output_dir,
                        foundation_root, verification, run_start_time,
                        foundation_verification_seconds, controller_family,
                        baseline_tuning_artifact):
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
    horizon_seconds = int(run["horizon_seconds"])
    manifest_sha256 = canonical_json_sha256(manifest)
    tuning_binding = _tuning_binding(
        manifest, validation_cases, horizon_seconds, config)
    precomputed_provenance = None
    if baseline_tuning_artifact is not None:
        tuning, source_provenance = _load_precomputed_tuning(
            baseline_tuning_artifact)
        _validate_precomputed_tuning(
            tuning, tuning_binding, config, validation_cases)
    else:
        tuning = None
        source_provenance = None
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    checkpoints_dir = os.path.join(output_dir, "checkpoints")
    if not os.path.isdir(checkpoints_dir):
        os.makedirs(checkpoints_dir)
    _write_json(os.path.join(output_dir, "status.json"), {
        "status": "partial", "reason": "run in progress"})
    tuning_start = time.time()
    if tuning is None:
        tuning = _tune_fixed_time(
            env_factory, validation_cases, horizon_seconds, config,
            tuning_binding)
        tuning_seconds = time.time() - tuning_start
        precomputed_baseline_rows = None
    else:
        tuning_seconds = 0.0
        precomputed_baseline_rows = _selected_baseline_rows(
            tuning, validation_cases)
    fixed_duration = tuning["selected"]["fixed_green_duration"]
    tuning_path = os.path.join(output_dir, "baseline-tuning.json")
    _write_json(tuning_path, tuning)
    if source_provenance is not None:
        precomputed_provenance = dict(source_provenance)
        precomputed_provenance.update({
            "schema_version": 1,
            "strategy": "precomputed_baseline_tuning",
            "copied_artifact_path": "baseline-tuning.json",
            "copied_artifact_sha256": _file_sha256(tuning_path),
            "tuning_sha256": tuning["tuning_sha256"],
        })
        provenance_path = os.path.join(
            output_dir, "baseline-tuning-provenance.json")
        _write_json(provenance_path, precomputed_provenance)
        precomputed_provenance["provenance_path"] = (
            "baseline-tuning-provenance.json")
        precomputed_provenance["provenance_sha256"] = _file_sha256(provenance_path)
    resolved = json.loads(json.dumps(config))
    resolved["manifest_protocol_version"] = manifest["protocol_version"]
    resolved["network_sha256"] = manifest["network"]["sha256"]
    resolved["manifest_sha256"] = manifest_sha256
    resolved["generator_config_sha256"] = manifest["generator_config_sha256"]
    resolved["runtime"] = manifest["runtime"]
    resolved["baseline_tuning_sha256"] = tuning["tuning_sha256"]
    if precomputed_provenance is not None:
        resolved["baseline_tuning"] = {
            "mode": "precomputed",
            "copied_artifact_sha256": precomputed_provenance[
                "copied_artifact_sha256"],
            "provenance_sha256": precomputed_provenance["provenance_sha256"],
        }
    _write_json(os.path.join(output_dir, "resolved-config.json"), resolved)
    run_manifest = {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "foundation_verification": verification,
        "code_commit": _git_sha(foundation_root),
        "controller_id": controller_family,
        "mode": config.get("mode"),
        "learning_seed": learning_seed,
    }
    if precomputed_provenance is not None:
        run_manifest["baseline_tuning"] = {
            "mode": "precomputed",
            "tuning_sha256": tuning["tuning_sha256"],
            "copied_artifact_path": "baseline-tuning.json",
            "copied_artifact_sha256": precomputed_provenance[
                "copied_artifact_sha256"],
            "provenance_path": precomputed_provenance["provenance_path"],
            "provenance_sha256": precomputed_provenance["provenance_sha256"],
        }
    _write_json(os.path.join(output_dir, "run-manifest.json"), run_manifest)

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
    behavior_prior = _validated_behavior_prior(config)
    behavior_pretraining = None
    training_policy_audit = {
        "eligible_decisions": 0,
        "reference_actions_executed": 0,
        "random_actions_executed": 0,
        "learned_actions_executed": 0,
        "learned_reference_disagreements": 0,
        "executed_interventions": 0,
    }
    action_interval = int(config.get("simulation", {}).get(
        "action_interval", 10))
    total_online_decisions = (int(run["episodes"])
                              * int(math.ceil(float(horizon_seconds)
                                              / action_interval)))
    training_start_time = time.time()

    for episode in range(int(run["episodes"])):
        episode_start = time.time()
        case = sampler.next_case()
        env = env_factory(case, int(run["horizon_seconds"]))
        try:
            observations = env.reset()
            first_agent = env.agent_ids[0]
            observation_shape = observations[first_agent].shape
            max_green = len(env.action_masks()[first_agent])
            if controller_family == "neighbor_phase_ddqn":
                if len(observation_shape) != 2:
                    raise ValueError("neighbor observation must be phase rows")
                observed_max_green, feature_dim = observation_shape
                if observed_max_green != max_green:
                    raise ValueError("neighbor observation/action dimensions differ")
            else:
                if controller_family != "shared_ddqn_legacy" \
                        or len(observation_shape) != 1:
                    raise ValueError("legacy observation must be a flat vector")
                feature_dim = observation_shape[0]
            if network is None:
                if (controller_family == "neighbor_phase_ddqn"
                        and feature_dim != int(model_config["feature_dim"])):
                    raise ValueError("environment feature_dim differs from config")
                if controller_family == "neighbor_phase_ddqn":
                    network = PhaseScoringDDQN(
                        feature_dim, hidden=int(model_config["hidden"]),
                        lr=float(model_config["lr"]), seed=learning_seed,
                        grad_clip=optimizer.get("grad_clip"),
                        huber_delta=optimizer.get("huber_delta", 1.0))
                    replay = NetworkReplayBuffer(
                        int(optimizer["buffer_capacity"]), max_green, feature_dim,
                        seed=learning_seed)
                    feature_order = list(FEATURES)
                else:
                    network = SharedDQN(
                        feature_dim, max_green, hidden=int(model_config["hidden"]),
                        lr=float(model_config["lr"]), seed=learning_seed,
                        grad_clip=optimizer.get("grad_clip"),
                        huber_delta=optimizer.get("huber_delta", 1.0), dueling=True)
                    replay = VectorNetworkReplayBuffer(
                        int(optimizer["buffer_capacity"]), feature_dim, max_green,
                        seed=learning_seed)
                    feature_order = getattr(env.encoder, "feature_order", None)
                    if not feature_order or len(feature_order) != feature_dim:
                        raise ValueError("legacy encoder feature order is missing")
                contract = _checkpoint_contract(
                    manifest, config, max_green, tuning, verification,
                    controller_family=controller_family,
                    feature_order=feature_order,
                    baseline_tuning_provenance=precomputed_provenance)
                if behavior_prior is not None:
                    if controller_family != "neighbor_phase_ddqn":
                        raise ValueError(
                            "behavior prior requires neighbor_phase_ddqn")
                    behavior_pretraining = _behavior_clone_pretrain(
                        env_factory, train_cases, horizon_seconds, network,
                        fixed_duration, action_interval, behavior_prior)
                    network.sync_target()
                    _write_json(os.path.join(
                        output_dir, "behavior-prior.json"),
                        behavior_pretraining)
            elif observations[first_agent].shape != (
                    ((contract["max_green"], contract["feature_dim"])
                     if controller_family == "neighbor_phase_ddqn"
                     else (contract["feature_dim"],))):
                raise ValueError("environment observation shape drifted across cases")
            expected_agents = manifest["network"].get("controlled_signals")
            if expected_agents is not None and len(env.agent_ids) != int(expected_agents):
                raise ValueError("environment controlled signal count mismatch")

            accumulators = {
                agent_id: NStepAccumulator(int(model_config.get("n_step", 1)),
                                           float(model_config["gamma"]))
                for agent_id in env.agent_ids}
            reference_controller = (None if behavior_prior is None else
                                    FixedTimeController(
                                        env.num_actions, fixed_duration,
                                        action_interval))
            done = False
            losses = []
            rewards_log = []
            inference_seconds = 0.0
            info = {}
            while not done:
                masks = env.action_masks()
                actions = {}
                feature_batch = np.asarray(
                    [observations[agent_id] for agent_id in env.agent_ids])
                mask_batch = np.asarray(
                    [masks[agent_id] for agent_id in env.agent_ids])
                inference_start = time.time()
                greedy = np.argmax(
                    network.q_values(feature_batch, mask_batch), axis=1)
                inference_seconds += time.time() - inference_start
                if behavior_prior is None:
                    epsilon = _epsilon(decisions, config["exploration"])
                    for agent_index, agent_id in enumerate(env.agent_ids):
                        valid = np.flatnonzero(masks[agent_id])
                        if rng.rand() < epsilon:
                            actions[agent_id] = int(rng.choice(valid))
                        else:
                            actions[agent_id] = int(greedy[agent_index])
                else:
                    reference = reference_controller.act(
                        {"action_masks": masks})
                    p_reference = _linear_probability(
                        decisions, total_online_decisions,
                        behavior_prior["reference_probability_start"],
                        behavior_prior["reference_probability_end"])
                    p_random = _linear_probability(
                        decisions, total_online_decisions,
                        behavior_prior["random_probability_start"],
                        behavior_prior["random_probability_end"])
                    for agent_index, agent_id in enumerate(env.agent_ids):
                        valid = np.flatnonzero(masks[agent_id])
                        draw = rng.rand()
                        if draw < p_random:
                            action = int(rng.choice(valid))
                            training_policy_audit["random_actions_executed"] += 1
                        elif draw < p_random + p_reference:
                            action = int(reference[agent_id])
                            training_policy_audit[
                                "reference_actions_executed"] += 1
                        else:
                            action = int(greedy[agent_index])
                            training_policy_audit["learned_actions_executed"] += 1
                        actions[agent_id] = action
                        training_policy_audit["eligible_decisions"] += 1
                        training_policy_audit[
                            "learned_reference_disagreements"] += int(
                                int(greedy[agent_index]) != reference[agent_id])
                        training_policy_audit["executed_interventions"] += int(
                            action != reference[agent_id])
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
                "pending": info.get("pending"),
                "completion_rate": info.get("completion_rate"),
                "insertion_rate": info.get("insertion_rate"),
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
                env_factory, validation_cases, horizon_seconds,
                network, config, fixed_duration, precomputed_baseline_rows)
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
    model_class = (PhaseScoringDDQN if controller_family == "neighbor_phase_ddqn"
                   else SharedDQN)
    final_network = model_class.load_bundle(
        os.path.join(checkpoints_dir, selected), contract)
    final_checkpoint = os.path.join(output_dir, "checkpoint")
    final_network.save_bundle(final_checkpoint, contract)
    reloaded = model_class.load_bundle(final_checkpoint, contract)

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
        "selected_validation_score": scores[selected],
        "checkpoint_eligibility_policy": dict(
            CHECKPOINT_ELIGIBILITY_POLICY),
        "checkpoint_reload": reload_verification,
    }
    if behavior_prior is not None:
        eligible = training_policy_audit["eligible_decisions"]
        training_policy_audit["executed_intervention_rate"] = (
            float(training_policy_audit["executed_interventions"]) / eligible
            if eligible else 0.0)
        summary["training_policy_audit"] = training_policy_audit
        summary["behavior_pretraining"] = behavior_pretraining
    if run.get("require_optimizer_updates") and updates <= 0:
        raise ValueError("run requires at least one optimizer update")
    _write_json(os.path.join(output_dir, "train-log.json"), episode_log)
    _write_json(os.path.join(output_dir, "validation.json"), validation_log)
    _write_json(os.path.join(output_dir, "replay-coverage.json"), coverage)
    _write_json(os.path.join(output_dir, "selection.json"), {
        "status": selection_status,
        "selected_checkpoint": selected,
        "eligible_for_test_evaluation": selection_status == "eligible",
        "eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "score": scores[selected],
    })
    _write_json(os.path.join(output_dir, "summary.json"), summary)
    artifact_paths = [
        "baseline-tuning.json", "resolved-config.json", "run-manifest.json",
        "train-log.json", "validation.json", "replay-coverage.json",
        "selection.json", "summary.json", "checkpoint/contract.json",
        "checkpoint/weights.npz",
    ]
    if behavior_prior is not None:
        artifact_paths.append("behavior-prior.json")
    if precomputed_provenance is not None:
        artifact_paths.append("baseline-tuning-provenance.json")
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
                  run_started_at=None,
                  controller_family="neighbor_phase_ddqn",
                  baseline_tuning_artifact=None):
    """Verify the immutable foundation, then train without opening test cases."""
    if controller_family not in ("neighbor_phase_ddqn", "shared_ddqn_legacy"):
        raise ValueError("unknown learned controller family")
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
            run_start_time, verification_seconds, controller_family,
            baseline_tuning_artifact)
    except Exception as exc:
        absolute_output = os.path.abspath(output_dir)
        if os.path.isdir(absolute_output):
            _write_json(os.path.join(absolute_output, "status.json"), {
                "status": "failed", "error_type": type(exc).__name__,
                "error": str(exc)})
        raise


def precompute_baseline_tuning(env_factory, manifest, config, artifact_path,
                               foundation_root=None, foundation_verifier=None):
    """Write one immutable validation-only fixed-time tuning artifact."""
    if manifest.get("protocol_version") != 2:
        raise ValueError("Hai Chau manifest protocol_version must be 2")
    if config.get("schema_version") != 2:
        raise ValueError("Hai Chau training config schema_version must be 2")
    validation_cases = [case for case in manifest.get("cases", [])
                        if case.get("split") == "validation"]
    if set(case.get("scenario") for case in validation_cases) != set(
            ("normal", "am_peak", "pm_peak")):
        raise ValueError("validation cases must cover normal/am_peak/pm_peak")
    run = config["run"]
    root = os.path.abspath(foundation_root or os.getcwd())
    verifier = foundation_verifier or _default_foundation_verifier
    _verify_training_foundation(root, manifest, verifier)
    artifact_path = os.path.abspath(artifact_path)
    if os.path.exists(artifact_path):
        raise ValueError("refusing to overwrite baseline tuning artifact")
    parent = os.path.dirname(artifact_path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    binding = _tuning_binding(
        manifest, validation_cases, int(run["horizon_seconds"]), config)
    tuning = _tune_fixed_time(
        env_factory, validation_cases, int(run["horizon_seconds"]), config,
        binding)
    _write_json(artifact_path, tuning)
    return tuning
