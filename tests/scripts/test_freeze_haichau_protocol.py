import hashlib
import json
import subprocess

import pytest

from scripts.freeze_haichau_protocol import (
    _canonical_hash, _contains_test_reference, freeze_protocol)
from scripts import verify_haichau_thesis
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.checkpoint_selection import (
    CHECKPOINT_ELIGIBILITY_POLICY, score_validation)
from traffic_rl.sim.phase_encoder import SCHEDULE_CONTEXT_FEATURES


RUNTIME_DIGEST = "sha256:" + "a" * 64
RUNTIME_IMAGE = "registry.example/traffic-rl@" + RUNTIME_DIGEST
RUNTIME_IMAGE_ID = "sha256:" + "b" * 64
LEARNED = ("neighbor_phase_ddqn",)
CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "neighbor_phase_ddqn",
)


@pytest.mark.parametrize("value", [
    "testcase-01", "results/test/case.json", "TEST-01", "test_normal_case",
])
def test_test_reference_detection_covers_ids_and_path_components(value):
    assert _contains_test_reference(value) is True


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    path.write_text(value)


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args), universal_newlines=True).strip()


def _commit(root):
    subprocess.check_call(["git", "init", "-q", str(root)])
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD")


def _contract(network_sha, phase_contract_sha, generator_config_sha,
              manifest_sha, controller_family):
    return {
        "training_objective": {
            "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.1,
                       "switch_penalty": 0.05},
            "temporal_aggregation": "mean_over_simulator_steps_in_action_interval",
        },
        "obs_schema_version": 3,
        "feature_dim": len(SCHEDULE_CONTEXT_FEATURES),
        "feature_order": list(SCHEDULE_CONTEXT_FEATURES),
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "hidden_size": 128,
        "action_contract": {
            "type": "phase_rows", "version": 1,
            "mask_type": "boolean_selectable_green_rows",
            "padding_actions_selectable": False,
        },
        "network_compatibility": {
            "network_sha256": network_sha,
            "phase_contract_sha256": phase_contract_sha,
            "generator_config_sha256": generator_config_sha,
            "manifest_sha256": manifest_sha,
        },
        "controller_family": controller_family,
        "checkpoint_eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "training_step": 12,
    }


def _training_artifact(root, controller, seed, network_sha, phase_contract_sha,
                       generator_config_sha, manifest_sha, validation_cases,
                       selected_config, include_test=False):
    relative = "release-training/%s/final-seed%d" % (controller, seed)
    run_dir = root / relative
    contract = _contract(
        network_sha, phase_contract_sha, generator_config_sha, manifest_sha,
        controller)
    model = PhaseScoringDDQN(
        len(SCHEDULE_CONTEXT_FEATURES), hidden=128, lr=0.001, seed=seed)
    model.save_bundle(str(run_dir / "checkpoint"), contract)
    validation = {}
    for step in (4, 8, 12):
        checkpoint = "step-%d" % step
        checkpoint_contract = json.loads(json.dumps(contract))
        checkpoint_contract["training_step"] = step
        model.save_bundle(
            str(run_dir / "checkpoints" / checkpoint), checkpoint_contract)
        candidate_queue = 90.0 if step == 12 else 110.0
        rows = [{
            "case_id": case["case_id"], "scenario": case["scenario"],
            "candidate_queue": candidate_queue, "baseline_queue": 100.0,
            "candidate_completion": 1.0, "baseline_completion": 1.0,
            "candidate_insertion": 1.0, "baseline_insertion": 1.0,
        } for case in validation_cases]
        checkpoint_score = score_validation(rows)
        checkpoint_score["training_step"] = step
        validation[checkpoint] = {"rows": rows, "score": checkpoint_score}
    score = validation["step-12"]["score"]
    if include_test:
        validation["step-12"]["rows"].append({"case_id": "test_normal_demand101"})
    _write(run_dir / "validation.json", validation)
    _write(run_dir / "selection.json", {
        "status": "eligible",
        "selected_checkpoint": "step-12",
        "eligible_for_test_evaluation": True,
        "eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
        "score": score,
    })
    resolved = json.loads(json.dumps(selected_config))
    resolved.update({
        "mode": "final", "learning_seed": seed,
        "network_sha256": network_sha,
        "run": selected_config["tiers"]["final"],
    })
    _write(run_dir / "resolved-config.json", resolved)
    _write(run_dir / "baseline-tuning.json", {
        "selection_cases": [case["case_id"] for case in validation_cases],
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "rows": [{
                "case_id": row["case_id"], "scenario": row["scenario"],
                "queue_integral_vehicle_seconds": row["baseline_queue"],
                "completion_rate": row["baseline_completion"],
                "insertion_rate": row["baseline_insertion"],
            } for row in validation["step-12"]["rows"]],
        }],
    })
    _write(run_dir / "run-manifest.json", {
        "controller_id": controller,
        "learning_seed": seed,
    })
    artifacts = {}
    for name in (
            "checkpoint/weights.npz", "checkpoint/contract.json",
            "validation.json", "selection.json", "resolved-config.json",
            "baseline-tuning.json", "run-manifest.json") + tuple(
                "checkpoints/step-%d/%s" % (step, name)
                for step in (4, 8, 12)
                for name in ("contract.json", "weights.npz")):
        artifacts[name] = _sha256(run_dir / name)
    _write(run_dir / "status.json", {
        "status": "complete", "eligible_for_test_evaluation": True,
        "artifact_sha256": artifacts,
    })
    return relative


