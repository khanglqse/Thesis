import copy
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from traffic_rl.agents.schedule_residual import (
    CRITIC_UNITS, MACRO_FEATURES, MAX_MACROS, POLICY_INPUT_SCHEMA,
    ResidualDDQN, select_macro)
from traffic_rl.train.network_trainer import canonical_json_sha256, _tuning_binding
from traffic_rl.train.schedule_residual_trainer import OPERATIONAL_MODE


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value)
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args),
        stderr=subprocess.STDOUT, universal_newlines=True).strip()


def _metric(queue):
    return {
        "queue_integral_vehicle_seconds": float(queue),
        "network_queue_integral_vehicle_seconds": float(queue) - 10.0,
        "pending_integral_vehicle_seconds": 10.0,
        "completion_rate": 0.90,
        "insertion_rate": 0.95,
        "phase_switches": 100,
        "max_red_seconds": 120,
        "step": 3600,
        "scheduled": 100,
        "due": 100,
        "inserted": 95,
        "arrived": 90,
        "running": 5,
        "pending": 5,
    }


def _rewards(queue):
    values = [float(queue) / 12.0] * 11
    values.append(float(queue) - sum(values))
    return [{
        "block_start_second": index * 300,
        "duration_seconds": 300,
        "raw_objective_vehicle_seconds": value,
        "raw_reward_vehicle_seconds": -value,
        "scaled_reward": -value / 100000.0,
        "network_queue_vehicle_seconds": value - 1.0,
        "entry_pending_vehicle_seconds": 1.0,
    } for index, value in enumerate(values)]


def _events(nodes, reason, actions=None):
    actions = actions or {}
    result = []
    for block in range(12):
        for node in nodes:
            macro = int(actions.get((block, node), 0))
            active = macro != 0
            result.append({
                "node": node,
                "block_start_second": block * 300,
                "macro_id": macro,
                "reason": "learned_macro" if active else reason,
                "boundary_second": block * 300 + 100 if active else None,
                "shift_seconds": 10 if active else 0,
            })
    return result


def _audit(nodes, mode, actions=None, baseline=False):
    actions = actions or {}
    reason = ("normal_exact_reference" if mode == "normal" else
              "zero_residual_diagnostic" if baseline else
              "baseline_tie_or_best")
    events = _events(nodes, reason, actions=actions)
    nonzero = sum(event["macro_id"] != 0 for event in events)
    active_nodes = sorted(set(event["node"] for event in events
                              if event["macro_id"] != 0))
    return {
        "time_of_day": mode,
        "observed_node_seconds": len(nodes) * 3600,
        "phase_divergence_seconds": 10 * nonzero,
        "service_divergence_seconds": 10 * nonzero,
        "state_divergence_seconds": 10 * nonzero,
        "nonzero_macros": nonzero,
        "illegal_requests": 0,
        "anchor_violations": 0,
        "unlogged_divergence_seconds": 0,
        "resync_successes": len(nodes) * 12,
        "nonzero_macro_nodes": active_nodes,
        "abstentions": {reason: len(events) - nonzero},
        "phase_definition": "lightphase_exposed_during_simulator_step",
        "service_definition": "movement_time_since_service_divergence",
        "macro_events": events,
    }