def _pilot_selection(root, manifest_path):
    selected = {
        "schema_version": 2,
        "exploration": {"epsilon_decay_decisions": 4320},
        "model": {"feature_dim": 15, "hidden": 128},
        "observation": {
            "schema_version": 3,
            "type": "phase_rows_fixed_schedule_context",
            "phase_row_identity": "cycle_fraction",
            "global_cycle": {
                "encoding": "sin_cos", "green_duration_seconds": 25,
                "period": "green_duration_times_selectable_green_count",
            },
        },
        "behavior_prior": {
            "type": "fixed_time_behavior_cloning", "bc_epochs": 1,
            "pre_rl_validation": True,
            "reference_probability_start": 0.0,
            "reference_probability_end": 0.0,
            "random_probability_start": 0.10,
            "random_probability_end": 0.02,
            "minimum_validation_reference_disagreement_rate": 0.01,
            "rehearsal": {
                "enabled": True, "type": "behavior_clone",
                "every_td_updates": 1, "batch_size": 128,
            },
        },
        "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.1,
                   "switch_penalty": 0.05},
        "tiers": {
            "pilot": {
                "episodes": 12, "horizon_seconds": 3600, "eval_every": 4},
            "final": {
                "episodes": 12, "horizon_seconds": 3600, "eval_every": 4},
        },
    }
    ablation = json.loads(json.dumps(selected))
    ablation["behavior_prior"]["rehearsal"]["enabled"] = False
    configs = {}
    for name, source in (("schedule_bc_rehearsal", selected),
                         ("schedule_bc_no_rehearsal", ablation)):
        path = root / "release" / (name + ".yaml")
        _write(path, source)
        configs[name] = {
            "path": str(path.relative_to(root)), "sha256": _sha256(path),
            "behavior_prior": source["behavior_prior"],
        }
    selected_path = root / "release" / "selected.yaml"
    _write(selected_path, selected)
    baseline = root / "release" / "pilot-baseline.json"
    manifest = json.loads(manifest_path.read_text())
    validation_cases = [case for case in manifest["cases"]
                        if case["split"] == "validation"]
    baseline_document = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "binding": {"manifest_sha256": _canonical_hash(manifest)},
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "rows": [{
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "queue_integral_vehicle_seconds": 100.0,
                "completion_rate": 1.0,
                "insertion_rate": 1.0,
            } for case in validation_cases],
        }],
    }
    baseline_document["tuning_sha256"] = _canonical_hash(baseline_document)
    _write(baseline, baseline_document)
    spec_path = root / "release" / "schedule-selection.yaml"
    spec_arms = dict((name, {
        "config": configs[name]["path"],
        "run_dir": "release/pilot-" + name,
    }) for name in ("schedule_bc_rehearsal", "schedule_bc_no_rehearsal"))
    _write(spec_path, {
        "schema_version": 1,
        "decision_type": "haichau_pilot_schedule_rehearsal_selection",
        "learning_seed": 11, "mode": "pilot",
        "manifest": str(manifest_path.relative_to(root)),
        "baseline_tuning_artifact": str(baseline.relative_to(root)),
        "diagnostic_checkpoint": "step-0",
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "arms": spec_arms,
        "decision_output": "release/pilot-v3-schedule-selection.json",
        "selected_config_output": str(selected_path.relative_to(root)),
    })
    source_tree = {
        "schema_version": 1, "git_commit": "a" * 40,
        "tracked_worktree": "clean", "index": "clean",
        "untracked_files_policy": "allowed",
    }
    from traffic_rl.research.pilot_schedule_selector import _validate_arm

    manifest_hash = _canonical_hash(manifest)
    baseline_hash = _sha256(baseline)
    train_cases = [case for case in manifest["cases"]
                   if case["split"] == "train"]
    arms = {}
    for name, config in (("schedule_bc_rehearsal", selected),
                         ("schedule_bc_no_rehearsal", ablation)):
        run_dir = root / spec_arms[name]["run_dir"]
        execution_config = json.loads(json.dumps(config))
        execution_config.update({
            "mode": "pilot", "learning_seed": 11,
            "run": config["tiers"]["pilot"],
        })
        if "simulation" in manifest:
            execution_config["simulation"] = manifest["simulation"]
        training_config_sha = _canonical_hash(execution_config)
        _write(run_dir / "run-manifest.json", {
            "controller_id": "neighbor_phase_ddqn", "mode": "pilot",
            "learning_seed": 11, "manifest_sha256": manifest_hash,
            "code_commit": "a" * 40, "source_tree": source_tree,
        })
        resolved = json.loads(json.dumps(config))
        resolved.update({
            "mode": "pilot", "learning_seed": 11,
            "run": config["tiers"]["pilot"],
            "manifest_sha256": manifest_hash,
            "baseline_tuning_sha256": baseline_document["tuning_sha256"],
            "training_config_sha256": training_config_sha,
            "source_tree": source_tree,
        })
        if "simulation" in manifest:
            resolved["simulation"] = manifest["simulation"]
        _write(run_dir / "resolved-config.json", resolved)
        _write(run_dir / "baseline-tuning.json", baseline_document)
        _write(run_dir / "baseline-tuning-provenance.json", {
            "source_artifact_sha256": baseline_hash,
            "copied_artifact_sha256": _sha256(
                run_dir / "baseline-tuning.json"),
            "tuning_sha256": baseline_document["tuning_sha256"],
        })
        _write(run_dir / "behavior-prior.json", {
            "schema_version": 2,
            "loss_name": "conditional_cross_entropy",
            "labels": 10, "switch_eligible_labels": 10,
            "conditional_cross_entropy": 0.2, "top1_agreement": 0.8,
            "source_split": "train",
            "source_case_ids": [case["case_id"] for case in train_cases],
            "train_cases": [{
                "case_id": case["case_id"],
                "flow_sha256": case["flow_sha256"],
            } for case in train_cases],
        })
        _write(run_dir / "summary.json", {
            "behavior_rehearsal": {
                "enabled": config["behavior_prior"]["rehearsal"]["enabled"],
                "source_split": "train",
                "updates": (1 if config["behavior_prior"]["rehearsal"][
                    "enabled"] else 0),
            },
        })
        validation = {}
        model = PhaseScoringDDQN(15, hidden=128, lr=0.001, seed=11)
        for step in (0, 4, 8, 12):
            candidate_queue = (100.0 if step == 0 else
                               90.0 + (0.0 if name ==
                                      "schedule_bc_rehearsal" else 5.0))
            rows = [{
                "case_id": case["case_id"], "scenario": case["scenario"],
                "baseline_queue": 100.0,
                "candidate_queue": candidate_queue,
                "baseline_completion": 1.0, "candidate_completion": 1.0,
                "baseline_insertion": 1.0, "candidate_insertion": 1.0,
                "policy_audit": {
                    "evaluation_policy": "raw_ddqn_greedy",
                    "switch_eligible_decisions": 100,
                    "switch_eligible_reference_disagreements": 10,
                    "switch_eligible_reference_disagreement_rate": 0.1,
                },
            } for case in validation_cases]
            score = score_validation(rows)
            score["training_step"] = step
            checkpoint = "step-%d" % step
            validation[checkpoint] = {"rows": rows, "score": score}
            if step == 0:
                validation[checkpoint].update({
                    "diagnostic_only": True, "selectable": False})
                continue
            contract = {
                "obs_schema_version": 3, "feature_dim": 15,
                "feature_order": list(SCHEDULE_CONTEXT_FEATURES),
                "hidden_size": 128,
                "observation": config["observation"],
                "behavior_prior": config["behavior_prior"],
                "controller_family": "neighbor_phase_ddqn",
                "training_step": step,
                "manifest_sha256": manifest_hash,
                "baseline_tuning_sha256": baseline_document["tuning_sha256"],
                "training_config_sha256": training_config_sha,
                "source_tree": source_tree,
            }
            model.save_bundle(str(run_dir / "checkpoints" / checkpoint), contract)
        _write(run_dir / "validation.json", validation)
        selected_score = validation["step-4"]["score"]
        _write(run_dir / "selection.json", {
            "status": "eligible", "selected_checkpoint": "step-4",
            "eligible_for_test_evaluation": True,
            "eligibility_policy": dict(CHECKPOINT_ELIGIBILITY_POLICY),
            "score": selected_score,
        })
        artifacts = {}
        for artifact in (
                "run-manifest.json", "resolved-config.json",
                "baseline-tuning.json", "baseline-tuning-provenance.json",
                "behavior-prior.json", "validation.json", "selection.json",
                "summary.json") + tuple(
                    "checkpoints/step-%d/%s" % (step, item)
                    for step in (4, 8, 12)
                    for item in ("contract.json", "weights.npz")):
            artifacts[artifact] = _sha256(run_dir / artifact)
        _write(run_dir / "status.json", {
            "status": "complete", "eligible_for_test_evaluation": True,
            "artifact_sha256": artifacts,
        })
        arms[name] = _validate_arm(
            root, name, {
                "arms": spec_arms, "diagnostic_checkpoint": "step-0"},
            config, manifest, baseline_document, baseline_hash, manifest_hash,
            "a" * 40, source_tree)
    winner = min(arms, key=lambda arm: tuple(arms[arm]["rank_tuple"]))
    decision = {
        "schema_version": 1,
        "decision_type": "haichau_pilot_schedule_rehearsal_selection",
        "specification": {"path": str(spec_path.relative_to(root)),
                          "sha256": _sha256(spec_path)},
        "inputs": {
            "code_commit": "a" * 40,
            "source_tree": source_tree,
            "manifest": {"path": str(manifest_path.relative_to(root)),
                         "sha256": _sha256(manifest_path),
                         "canonical_json_sha256": _canonical_hash(manifest)},
            "baseline_tuning": {"path": str(baseline.relative_to(root)),
                               "sha256": _sha256(baseline),
                               "tuning_sha256": baseline_document[
                                   "tuning_sha256"]},
            "configs": configs,
        },
        "arms": arms,
        "validation_checkpoints": ["step-4", "step-8", "step-12"],
        "diagnostic_checkpoint": "step-0",
        "winner": {"arm": winner,
                   "selected_checkpoint": arms[winner]["selected_checkpoint"],
                   "rank_tuple": arms[winner]["rank_tuple"],
                   "config": configs[winner]},
        "selected_config": {"path": str(selected_path.relative_to(root)),
                            "sha256": _sha256(selected_path)},
    }
    decision["decision_identity_sha256"] = _canonical_hash(decision)
    decision_path = root / "release" / "pilot-v3-schedule-selection.json"
    _write(decision_path, decision)
    binding = {
        "path": str(decision_path.relative_to(root)),
        "sha256": _sha256(decision_path),
        "decision_identity_sha256": decision["decision_identity_sha256"],
        "primary_learned_controller": "neighbor_phase_ddqn",
        "pilot_learning_seed": 11,
        "winner": {"arm": winner,
                   "selected_checkpoint": arms[winner]["selected_checkpoint"],
                   "config": configs[winner]},
        "selected_config": {"path": str(selected_path.relative_to(root)),
                            "sha256": _sha256(selected_path)},
    }
    training_bindings = {
        "neighbor_phase_ddqn": {
            "path": str(selected_path.relative_to(root)),
            "sha256": _sha256(selected_path),
        },
    }
    return selected, binding, training_bindings


def _fixture(root):
    agent_ids = ["N%02d" % number for number in range(53)]
    roadnet = root / "release/roadnet.json"
    viewer = root / "release/viewer.json"
    _write(roadnet, {"intersections": agent_ids})
    _write(viewer, {"nodes": agent_ids})
    network_sha = _sha256(roadnet)
    phase_contract = root / "release/phase-contract.json"
    generator_config = root / "release/generator-config.json"
    _write(phase_contract, {"phase_contract": 1})
    _write(generator_config, {"generator_config": 1})
    cases = []
    for split, count in (("train", 9), ("validation", 6), ("test", 15)):
        for number in range(count):
            scenario = ("normal", "am_peak", "pm_peak")[number % 3]
            flow = root / ("release/%s-%02d.json" % (split, number))
            _write(flow, "%s-%02d" % (split, number))
            cases.append({
                "case_id": "%s_%s_%02d" % (split, scenario, number),
                "split": split,
                "scenario": scenario,
                "demand_seed": 100 + number,
                "sim_seed": 200 + number,
                "flow_path": str(flow.relative_to(root)),
                "flow_sha256": _sha256(flow),
                "scheduled_vehicles": 1000 + number,
            })
    manifest = {
        "protocol_version": 2,
        "network": {
            "controlled_signals": 53, "agent_ids": agent_ids,
            "path": str(roadnet.relative_to(root)), "sha256": network_sha,
        },
        "phase_contract": {
            "path": str(phase_contract.relative_to(root)),
            "sha256": _sha256(phase_contract),
        },
        "generator_config_path": str(generator_config.relative_to(root)),
        "generator_config_sha256": _sha256(generator_config),
        "runtime": {"base_image_digest": RUNTIME_DIGEST},
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
        "cases": cases,
    }
    manifest_path = root / "release/experiment-manifest.json"
    _write(manifest_path, manifest)
    manifest_sha = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    validation_cases = [case for case in cases if case["split"] == "validation"]
    selected_config, selection_binding, training_bindings = \
        _pilot_selection(root, manifest_path)
    dockerfile = root / "docker/haichau-evaluation.Dockerfile"
    _write(dockerfile, "FROM %s\n" % RUNTIME_IMAGE)
    controller_configs = dict(
        (controller, {"controller_version": 2}) for controller in CONTROLLERS)
    controller_configs["tuned_fixed"]["green_duration"] = 30
    controller_configs["hysteretic_mp"].update({
        "min_hold_decisions": 3, "switch_threshold": 2.5,
    })
    config = {
        "resolved_config": {
            "network_path": str(roadnet.relative_to(root)),
            "phase_contract_path": str(phase_contract.relative_to(root)),
            "phase_contract_sha256": _sha256(phase_contract),
            "step_seconds": 1,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {
                "action_interval": 10, "yellow_time": 3,
                "min_green": 20, "maximum_red": 180,
            },
            "reward": {
                "queue_weight": 1.0, "downstream_block_weight": 0.1,
                "switch_penalty": 0.05,
            },
        },
        "controller_configs": controller_configs,
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": [12, 13, 14, 15, 16],
        "pilot_schedule_selection": selection_binding,
        "training_config_bindings": training_bindings,
        "controller_commands": dict(
            (controller, ["python3", "scripts/evaluate_haichau_network.py"])
            for controller in CONTROLLERS),
    }
    config_path = root / "release/controller-configs.json"
    _write(config_path, config)
    index = dict((controller, {}) for controller in LEARNED)
    for controller in LEARNED:
        for seed in range(12, 17):
            index[controller][str(seed)] = _training_artifact(
                root, controller, seed, network_sha,
                manifest["phase_contract"]["sha256"],
                manifest["generator_config_sha256"], manifest_sha,
                validation_cases, selected_config)
    index_path = root / "release/training-index.json"
    _write(index_path, index)
    commit = _commit(root)
    return {
        "agent_ids": agent_ids,
        "commit": commit,
        "config": config_path,
        "dockerfile": dockerfile,
        "index": index_path,
        "manifest": manifest_path,
        "network_sha": network_sha,
        "phase_contract_sha": manifest["phase_contract"]["sha256"],
        "generator_config_sha": manifest["generator_config_sha256"],
        "manifest_sha": manifest_sha,
        "roadnet": roadnet,
        "viewer": viewer,
    }