def _timeline(nodes, actions):
    digest = hashlib.sha256()
    for second in range(1, 3601):
        block = (second - 1) // 300
        for node in nodes:
            macro = int(actions.get((block, node), 0))
            frame = {
                "second": second, "node": node,
                "served_lightphase": macro,
                "signal_state": {
                    "macro_id": macro,
                    "second_in_block": (second - 1) % 300,
                },
            }
            digest.update((json.dumps(
                frame, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return {
        "schema_version": 1,
        "frame_definition": (
            "canonical_json_lines(second,node,served_lightphase,signal_state)_v1"),
        "observed_node_seconds": len(nodes) * 3600,
        "sha256": digest.hexdigest(),
    }


class _FixtureValidationRunner(object):
    """Policy replay whose source rows derive from actual checkpoint scores."""
    def __init__(self, nodes):
        self.nodes = list(nodes)

    def _actions(self, network, scenario, policy):
        actions = {}
        if policy != "candidate" or scenario == "normal":
            return actions
        for index, node in enumerate(self.nodes):
            desired = index + 1
            features = np.zeros((MAX_MACROS, len(MACRO_FEATURES)), np.float32)
            mask = np.zeros(MAX_MACROS, np.bool_)
            mask[[0, desired]] = True
            features[desired, 0] = 1.0
            scores = network.q_values(features, mask)[0]
            choice, _ = select_macro(scores, mask)
            actions[(0, node)] = choice
        return actions

    def __call__(self, network, training_step, case, policy):
        scenario = case["scenario"]
        actions = self._actions(network, scenario, policy)
        learned = sum(value != 0 for value in actions.values())
        queue = 1000
        if policy == "candidate" and scenario != "normal" and learned == 2:
            queue = ({2: {"am_peak": 980, "pm_peak": 990},
                      4: {"am_peak": 970, "pm_peak": 980}}
                     [training_step][scenario])
        result = {"metrics": _metric(queue),
                  "timeline": _timeline(self.nodes, actions)}
        if policy != "fixed25":
            result.update({
                "macro_rewards": _rewards(queue),
                "policy_audit": _audit(
                    self.nodes, scenario, actions=actions,
                    baseline=(policy == "forced_macro0")),
            })
        return result


def _row(case, candidate, baseline):
    return {
        "case_id": case["case_id"],
        "scenario": case["scenario"],
        "horizon_seconds": 3600,
        "baseline": baseline["metrics"],
        "candidate": candidate["metrics"],
        "policy_audit": candidate["policy_audit"],
        "candidate_macro_rewards": candidate["macro_rewards"],
        "baseline_macro_rewards": baseline["macro_rewards"],
        "baseline_policy": "forced_macro0_counterfactual",
        "baseline_policy_audit": baseline["policy_audit"],
        "counterfactual_weight_independence": "macro0 never evaluates network",
        "operational_mode_source": "preregistered_time_of_day",
        "source_manifest_field": "cases[].operational_time_of_day",
        "operational_time_of_day": case["scenario"],
    }


def _refresh_status(run_dir):
    hashes = {}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "status.json":
            hashes[str(path.relative_to(run_dir))] = _sha(path)
    status = json.loads((run_dir / "status.json").read_text())
    status["artifact_sha256"] = hashes
    _write(run_dir / "status.json", status)


def _fixture(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "Fixture")
    _write(root / ".gitignore", "training/\noutput/\n")
    network_path = root / "network.json"
    phase_path = root / "phase-contract.json"
    _write(network_path, {"fixture": "network"})
    _write(phase_path, {"fixture": "phase-contract"})
    nodes = ["node-a", "node-b"]
    scenarios = ("normal", "am_peak", "pm_peak")
    cases = []
    for split, seeds in (("train", (11, 12)),
                         ("validation", (31, 32)),
                         ("test", (101, 102))):
        for seed in seeds:
            for scenario in scenarios:
                path = root / "flows" / ("%s-%s-%s.json" % (split, scenario, seed))
                _write(path, "[]\n")
                cases.append({
                    "case_id": "%s_%s_%s" % (split, scenario, seed),
                    "split": split, "scenario": scenario,
                    "operational_time_of_day": scenario,
                    "flow_path": str(path.relative_to(root)),
                    "flow_sha256": _sha(path),
                })
    manifest = {
        "schema_version": 1,
        "cases": cases,
        "network": {"agent_ids": nodes, "path": "network.json",
                    "sha256": _sha(network_path)},
        "phase_contract": {"path": "phase-contract.json",
                           "sha256": _sha(phase_path)},
        "runtime": {"base_image_digest": "sha256:runtime"},
        "preprocessing": {"count_norm": 20, "capacity_norm": 40},
        "simulation": {"action_interval": 10, "min_green": 20,
                       "maximum_red": 180, "sim_step_seconds": 1},
        "generator_config_sha256": "g" * 64,
    }
    _write(root / "manifest.json", manifest)
    validation = [case for case in cases if case["split"] == "validation"]
    baseline_rows = [dict(
        case_id=case["case_id"], scenario=case["scenario"],
        queue_integral_vehicle_seconds=1000.0,
        completion_rate=0.90, insertion_rate=0.95)
        for case in validation]
    durations = [20, 25, 30, 35, 40, 45, 50, 60]
    baseline = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "binding": _tuning_binding(
            manifest, validation, 3600,
             {"simulation": manifest["simulation"],
              "baseline": {"controller": "validation_tuned_fixed",
                          "search_green_durations": durations}}),
        "search_space": {"fixed_green_duration": durations},
        "selected": {"fixed_green_duration": 25},
        "candidates": [
            {"fixed_green_duration": duration,
             "mean_queue_integral_vehicle_seconds": (
                 1000.0 if duration == 25 else 1100.0),
             "rows": (baseline_rows if duration == 25 else [
                 dict(row, queue_integral_vehicle_seconds=1100.0)
                 for row in baseline_rows])}
            for duration in durations],
    }
    baseline["tuning_sha256"] = canonical_json_sha256(baseline)
    _write(root / "baseline.json", baseline)
    registered_config = (Path(__file__).resolve().parents[2] / "configs" /
                         "haichau_training_v3b_residual.yaml")
    config_bytes = registered_config.read_bytes()
    config_path = root / "configs/haichau_training_v3b_residual.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(config_bytes)
    config = yaml.safe_load(config_bytes)
    spec = {
        "schema_version": 1,
        "decision_type": "haichau_residual_pilot_selection",
        "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11,
        "source_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "validation_checkpoints": ["step-2", "step-4"],
        "ranking": ["mean_peak_queue_regret_percent_ascending",
                    "training_step_ascending"],
        "no_eligible": "fail_closed",
        "gates": {
            "normal_exact_fixed_per_case": True,
            "normal_timeline_zero": [
                "phase_divergence_seconds", "service_divergence_seconds",
                "state_divergence_seconds", "nonzero_macros",
                "illegal_requests", "anchor_violations",
                "unlogged_divergence_seconds"],
            "peak_regime_mean_queue_regret_percent_max": 0.0,
            "mean_peak_queue_regret_percent_max": -1.0,
            "per_case_completion_loss_max": 0.02,
            "per_case_insertion_loss_max": 0.02,
            "learned_macros_required_regimes": ["am_peak", "pm_peak"],
            "minimum_distinct_nonzero_macro_nodes": 2,
            "peak_timeline_zero": ["illegal_requests", "anchor_violations",
                                   "unlogged_divergence_seconds"],
            "forced_macro0_counterfactual_exact_fixed25": True,
            "checkpoint_traffic_feature_response_required": True,
        },
        "manifest": "manifest.json",
        "baseline_tuning_artifact": "baseline.json",
        "arm": {"config": "configs/haichau_training_v3b_residual.yaml",
                "run_dir": "training/pilot"},
        "decision_output": "output/residual-decision.json",
        "selected_config_output": "output/residual-selected.yaml",
        "validation_rerun_output": "output/residual-rerun.json",
    }
    _write(root / "spec.yaml", yaml.safe_dump(spec, sort_keys=True))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture inputs")
    commit = _git(root, "rev-parse", "HEAD")
    source_tree = {
        "schema_version": 1, "git_commit": commit,
        "tracked_worktree": "clean", "index": "clean",
        "untracked_files_policy": "allowed",
    }
    run = root / "training/pilot"
    run.mkdir(parents=True)
    resolved = copy.deepcopy(config)
    resolved.update({"mode": "pilot", "learning_seed": 11,
                     "run": config["tiers"]["pilot"],
                     "source_tree": source_tree,
                     "manifest_sha256": canonical_json_sha256(manifest),
                     "baseline_tuning_sha256": baseline["tuning_sha256"]})
    _write(run / "resolved-config.json", resolved)
    training = [case["case_id"] for case in cases
                if case["split"] == "train" and case["scenario"] != "normal"]
    run_manifest = {
        "schema_version": 1, "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11,
        "manifest_sha256": canonical_json_sha256(manifest),
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "runtime": manifest["runtime"], "code_commit": commit,
        "source_tree": source_tree,
        "foundation_verification": {
            "status": "verified", "network_sha256": manifest["network"]["sha256"],
            "generator_config_sha256": manifest["generator_config_sha256"],
            "runtime_digest": manifest["runtime"]["base_image_digest"]},
        "training_case_ids": training,
        "validation_case_ids": [case["case_id"] for case in validation],
        "test_split_accessed": False,
        "operational_mode": {
            "input": "declared_time_of_day",
            "operational_mode_source": "preregistered_time_of_day",
            "source_manifest_field": "cases[].operational_time_of_day",
            "allowed_values": ["normal", "am_peak", "pm_peak"],
            "inference_inputs": ["current_phase_rows", "current_signal_state",
                                 "elapsed_seconds"],
            "case_id_seed_filename_future_flow_features": False},
        "policy_input_schema": POLICY_INPUT_SCHEMA,
    }
    _write(run / "run-manifest.json", run_manifest)
    _write(run / "baseline-tuning.json", baseline)
    execution_config = copy.deepcopy(config)
    execution_config.update({"mode": "pilot", "learning_seed": 11,
                             "run": config["tiers"]["pilot"]})
    checkpoints = []
    validation_runner = _FixtureValidationRunner(nodes)
    for step in (2, 4):
        contract = {
            "schema_version": 1,
            "controller_family": "schedule_residual_ddqn",
            "feature_dim": len(MACRO_FEATURES),
            "feature_order": MACRO_FEATURES,
            "hidden_size": config["model"]["hidden"],
            "max_macros": MAX_MACROS,
            "macro": config["macro"],
            "normal_policy": "exact_executed_fixed25_from_reset",
            "critic_units": CRITIC_UNITS,
            "policy_input_schema": POLICY_INPUT_SCHEMA,
            "peak_policy": "raw_greedy_prevalidated_macro_with_baseline_tie_break",
            "network_sha256": manifest["network"]["sha256"],
            "phase_contract_sha256": manifest["phase_contract"]["sha256"],
            "simulation": manifest["simulation"],
            "normalization": manifest["preprocessing"],
            "code_commit": commit, "training_step": step,
            "learning_seed": 11, "mode": "pilot",
            "training_config_sha256": canonical_json_sha256(execution_config),
            "baseline_tuning_sha256": baseline["tuning_sha256"],
        }
        checkpoint = run / "checkpoints" / ("step-%04d" % step)
        net = ResidualDDQN(len(MACRO_FEATURES), 64, 0.0003, step,
                           grad_clip=10.0, huber_delta=1.0)
        # Make the policy demonstrably respond to a traffic feature. A clone
        # whose traffic columns are zero is rejected by the selector.
        for name in net.params:
            getattr(net, name)[:] = 0
        net.W1[0, 0] = 1.0
        net.W2[0, 0] = 1.0
        net.W3[0, 0] = 1.0
        net.sync_target()
        net.save_bundle(str(checkpoint), contract)
        checkpoint_record = {
            "contract_path": str((checkpoint / "contract.json").relative_to(run)),
            "contract_sha256": _sha(checkpoint / "contract.json"),
            "weights_path": str((checkpoint / "weights.npz").relative_to(run)),
            "weights_sha256": _sha(checkpoint / "weights.npz"),
        }
        rows = []
        for case in validation:
            candidate = validation_runner(net, step, case, "candidate")
            forced = validation_runner(net, step, case, "forced_macro0")
            rows.append(_row(case, candidate, forced))
        artifact = {
            "schema_version": 1,
            "controller_family": "schedule_residual_ddqn",
            "mode": "pilot", "learning_seed": 11,
            "training_step": step,
            "checkpoint": checkpoint_record,
            "rows": rows,
            "reload_score_identity": True,
        }
        validation_name = "validation-step-%04d.json" % step
        _write(run / validation_name, artifact)
        checkpoints.append({"training_step": step,
                            "validation_path": validation_name,
                            "checkpoint": checkpoint_record})
    _write(run / "learning-curve.json", [{"episode": index}
                                           for index in range(1, 5)])
    _write(run / "summary.json", {
        "schema_version": 1, "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11, "episodes": 4,
        "optimizer_updates": 10,
        "replay_coverage": {"am_peak": 100, "pm_peak": 100},
        "checkpoints": checkpoints, "mean_training_loss": 0.1,
        "wall_time_seconds": 1.0, "test_split_accessed": False,
        "selection": "requires_preregistered_residual_selector",
    })
    _write(run / "status.json", {
        "status": "complete", "source_tree": source_tree,
        "artifact_sha256": {}, "eligible_for_final": False,
        "reason": "pilot must pass preregistered selector",
    })
    _refresh_status(run)
    return root, spec, run, validation_runner


def _mutate_json(path, callback):
    value = json.loads(path.read_text())
    callback(value)
    _write(path, value)


def _set_candidate_queue(row, queue):
    row["candidate"].update({
        "queue_integral_vehicle_seconds": float(queue),
        "network_queue_integral_vehicle_seconds": float(queue) - 10.0,
        "pending_integral_vehicle_seconds": 10.0,
    })
    row["candidate_macro_rewards"] = _rewards(queue)


def test_selects_best_eligible_checkpoint_and_binds_outputs(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, spec, _, runner = _fixture(tmp_path)
    decision = select_from_spec(root, root / "spec.yaml", runner)

    assert decision["status"] == "selected"
    assert decision["winner"]["checkpoint"] == "step-4"
    assert decision["winner"]["training_step"] == 4
    assert decision["winner"]["mean_peak_queue_regret_percent"] == -2.5
    assert decision["ranking"] == spec["ranking"]
    selected = yaml.safe_load((root / spec["selected_config_output"]).read_text())
    assert selected["pilot_selection"]["selected_checkpoint"] == "step-4"
    assert selected["pilot_selection"]["pilot_run_dir"] == spec["arm"]["run_dir"]
    assert selected["pilot_selection"]["decision"]["path"] == spec[
        "decision_output"]
    assert decision["selected_config"]["sha256"] == _sha(
        root / spec["selected_config_output"])


def test_selector_fails_closed_without_deterministic_replay_runner(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="validation runner is required"):
        select_from_spec(root, root / "spec.yaml")


def test_tie_uses_earliest_preregistered_checkpoint(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    step4 = run / "validation-step-0004.json"
    step2 = json.loads((run / "validation-step-0002.json").read_text())
    value = json.loads(step4.read_text())
    value["rows"] = copy.deepcopy(step2["rows"])
    _write(step4, value)
    _refresh_status(run)

    def tied_runner(network, step, case, policy):
        return runner(network, 2 if step == 4 else step, case, policy)

    decision = select_from_spec(root, root / "spec.yaml", tied_runner)

    assert decision["winner"]["checkpoint"] == "step-2"


@pytest.mark.parametrize("mutation, message", [
    ("forged_rank", "ranking"),
    ("missing_trace", "source row|macro events"),
    ("missing_hash", "hashes.*incomplete"),
    ("fixed_only_clone", "traffic feature response"),
    ("one_peak_only", "source row|no eligible"),
    ("one_macro_node", "source row|no eligible"),
    ("checkpoint_mismatch", "training step"),
])
def test_fail_closed_adversarial_evidence(tmp_path, mutation, message):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    if mutation == "forged_rank":
        spec_path = root / "spec.yaml"
        spec = yaml.safe_load(spec_path.read_text())
        spec["ranking"].reverse()
        _write(spec_path, yaml.safe_dump(spec, sort_keys=True))
        _git(root, "add", "spec.yaml")
        _git(root, "commit", "-qm", "forge ranking")
    elif mutation == "missing_trace":
        path = run / "validation-step-0004.json"
        _mutate_json(path, lambda value: value["rows"][0][
            "policy_audit"].pop("macro_events"))
        _refresh_status(run)
    elif mutation == "missing_hash":
        path = run / "status.json"
        _mutate_json(path, lambda value: value["artifact_sha256"].pop(
            "checkpoints/step-0004/weights.npz"))
    elif mutation == "fixed_only_clone":
        for step in (2, 4):
            path = run / "checkpoints" / ("step-%04d" % step) / "weights.npz"
            with np.load(str(path)) as source:
                arrays = {name: source[name].copy() for name in source.files}
            arrays["W1"][:24] = 0
            np.savez(str(path), **arrays)
            contract = path.parent / "contract.json"
            artifact = run / ("validation-step-%04d.json" % step)
            _mutate_json(artifact, lambda value, path=path, contract=contract: value[
                "checkpoint"].update({"weights_sha256": _sha(path),
                                      "contract_sha256": _sha(contract)}))
        summary_path = run / "summary.json"
        summary = json.loads(summary_path.read_text())
        for item in summary["checkpoints"]:
            artifact = json.loads((run / item["validation_path"]).read_text())
            item["checkpoint"] = artifact["checkpoint"]
        _write(summary_path, summary)
        _refresh_status(run)
    elif mutation == "one_peak_only":
        for step in (2, 4):
            path = run / ("validation-step-%04d.json" % step)
            def make_bad(value):
                for row in value["rows"]:
                        if row["scenario"] == "pm_peak":
                            _set_candidate_queue(row, 1010)
            _mutate_json(path, make_bad)
        _refresh_status(run)
    elif mutation == "one_macro_node":
        for step in (2, 4):
            path = run / ("validation-step-%04d.json" % step)
            def one_node(value):
                for row in value["rows"]:
                    if row["scenario"] in ("am_peak", "pm_peak"):
                        audit = row["policy_audit"]
                        for event in audit["macro_events"]:
                            if event["node"] == "node-b" and event["macro_id"]:
                                event.update({"macro_id": 0,
                                              "reason": "baseline_tie_or_best",
                                              "boundary_second": None,
                                              "shift_seconds": 0})
                        audit["nonzero_macros"] = 1
                        audit["nonzero_macro_nodes"] = ["node-a"]
                        audit["abstentions"]["baseline_tie_or_best"] = 23
            _mutate_json(path, one_node)
        _refresh_status(run)
    else:
        path = run / "validation-step-0004.json"
        _mutate_json(path, lambda value: value.update(training_step=2))
        _refresh_status(run)

    with pytest.raises(ValueError, match=message):
        select_from_spec(root, root / "spec.yaml", runner)


def test_rejects_rehashed_forged_source_rows(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "validation-step-0004.json"
    def forge(value):
        row = next(row for row in value["rows"]
                   if row["scenario"] == "normal")
        _set_candidate_queue(row, 999)
    _mutate_json(path, forge)
    _refresh_status(run)

    with pytest.raises(ValueError, match="source row|normal.*exact"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_descendant_rejects_forged_rows_status_rerun_and_decision(tmp_path):
    from traffic_rl.research.pilot_residual_selector import (
        select_from_spec, validate_selected_outputs)

    root, spec, run, runner = _fixture(tmp_path)
    select_from_spec(root, root / "spec.yaml", runner)
    source_path = run / "validation-step-0004.json"
    _mutate_json(source_path, lambda value: _set_candidate_queue(
        next(row for row in value["rows"] if row["scenario"] == "am_peak"),
        900))
    _refresh_status(run)

    rerun_path = root / spec["validation_rerun_output"]
    _mutate_json(rerun_path, lambda value: value["checkpoints"]["step-4"][
        "rows"][1]["candidate"]["metrics"].update(
            queue_integral_vehicle_seconds=900.0,
            network_queue_integral_vehicle_seconds=890.0))
    decision_path = root / spec["decision_output"]
    decision = json.loads(decision_path.read_text())
    decision["pilot_status"]["sha256"] = _sha(run / "status.json")
    decision["checkpoints"]["step-4"]["validation"]["sha256"] = _sha(
        source_path)
    decision["validation_rerun"]["sha256"] = _sha(rerun_path)
    _write(decision_path, decision)

    with pytest.raises(ValueError, match="source row|deterministic|rerun"):
        validate_selected_outputs(root, root / "spec.yaml", runner)


def test_rejects_rehashed_weights_whose_real_policy_chooses_macro0(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "checkpoints/step-0004/weights.npz"
    with np.load(str(path)) as source:
        arrays = {name: source[name].copy() for name in source.files}
    # The checkpoint remains traffic-responsive, but every fixture macro now
    # scores below macro0. The old boolean reload claim would accept this.
    arrays["W3"] *= -1.0
    arrays["target_W3"] *= -1.0
    np.savez(str(path), **arrays)
    artifact_path = run / "validation-step-0004.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["checkpoint"]["weights_sha256"] = _sha(path)
    _write(artifact_path, artifact)
    summary_path = run / "summary.json"
    summary = json.loads(summary_path.read_text())
    next(item for item in summary["checkpoints"]
         if item["training_step"] == 4)["checkpoint"] = artifact["checkpoint"]
    _write(summary_path, summary)
    _refresh_status(run)

    with pytest.raises(ValueError, match="deterministic checkpoint replay"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_rejects_equal_aggregate_normal_with_different_second_timeline(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, _, runner = _fixture(tmp_path)

    def forged_timeline_runner(network, step, case, policy):
        result = runner(network, step, case, policy)
        if case["scenario"] == "normal" and policy == "candidate":
            result["timeline"]["sha256"] = "f" * 64
        return result

    with pytest.raises(ValueError, match="normal candidate per-second timeline"):
        select_from_spec(root, root / "spec.yaml", forged_timeline_runner)


@pytest.mark.parametrize("section,field,value", [
    ("optimizer", "updates_per_macro", 9),
    ("exploration", "epsilon", 0.14),
])
def test_pins_every_registered_config_value_by_full_sha256(
        tmp_path, section, field, value):
    from traffic_rl.research.pilot_residual_selector import validate_registered_config

    root, _, _, _ = _fixture(tmp_path)
    path = root / "configs/haichau_training_v3b_residual.yaml"
    config = yaml.safe_load(path.read_text())
    config[section][field] = value
    _write(path, yaml.safe_dump(config, sort_keys=True))
    spec_path = root / "spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    spec["source_config_sha256"] = _sha(path)
    _write(spec_path, yaml.safe_dump(spec, sort_keys=True))
    _git(root, "add", "configs/haichau_training_v3b_residual.yaml", "spec.yaml")
    _git(root, "commit", "-qm", "forge registered config and hash")

    with pytest.raises(ValueError, match="preregistration|SHA256"):
        validate_registered_config(root, spec_path)


def test_rejects_counterfactual_or_operational_mode_forgery(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "validation-step-0004.json"
    _mutate_json(path, lambda value: value["rows"][0].update(
        counterfactual_weight_independence="claimed only",
        operational_mode_source="case_id"))
    _refresh_status(run)

    with pytest.raises(ValueError, match="counterfactual|operational"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_requires_explicit_manifest_time_of_day_declaration(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, _, runner = _fixture(tmp_path)
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    next(case for case in manifest["cases"]
         if case["split"] == "validation").pop("operational_time_of_day")
    _write(path, manifest)
    _git(root, "add", "manifest.json")
    _git(root, "commit", "-qm", "remove explicit time of day")

    with pytest.raises(ValueError, match="time-of-day"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_rejects_unregistered_config_input_even_when_committed(tmp_path):
    from traffic_rl.research.pilot_residual_selector import validate_registered_config

    root, _, _, _ = _fixture(tmp_path)
    path = root / "configs/haichau_training_v3b_residual.yaml"
    config = yaml.safe_load(path.read_text())
    config["case_id_feature"] = True
    _write(path, yaml.safe_dump(config, sort_keys=True))
    _git(root, "add", "configs/haichau_training_v3b_residual.yaml")
    _git(root, "commit", "-qm", "inject identity feature")

    with pytest.raises(ValueError, match="SHA256|keys|input|identity"):
        validate_registered_config(root, root / "spec.yaml")


def test_rejects_row_whose_network_plus_pending_does_not_equal_queue(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "validation-step-0004.json"
    _mutate_json(path, lambda value: value["rows"][0]["candidate"].update(
        network_queue_integral_vehicle_seconds=1.0,
        pending_integral_vehicle_seconds=1.0))
    _refresh_status(run)

    with pytest.raises(ValueError, match="network.*pending|objective"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_rejects_checkpoint_bundle_hash_or_reload_drift(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "checkpoints/step-0004/weights.npz"
    path.write_bytes(b"forged")
    _refresh_status(run)

    with pytest.raises(ValueError, match="checkpoint.*hash|reload"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_rejects_rehashed_npz_with_uncontracted_array(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, _, run, runner = _fixture(tmp_path)
    path = run / "checkpoints/step-0004/weights.npz"
    with np.load(str(path)) as source:
        arrays = {name: source[name].copy() for name in source.files}
    arrays["uncontracted"] = np.asarray([123])
    np.savez(str(path), **arrays)
    artifact_path = run / "validation-step-0004.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["checkpoint"]["weights_sha256"] = _sha(path)
    _write(artifact_path, artifact)
    summary_path = run / "summary.json"
    summary = json.loads(summary_path.read_text())
    next(item for item in summary["checkpoints"]
         if item["training_step"] == 4)["checkpoint"] = artifact["checkpoint"]
    _write(summary_path, summary)
    _refresh_status(run)

    with pytest.raises(ValueError, match="NPZ.*fields|uncontracted"):
        select_from_spec(root, root / "spec.yaml", runner)


def test_descendant_validator_recomputes_source_rows_and_hashes(tmp_path):
    from traffic_rl.research.pilot_residual_selector import (
        select_from_spec, validate_selected_outputs)

    root, spec, run, runner = _fixture(tmp_path)
    select_from_spec(root, root / "spec.yaml", runner)
    _write(root / "descendant.txt", "new release code\n")
    _git(root, "add", "descendant.txt")
    _git(root, "commit", "-qm", "descendant")

    evidence = validate_selected_outputs(root, root / "spec.yaml", runner)
    assert evidence["status"] == "selected"
    assert evidence["winner"]["checkpoint"] == "step-4"

    path = run / "validation-step-0004.json"
    _mutate_json(path, lambda value: _set_candidate_queue(value["rows"][1], 900))
    _refresh_status(run)
    with pytest.raises(ValueError, match="selected decision drift|source row"):
        validate_selected_outputs(root, root / "spec.yaml", runner)


def test_no_eligible_writes_rejection_but_no_selected_config(tmp_path):
    from traffic_rl.research.pilot_residual_selector import select_from_spec

    root, spec, run, runner = _fixture(tmp_path)
    for step in (2, 4):
        path = run / ("validation-step-%04d.json" % step)
        def degrade(value):
            for row in value["rows"]:
                if row["scenario"] != "normal":
                    _set_candidate_queue(row, 1100)
        _mutate_json(path, degrade)
    _refresh_status(run)

    def degraded_runner(network, step, case, policy):
        result = runner(network, step, case, policy)
        if policy == "candidate" and case["scenario"] != "normal":
            result["metrics"] = _metric(1100)
            result["macro_rewards"] = _rewards(1100)
        return result

    with pytest.raises(ValueError, match="no eligible"):
        select_from_spec(root, root / "spec.yaml", degraded_runner)
    decision = json.loads((root / spec["decision_output"]).read_text())
    assert decision["status"] == "rejected"
    assert decision["winner"] is None
    assert not (root / spec["selected_config_output"]).exists()


def test_cli_is_directly_invocable():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        ["python3", "scripts/select_haichau_residual_pilot.py", "--help"],
        cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
    assert completed.returncode == 0, completed.stderr
    assert "residual" in completed.stdout.lower()


def test_registered_residual_selector_and_config_are_preregistered():
    from traffic_rl.research.pilot_residual_selector import validate_registered_config

    root = Path(__file__).resolve().parents[2]
    evidence = validate_registered_config(
        root, root / "configs/haichau_residual_pilot_selection_v1.yaml")
    assert evidence["pilot_tier"] == {
        "episodes": 4, "horizon_seconds": 3600, "eval_every": 2}
    assert evidence["feature_dim"] == 27
    assert evidence["operational_mode_source"] == "declared_time_of_day"


def test_selector_v2_binds_explicit_safety_config(tmp_path):
    """A repair cohort may bind a new preregistered source config explicitly."""
    from traffic_rl.research import pilot_residual_selector as selector

    config = tmp_path / "configs" / "haichau_training_v3c_residual_safety.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("schema_version: 1\n")
    spec = {
        "schema_version": 2,
        "decision_type": "haichau_residual_pilot_selection",
        "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11,
        "validation_checkpoints": ["step-2", "step-4"],
        "ranking": list(selector._RANKING), "no_eligible": "fail_closed",
        "gates": selector._GATES,
        "arm": {"config": "configs/haichau_training_v3c_residual_safety.yaml",
                "run_dir": "results/pilot"},
        "source_config_sha256": _sha(config),
        "manifest": "manifest.json",
        "baseline_tuning_artifact": "baseline.json",
        "decision_output": "decision.json",
        "selected_config_output": "selected.yaml",
        "validation_rerun_output": "rerun.json",
    }
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False))
    path, loaded = selector._validate_spec(tmp_path, spec_path)
    assert path == spec_path
    assert loaded["arm"]["config"].endswith("v3c_residual_safety.yaml")