def _runtime(image):
    assert image == RUNTIME_IMAGE
    return {
        "runtime_image": RUNTIME_IMAGE,
        "runtime_image_id": RUNTIME_IMAGE_ID,
        "repo_digests": [RUNTIME_IMAGE],
    }


def _add_precomputed_tuning_provenance(root, relative):
    run_dir = root / relative
    tuning_path = run_dir / "baseline-tuning.json"
    manifest = json.loads((root / "release/experiment-manifest.json").read_text())
    validation_cases = [case for case in manifest["cases"]
                        if case["split"] == "validation"]
    resolved_path = run_dir / "resolved-config.json"
    resolved = json.loads(resolved_path.read_text())
    resolved["baseline"] = {
        "controller": "validation_tuned_fixed",
        "search_green_durations": [30],
    }
    resolved["simulation"] = {"action_interval": 10}
    _write(resolved_path, resolved)
    tuning = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "search_space": {"fixed_green_duration": [30]},
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "mean_queue_integral_vehicle_seconds": 100.0,
            "rows": [{
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "queue_integral_vehicle_seconds": 100.0,
                "completion_rate": 1.0,
                "insertion_rate": 1.0,
            } for case in validation_cases],
        }],
        "binding": {
            "manifest_sha256": _canonical_hash(manifest),
            "network_sha256": manifest["network"]["sha256"],
            "generator_config_sha256": manifest["generator_config_sha256"],
            "runtime": manifest["runtime"],
            "validation_case_hashes": dict(
                (case["case_id"], case["flow_sha256"])
                for case in validation_cases),
            "horizon_seconds": 3600,
            "action_interval": 10,
            "queue_objective": {
                "schema_version": 2,
                "network_queue": "per_step_waiting",
                "entry_pending": "due_not_inserted",
                "future_departures": "unreleased_excluded",
            },
        },
    }
    tuning["tuning_sha256"] = _canonical_hash(tuning)
    _write(tuning_path, tuning)
    provenance_path = run_dir / "baseline-tuning-provenance.json"
    _write(provenance_path, {
        "schema_version": 1,
        "strategy": "precomputed_baseline_tuning",
        "source_kind": "file",
        "source_path": "cache/baseline-tuning.json",
        "source_artifact_sha256": "f" * 64,
        "copied_artifact_path": "baseline-tuning.json",
        "copied_artifact_sha256": _sha256(tuning_path),
        "tuning_sha256": tuning["tuning_sha256"],
    })
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"] = {
        "mode": "precomputed",
        "tuning_sha256": tuning["tuning_sha256"],
        "copied_artifact_path": "baseline-tuning.json",
        "copied_artifact_sha256": _sha256(tuning_path),
        "provenance_path": "baseline-tuning-provenance.json",
        "provenance_sha256": _sha256(provenance_path),
    }
    _write(run_manifest_path, run_manifest)
    for contract_path in (run_dir / "checkpoint/contract.json",
                          run_dir / "checkpoints/step-12/contract.json"):
        contract = json.loads(contract_path.read_text())
        contract["baseline_tuning_provenance_sha256"] = run_manifest[
            "baseline_tuning"]["provenance_sha256"]
        contract["baseline_tuning_artifact_sha256"] = run_manifest[
            "baseline_tuning"]["copied_artifact_sha256"]
        _write(contract_path, contract)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
    status["artifact_sha256"]["resolved-config.json"] = _sha256(resolved_path)
    status["artifact_sha256"]["checkpoint/contract.json"] = _sha256(
        run_dir / "checkpoint/contract.json")
    status["artifact_sha256"]["checkpoints/step-12/contract.json"] = _sha256(
        run_dir / "checkpoints/step-12/contract.json")
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    status["artifact_sha256"]["baseline-tuning-provenance.json"] = _sha256(
        provenance_path)
    _write(status_path, status)


def _refresh_precomputed_tuning_hashes(run_dir):
    tuning_path = run_dir / "baseline-tuning.json"
    tuning = json.loads(tuning_path.read_text())
    tuning["tuning_sha256"] = _canonical_hash(
        dict((key, value) for key, value in tuning.items()
             if key != "tuning_sha256"))
    _write(tuning_path, tuning)
    provenance_path = run_dir / "baseline-tuning-provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["copied_artifact_sha256"] = _sha256(tuning_path)
    provenance["tuning_sha256"] = tuning["tuning_sha256"]
    _write(provenance_path, provenance)
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"]["tuning_sha256"] = tuning["tuning_sha256"]
    run_manifest["baseline_tuning"]["copied_artifact_sha256"] = _sha256(
        tuning_path)
    run_manifest["baseline_tuning"]["provenance_sha256"] = _sha256(
        provenance_path)
    _write(run_manifest_path, run_manifest)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
    status["artifact_sha256"]["baseline-tuning-provenance.json"] = _sha256(
        provenance_path)
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    _write(status_path, status)


def test_freeze_audits_hash_bound_precomputed_baseline_provenance(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["12"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "add cache provenance")

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    checkpoint = next(item for item in protocol["checkpoints"]
                      if item["controller_id"] == "neighbor_phase_ddqn"
                      and item["learning_seed"] == 12)
    assert "baseline-tuning-provenance.json" in checkpoint["source_artifacts"]


def test_freeze_rejects_precomputed_baseline_provenance_hash_drift(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["12"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    run_dir = tmp_path / relative
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"]["provenance_sha256"] = "0" * 64
    _write(run_manifest_path, run_manifest)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "drift cache provenance")

    with pytest.raises(ValueError, match="provenance hash drift"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_revalidates_precomputed_baseline_binding(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["12"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    run_dir = tmp_path / relative
    tuning_path = run_dir / "baseline-tuning.json"
    tuning = json.loads(tuning_path.read_text())
    del tuning["binding"]
    _write(tuning_path, tuning)
    _refresh_precomputed_tuning_hashes(run_dir)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove cache binding")

    with pytest.raises(ValueError, match="binding"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_writes_hash_bound_protocol_from_all_final_eligible_cells(tmp_path):
    fixture = _fixture(tmp_path)

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    output = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    assert json.loads(output.read_text()) == protocol
    assert protocol["code_commit"] == fixture["commit"]
    assert protocol["agent_ids"] == fixture["agent_ids"]
    assert protocol["network_sha256"] == fixture["network_sha"]
    assert protocol["phase_contract_sha256"] == fixture["phase_contract_sha"]
    assert protocol["generator_config_sha256"] == fixture["generator_config_sha"]
    assert protocol["experiment_manifest_sha256"] == fixture["manifest_sha"]
    assert protocol["runtime_image_id"] == RUNTIME_IMAGE_ID
    assert set(protocol["controller_configs"]) == set(CONTROLLERS)
    assert len(protocol["checkpoints"]) == 5
    assert all(entry["validation_eligible"] for entry in protocol["checkpoints"])
    assert all("validation.json" in entry["source_artifacts"]
               for entry in protocol["checkpoints"])
    assert all(entry["contract_path"].endswith("checkpoint/contract.json")
               for entry in protocol["checkpoints"])
    assert all(entry["contract_file_sha256"] == _sha256(
        tmp_path / entry["contract_path"])
               for entry in protocol["checkpoints"])
    assert protocol["acceptance_rules"]["required_learning_seeds"] == [12, 13, 14, 15, 16]
    assert protocol["case_manifest_sha256"] == _sha256(
        tmp_path / protocol["case_manifest_path"])
    assert protocol["network_manifest_sha256"] == _sha256(
        tmp_path / protocol["network_manifest_path"])
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "freeze protocol")
    assert verify_haichau_thesis._network_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._case_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._checkpoint_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._acceptance_rules(protocol)["bootstrap_samples"] == 10000


def test_freeze_requires_pilot_schedule_selection_binding(tmp_path):
    fixture = _fixture(tmp_path)
    document = json.loads(fixture["config"].read_text())
    del document["pilot_schedule_selection"]
    _write(fixture["config"], document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove selection binding")

    with pytest.raises(ValueError, match="pilot V3 schedule selection"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_rejects_pilot_seed_or_unselected_family_in_training_index(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    index["neighbor_phase_ddqn"]["11"] = index[
        "neighbor_phase_ddqn"]["12"]
    index["shared_ddqn_legacy"] = {}
    _write(fixture["index"], index)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "inject pilot seed and unselected family")

    with pytest.raises(ValueError, match="selected learned controller"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_requires_and_preserves_scheduled_vehicle_counts(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = json.loads(fixture["manifest"].read_text())
    expected = dict((case["case_id"], case["scheduled_vehicles"])
                    for case in manifest["cases"])

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    release_manifest = json.loads(
        (tmp_path / protocol["case_manifest_path"]).read_text())
    assert dict((case["case_id"], case["scheduled_vehicles"])
                for case in release_manifest["cases"]) == expected


def test_freeze_rejects_case_without_scheduled_vehicle_count(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = json.loads(fixture["manifest"].read_text())
    del manifest["cases"][0]["scheduled_vehicles"]
    _write(fixture["manifest"], manifest)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove scheduled vehicle count")

    with pytest.raises(ValueError, match="scheduled_vehicles"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_overwrite_or_any_test_case_in_selection_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    relative = index["neighbor_phase_ddqn"]["12"]
    validation = tmp_path / relative / "validation.json"
    document = json.loads(validation.read_text())
    document["step-12"]["rows"].append({"case_id": "test_normal_demand00"})
    _write(validation, document)
    status = tmp_path / relative / "status.json"
    status_doc = json.loads(status.read_text())
    status_doc["artifact_sha256"]["validation.json"] = _sha256(validation)
    _write(status, status_doc)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "inject test evidence")

    with pytest.raises(ValueError, match="test.*selection"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_recomputes_insertion_gate_and_rejects_old_eligible_artifact(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    for row in validation["step-12"]["rows"]:
        row.pop("candidate_insertion")
        row.pop("baseline_insertion")
    _write(validation_path, validation)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["validation.json"] = _sha256(validation_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove insertion evidence")

    with pytest.raises(ValueError, match="score|insertion|eligible|baseline"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_requires_the_selected_checkpoint_bundle_to_match_final_checkpoint(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["13"]
    (run_dir / "checkpoints/step-12/weights.npz").unlink()
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "remove selected checkpoint")

    with pytest.raises(ValueError, match="selected checkpoint|training artifact is missing"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_requires_exact_v3_validation_checkpoint_set(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    del validation["step-8"]
    _write(validation_path, validation)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["validation.json"] = _sha256(validation_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove V3 validation checkpoint")

    with pytest.raises(ValueError, match="validation checkpoints must be exactly"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_binds_contract_training_step_to_selected_checkpoint(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    contract_path = run_dir / "checkpoint/contract.json"
    contract = json.loads(contract_path.read_text())
    contract["training_step"] = None
    _write(contract_path, contract)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["checkpoint/contract.json"] = _sha256(
        contract_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "detach selected training step")

    with pytest.raises(ValueError, match="training_step"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_binds_reported_score_step_to_checkpoint_key(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    validation["step-12"]["score"]["training_step"] = 8
    _write(validation_path, validation)
    selection_path = run_dir / "selection.json"
    selection = json.loads(selection_path.read_text())
    selection["score"]["training_step"] = 8
    _write(selection_path, selection)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["validation.json"] = _sha256(validation_path)
    status["artifact_sha256"]["selection.json"] = _sha256(selection_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "detach score training step")

    with pytest.raises(ValueError, match="training_step differs"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_recomputes_the_best_eligible_final_checkpoint(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    validation_path = run_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    for row in validation["step-4"]["rows"]:
        row["candidate_queue"] = 80.0
    score = score_validation(validation["step-4"]["rows"])
    score["training_step"] = 4
    validation["step-4"]["score"] = score
    _write(validation_path, validation)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["validation.json"] = _sha256(validation_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "make step four best")

    with pytest.raises(ValueError, match="best eligible checkpoint"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


@pytest.mark.parametrize("field,value", [
    ("horizon_seconds", 120),
    ("episodes", 80),
    ("eval_every", 20),
])
def test_freeze_refuses_any_non_v3_final_tier(tmp_path, field, value):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    resolved = run_dir / "resolved-config.json"
    document = json.loads(resolved.read_text())
    document["run"][field] = value
    _write(resolved, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["resolved-config.json"] = _sha256(resolved)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "non-v3 final run")

    with pytest.raises(ValueError, match="selected config drift|full 3600-second horizon"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_status_artifact_paths_that_escape_the_training_run(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["13"]
    status = run_dir / "status.json"
    document = json.loads(status.read_text())
    escaped = tmp_path / "release/experiment-manifest.json"
    document["artifact_sha256"]["../../../release/experiment-manifest.json"] = _sha256(escaped)
    _write(status, document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "escape training status")

    with pytest.raises(ValueError, match="escapes the training run"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_test_metric_keys_in_checkpoint_selection_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["14"]
    validation = run_dir / "validation.json"
    document = json.loads(validation.read_text())
    document["step-12"]["test_metrics"] = {"queue_integral": 1.0}
    _write(validation, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["validation.json"] = _sha256(validation)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "inject test metric key")

    with pytest.raises(ValueError, match="test metric.*selection"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_conflicting_legacy_contract_aliases(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["15"]
    contract = run_dir / "checkpoint/contract.json"
    document = json.loads(contract.read_text())
    document["hidden"] = 64
    _write(contract, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["checkpoint/contract.json"] = _sha256(contract)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "conflicting old checkpoint alias")

    with pytest.raises(ValueError, match="alias drift"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


@pytest.mark.parametrize(
    "mutate, error",
        [
            (lambda contract: contract["action_contract"].update({"version": 2}),
             "action contract drift"),
            (lambda contract: contract.update(
                {"feature_order": ["forged_%d" % index for index in range(12)]}),
             "feature order drift"),
            (lambda contract: contract["normalization"].update(
                {"count_norm": 99.0}),
             "normalization is invalid"),
            (lambda contract: contract["network_compatibility"].update(
            {"phase_contract_sha256": "0" * 64}),
         "network compatibility drift"),
    ],
)
def test_freeze_requires_exact_neighbor_contract(tmp_path, mutate, error):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    contract = run_dir / "checkpoint/contract.json"
    document = json.loads(contract.read_text())
    mutate(document)
    _write(contract, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["checkpoint/contract.json"] = _sha256(contract)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "mutate neighbor contract")

    with pytest.raises(ValueError, match=error):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)

    final = tmp_path / "results/haichau_network_v2/final"
    final.mkdir(parents=True)
    _write(final / "frozen-protocol.json", "{}")
    with pytest.raises(ValueError, match="overwrite"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


@pytest.mark.parametrize('mutation', ['missing', 'endpoint', 'reward', 'resolved_reward'])
def test_freeze_rejects_training_objective_drift(tmp_path, mutation):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture['index'].read_text())['neighbor_phase_ddqn']['12']
    run_dir = tmp_path / relative
    for path in [run_dir / 'checkpoint/contract.json',
                 run_dir / 'checkpoints/step-12/contract.json']:
        contract = json.loads(path.read_text())
        if mutation == 'missing':
            del contract['training_objective']
        elif mutation == 'endpoint':
            contract['training_objective']['temporal_aggregation'] = 'endpoint'
        elif mutation == 'reward':
            contract['training_objective']['reward']['queue_weight'] = 2.0
        _write(path, contract)
    if mutation == 'resolved_reward':
        path = run_dir / 'resolved-config.json'
        resolved = json.loads(path.read_text())
        resolved['reward']['queue_weight'] = 2.0
        _write(path, resolved)
    status_path = run_dir / 'status.json'
    status = json.loads(status_path.read_text())
    for relative in status['artifact_sha256']:
        status['artifact_sha256'][relative] = _sha256(run_dir / relative)
    _write(status_path, status)
    _git(tmp_path, 'add', '.')
    _git(tmp_path, 'commit', '-qm', 'training objective drift')
    with pytest.raises(ValueError, match='selected config drift|training objective'):
        freeze_protocol(
            tmp_path, fixture['manifest'], fixture['viewer'], fixture['config'],
            fixture['index'], RUNTIME_IMAGE, fixture['dockerfile'],
            runtime_inspector=_runtime)
