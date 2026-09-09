"""Fail-closed V3-B residual pilot checkpoint selection.

The selector loads preregistered training artifacts, reruns all six validation
cases from both checkpoint bundles, and recomputes every gate and ranking.  It
never opens a held-out flow file.
"""
import copy
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
import yaml

from traffic_rl.agents.schedule_residual import (
    CRITIC_UNITS, MACRO_FEATURES, MAX_MACROS, POLICY_INPUT_SCHEMA,
    ResidualDDQN)
from traffic_rl.research.artifacts import sha256_file
from traffic_rl.sim.schedule_residual import signal_state
from traffic_rl.train.network_trainer import (
    _assert_rollout_complete, _close, _rollout, _tracked_tree_attestation,
    _tuning_binding, _validate_precomputed_tuning, canonical_json_sha256)
from traffic_rl.train.schedule_residual_trainer import (
    OPERATIONAL_MODE, _summary_metrics, operational_time_of_day,
    run_macro_episode)


_CHECKPOINTS = ("step-2", "step-4")
_SCENARIOS = ("normal", "am_peak", "pm_peak")
_RANKING = ("mean_peak_queue_regret_percent_ascending",
            "training_step_ascending")
_NORMAL_ZERO = (
    "phase_divergence_seconds", "service_divergence_seconds",
    "state_divergence_seconds", "nonzero_macros", "illegal_requests",
    "anchor_violations", "unlogged_divergence_seconds")
_PEAK_ZERO = ("illegal_requests", "anchor_violations",
              "unlogged_divergence_seconds")
_COUNTERFACTUAL = "macro0 never evaluates network"
_REGISTERED_CONFIG_PATH = "configs/haichau_training_v3b_residual.yaml"
_REGISTERED_CONFIG_SHA256 = (
    "8195782b5d099bd7a04de03bfebfd5206957e7d76ada354047c971cbb3d6e75a")
_RERUN_PROTOCOL = "deterministic_cityflow_checkpoint_replay_v1"
_TIMELINE_DEFINITION = (
    "canonical_json_lines(second,node,served_lightphase,signal_state)_v1")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRAFFIC_FEATURE_SUFFIXES = {
    "incoming_queue_mean", "incoming_queue_max", "incoming_running_mean",
    "outgoing_queue_mean", "outgoing_remaining_capacity_mean", "pressure",
    "upstream_queue_mean", "downstream_queue_mean"}
_GATES = {
    "normal_exact_fixed_per_case": True,
    "normal_timeline_zero": list(_NORMAL_ZERO),
    "peak_regime_mean_queue_regret_percent_max": 0.0,
    "mean_peak_queue_regret_percent_max": -1.0,
    "per_case_completion_loss_max": 0.02,
    "per_case_insertion_loss_max": 0.02,
    "learned_macros_required_regimes": ["am_peak", "pm_peak"],
    "minimum_distinct_nonzero_macro_nodes": 2,
    "peak_timeline_zero": list(_PEAK_ZERO),
    "forced_macro0_counterfactual_exact_fixed25": True,
    "checkpoint_traffic_feature_response_required": True,
}


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _yaml(path, label):
    try:
        value = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is not valid YAML: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a YAML mapping" % label)
    return value


def _inside(root, relative, label):
    value = Path(relative)
    if value.is_absolute():
        raise ValueError("%s must be repository-relative" % label)
    root = Path(root).resolve()
    result = (root / value).resolve()
    try:
        result.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    return result


def _record(root, path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return {"path": str(path.resolve().relative_to(Path(root).resolve())),
            "sha256": sha256_file(path)}


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_yaml(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, default_flow_style=False,
                                   sort_keys=True))


def _committed_file_sha256(root, commit, relative):
    """Hash a file exactly as stored at a declared Git commit."""
    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "show", "%s:%s" % (commit, relative)],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        raise ValueError("registered source file is absent from commit: %s" %
                         exc.output.decode("utf-8", "replace"))
    return hashlib.sha256(value).hexdigest()


def _frozen_file_record(root, commit, relative, expected_sha256, label):
    path = _inside(root, relative, label)
    if not path.is_file() or sha256_file(path) != expected_sha256:
        raise ValueError("%s differs from declared SHA256" % label)
    if _committed_file_sha256(root, commit, relative) != expected_sha256:
        raise ValueError("%s differs from source commit" % label)
    return {"path": relative, "sha256": expected_sha256,
            "git_commit": commit}


def _frozen_simulation_inputs(root, commit, manifest, validation):
    records = {}
    for key, label in (("network", "road network"),
                       ("phase_contract", "phase contract")):
        value = manifest.get(key)
        if (not isinstance(value, dict)
                or not isinstance(value.get("path"), str)
                or not _SHA256.match(str(value.get("sha256") or ""))):
            raise ValueError("%s manifest binding is incomplete" % label)
        records[key] = _frozen_file_record(
            root, commit, value["path"], value["sha256"], label)
    flow_records = []
    for case in validation:
        relative, digest = case.get("flow_path"), case.get("flow_sha256")
        if not isinstance(relative, str) or not _SHA256.match(str(digest or "")):
            raise ValueError("validation flow binding is incomplete")
        record = _frozen_file_record(
            root, commit, relative, digest,
            "validation flow " + case["case_id"])
        record["case_id"] = case["case_id"]
        flow_records.append(record)
    records["validation_flows"] = flow_records
    return records


def _number(value, label, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError("%s must be numeric" % label)
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be numeric" % label)
    if not math.isfinite(result):
        raise ValueError("%s must be finite" % label)
    if minimum is not None and result < minimum:
        raise ValueError("%s is below its minimum" % label)
    if maximum is not None and result > maximum:
        raise ValueError("%s exceeds its maximum" % label)
    return result


def _integer(value, label, minimum=0):
    number = _number(value, label, minimum)
    if int(number) != number:
        raise ValueError("%s must be an integer" % label)
    return int(number)


def _at_most(value, maximum):
    return value <= maximum + 1e-12


def _validate_spec(root, spec_path):
    supplied = Path(spec_path)
    if supplied.is_absolute():
        try:
            supplied = supplied.resolve().relative_to(Path(root).resolve())
        except ValueError:
            raise ValueError("residual pilot selector specification must remain inside the project")
    path = _inside(root, supplied, "residual pilot selector specification")
    spec = _yaml(path, "residual pilot selector specification")
    expected = {
        "schema_version": 1,
        "decision_type": "haichau_residual_pilot_selection",
        "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11,
        "validation_checkpoints": list(_CHECKPOINTS),
        "ranking": list(_RANKING), "no_eligible": "fail_closed",
        "gates": _GATES,
    }
    for field, value in expected.items():
        if spec.get(field) != value:
            raise ValueError("residual pilot selector %s differs from preregistration" % field)
    arm = spec.get("arm")
    if not isinstance(arm, dict) or set(arm) != {"config", "run_dir"} \
            or not all(isinstance(arm.get(field), str)
                       for field in ("config", "run_dir")):
        raise ValueError("residual pilot selector arm is invalid")
    if arm["config"] != _REGISTERED_CONFIG_PATH:
        raise ValueError("residual pilot selector config path differs from preregistration")
    if spec.get("source_config_sha256") != _REGISTERED_CONFIG_SHA256:
        raise ValueError("residual pilot selector config SHA256 differs from preregistration")
    for field in ("manifest", "baseline_tuning_artifact", "decision_output",
                  "selected_config_output", "validation_rerun_output"):
        if not isinstance(spec.get(field), str):
            raise ValueError("residual pilot selector requires %s" % field)
    outputs = (spec["decision_output"], spec["selected_config_output"],
               spec["validation_rerun_output"])
    if len(set(outputs)) != len(outputs):
        raise ValueError("residual selector outputs must be distinct")
    return path, spec


def _validate_config(config):
    expected_keys = {
        "schema_version", "controller_family", "macro", "operational_mode",
        "model", "optimizer", "exploration", "reward", "critic_units",
        "baseline", "tiers"}
    if set(config) != expected_keys:
        raise ValueError("residual source config keys include an unregistered input")
    if (config.get("schema_version") != 1
            or config.get("controller_family") != "schedule_residual_ddqn"
            or config.get("macro") != {
                "duration_seconds": 300, "shift_seconds": 10,
                "baseline_green_seconds": 25}
            or config.get("operational_mode") != OPERATIONAL_MODE
            or config.get("reward") != {
                "type": "negative_network_queue_plus_pending_integral"}
            or config.get("critic_units") != CRITIC_UNITS):
        raise ValueError("residual source config contract drift")
    model = config.get("model", {})
    if (set(model) != {"feature_dim", "hidden", "lr", "gamma_per_macro"}
            or model.get("feature_dim") != len(MACRO_FEATURES)
            or model.get("gamma_per_macro") != 0.99):
        raise ValueError("residual source config model contract drift")
    if set(config.get("optimizer", {})) != {
            "batch_size", "buffer_capacity", "train_start",
            "updates_per_macro", "target_sync", "grad_clip", "huber_delta"} \
            or set(config.get("exploration", {})) != {"epsilon"} \
            or set(config.get("baseline", {})) != {
                "controller", "search_green_durations"} \
            or set(config.get("tiers", {})) != {"smoke", "pilot"}:
        raise ValueError("residual source config nested keys drift")
    if config.get("tiers", {}).get("pilot") != {
            "episodes": 4, "horizon_seconds": 3600, "eval_every": 2}:
        raise ValueError("residual pilot tier must be four full-hour episodes with eval2/4")
    forbidden = set(OPERATIONAL_MODE["forbidden_features"])
    learned = set(POLICY_INPUT_SCHEMA["learned_features"])
    if forbidden.intersection(learned) or config["operational_mode"].get(
            "input") != "declared_time_of_day":
        raise ValueError("residual policy config leaks case identity or future demand")


def validate_registered_config(root, spec_path):
    """Validate the preregistered V3-B config without reading pilot outcomes."""
    root = Path(root).resolve()
    _, spec = _validate_spec(root, spec_path)
    path = _inside(root, spec["arm"]["config"], "residual source config")
    if sha256_file(path) != _REGISTERED_CONFIG_SHA256:
        raise ValueError("residual source config differs from preregistered full SHA256")
    config = _yaml(path, "residual source config")
    _validate_config(config)
    return {
        "config": _record(root, path, "residual source config"),
        "pilot_tier": copy.deepcopy(config["tiers"]["pilot"]),
        "feature_dim": config["model"]["feature_dim"],
        "operational_mode_source": config["operational_mode"]["input"],
    }


def _manifest_cases(manifest):
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("experiment manifest cases are invalid")
    validation = [case for case in cases if isinstance(case, dict)
                  and case.get("split") == "validation"]
    if len(validation) != 6:
        raise ValueError("residual selection requires six validation cases")
    if any(case.get("scenario") not in _SCENARIOS or
           case.get("operational_time_of_day") != case.get("scenario")
           for case in validation):
        raise ValueError("validation operational time-of-day declaration is invalid")
    counts = dict((scenario, sum(case.get("scenario") == scenario
                                 for case in validation))
                  for scenario in _SCENARIOS)
    ids = [case.get("case_id") for case in validation]
    if counts != {"normal": 2, "am_peak": 2, "pm_peak": 2} \
            or any(not isinstance(case_id, str) or not case_id for case_id in ids) \
            or len(set(ids)) != 6:
        raise ValueError("validation case enumeration is invalid")
    train_ids = [case.get("case_id") for case in cases
                 if isinstance(case, dict) and case.get("split") == "train"
                 and case.get("scenario") in ("am_peak", "pm_peak")]
    if not train_ids:
        raise ValueError("residual manifest has no peak training cases")
    return validation, train_ids


def _baseline_rows(baseline, validation, config, manifest):
    baseline_config = {"baseline": config["baseline"],
                       "simulation": manifest["simulation"]}
    _validate_precomputed_tuning(
        baseline, _tuning_binding(manifest, validation, 3600,
                                  baseline_config),
        baseline_config, validation)
    if (baseline.get("schema_version") != 1
            or baseline.get("method") != "validation_grid_search"):
        raise ValueError("baseline tuning schema is invalid")
    unsigned = dict((key, value) for key, value in baseline.items()
                    if key != "tuning_sha256")
    if baseline.get("tuning_sha256") != canonical_json_sha256(unsigned):
        raise ValueError("baseline tuning hash drift")
    if baseline.get("selected", {}).get("fixed_green_duration") != 25:
        raise ValueError("residual pilot requires validation-selected fixed25")
    matches = [item for item in baseline.get("candidates", [])
               if isinstance(item, dict)
               and item.get("fixed_green_duration") == 25]
    if len(matches) != 1 or not isinstance(matches[0].get("rows"), list):
        raise ValueError("fixed25 baseline rows are invalid")
    rows = matches[0]["rows"]
    expected = dict((case["case_id"], case["scenario"])
                    for case in validation)
    if len(rows) != 6:
        raise ValueError("fixed25 baseline must contain six validation rows")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("case_id") in result \
                or expected.get(row.get("case_id")) != row.get("scenario"):
            raise ValueError("fixed25 baseline case identity drift")
        for field in ("queue_integral_vehicle_seconds", "completion_rate",
                      "insertion_rate"):
            _number(row.get(field), "fixed25 baseline " + field, 0.0)
        result[row["case_id"]] = row
    if set(result) != set(expected):
        raise ValueError("fixed25 baseline case set drift")
    return result


def _validate_status(run_dir, required, source_tree):
    status = _json(run_dir / "status.json", "residual pilot status")
    if (set(status) != {"status", "source_tree", "artifact_sha256",
                        "eligible_for_final", "reason"}
            or status.get("status") != "complete"
            or status.get("eligible_for_final") is not False
            or status.get("reason") != "pilot must pass preregistered selector"
            or status.get("source_tree") != source_tree):
        raise ValueError("residual pilot status or source provenance drift")
    hashes = status.get("artifact_sha256")
    if not isinstance(hashes, dict) or not set(required).issubset(hashes):
        raise ValueError("residual pilot status hashes are incomplete")
    for relative, digest in hashes.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not path.parts \
                or not _SHA256.match(str(digest or "")):
            raise ValueError("residual pilot status hash record is invalid")
        artifact = run_dir / path
        if not artifact.is_file() or sha256_file(artifact) != digest:
            raise ValueError("residual pilot artifact hash drift: %s" % relative)
    return status


def _expected_contract(config, manifest, baseline, source_tree, step):
    execution = copy.deepcopy(config)
    execution.update({"mode": "pilot", "learning_seed": 11,
                      "run": copy.deepcopy(config["tiers"]["pilot"])})
    return {
        "schema_version": 1,
        "controller_family": "schedule_residual_ddqn",
        "feature_dim": len(MACRO_FEATURES), "feature_order": MACRO_FEATURES,
        "hidden_size": config["model"]["hidden"], "max_macros": MAX_MACROS,
        "macro": config["macro"],
        "normal_policy": "exact_executed_fixed25_from_reset",
        "critic_units": CRITIC_UNITS,
        "policy_input_schema": POLICY_INPUT_SCHEMA,
        "peak_policy": "raw_greedy_prevalidated_macro_with_baseline_tie_break",
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "simulation": manifest["simulation"],
        "normalization": manifest["preprocessing"],
        "code_commit": source_tree["git_commit"], "training_step": step,
        "learning_seed": 11, "mode": "pilot",
        "training_config_sha256": canonical_json_sha256(execution),
        "baseline_tuning_sha256": baseline["tuning_sha256"],
    }


def _checkpoint_record(run_dir, checkpoint):
    directory = run_dir / "checkpoints" / ("step-%04d" % checkpoint)
    return {
        "contract_path": str((directory / "contract.json").relative_to(run_dir)),
        "contract_sha256": sha256_file(directory / "contract.json"),
        "weights_path": str((directory / "weights.npz").relative_to(run_dir)),
        "weights_sha256": sha256_file(directory / "weights.npz"),
    }


def _traffic_feature_response(network):
    responses = []
    indices = [index for index, name in enumerate(MACRO_FEATURES[:-3])
               if any(name == prefix + suffix for prefix in ("source_", "target_")
                      for suffix in _TRAFFIC_FEATURE_SUFFIXES)]
    descriptors = ((0.0, 0.0, 1.0), (0.5, 1.0, 0.0))
    for index in indices:
        maximum = 0.0
        for base_value in (0.0, 0.25, 0.75):
            for descriptor in descriptors:
                low = np.full((1, len(MACRO_FEATURES)), base_value,
                              np.float32)
                high = low.copy()
                low[0, -3:], high[0, -3:] = descriptor, descriptor
                low[0, index], high[0, index] = 0.0, 1.0
                first = float(network.q_values(low, [True])[0, 0])
                second = float(network.q_values(high, [True])[0, 0])
                difference = abs(second - first)
                if not math.isfinite(difference):
                    raise ValueError("checkpoint traffic feature response is nonfinite")
                maximum = max(maximum, difference)
        if maximum > 1e-8:
            responses.append({"feature": MACRO_FEATURES[index],
                              "absolute_score_response": maximum})
    if not responses:
        raise ValueError("checkpoint has no traffic feature response; fixed-only clone rejected")
    return {"responsive_feature_count": len(responses),
            "maximum_absolute_score_response": max(
                item["absolute_score_response"] for item in responses),
            "responsive_features": [item["feature"] for item in responses]}


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError("timeline value is not JSON serializable")


class _TimelineDigest(object):
    """Streaming digest of every exposed signal state at every second."""
    def __init__(self):
        self.digest = hashlib.sha256()
        self.observed_node_seconds = 0

    def observe(self, env):
        for node in env.agent_ids:
            frame = {
                "second": int(env._t), "node": node,
                "served_lightphase": int(env._last_step_lightphases[node]),
                "signal_state": signal_state(env, node),
            }
            encoded = json.dumps(
                frame, sort_keys=True, separators=(",", ":"),
                allow_nan=False, default=_json_default).encode("utf-8") + b"\n"
            self.digest.update(encoded)
            self.observed_node_seconds += 1

    def record(self):
        return {
            "schema_version": 1,
            "frame_definition": _TIMELINE_DEFINITION,
            "observed_node_seconds": self.observed_node_seconds,
            "sha256": self.digest.hexdigest(),
        }


def make_env_validation_runner(env_factory):
    """Create the deterministic checkpoint replay used by the release CLI."""
    if not callable(env_factory):
        raise ValueError("validation environment factory must be callable")

    def runner(network, training_step, case, policy):
        del training_step
        env = env_factory(case, 3600)
        timeline = _TimelineDigest()
        prior = getattr(env, "signal_observer", None)

        def observer(observed):
            if prior is not None:
                prior(observed)
            timeline.observe(observed)

        env.signal_observer = observer
        try:
            if policy == "candidate":
                info = run_macro_episode(
                    env, network, operational_time_of_day(case), epsilon=0.0,
                    seed=0)
                result = {
                    "metrics": _summary_metrics(info),
                    "macro_rewards": info.get("macro_rewards"),
                    "policy_audit": info.get("policy_audit"),
                }
            elif policy == "forced_macro0":
                info = run_macro_episode(
                    env, network, operational_time_of_day(case), epsilon=0.0,
                    seed=0, zero_residual=True)
                result = {
                    "metrics": _summary_metrics(info),
                    "macro_rewards": info.get("macro_rewards"),
                    "policy_audit": info.get("policy_audit"),
                }
            elif policy == "fixed25":
                info = _rollout(env, None, fixed_green_duration=25,
                                action_interval=10)
                result = {"metrics": _summary_metrics(info)}
            else:
                raise ValueError("unknown validation replay policy")
            _assert_rollout_complete(
                info, 3600, "%s replay %s" % (policy, case["case_id"]))
            result["timeline"] = timeline.record()
            return result
        finally:
            _close(env)

    return runner


def _validate_loaded_network(network, config):
    if (network.feature_dim != len(MACRO_FEATURES)
            or network.hidden != config["model"]["hidden"]
            or network.lr != config["model"]["lr"]
            or network.grad_clip != config["optimizer"]["grad_clip"]
            or network.huber_delta != config["optimizer"]["huber_delta"]):
        raise ValueError("checkpoint NPZ optimizer metadata differs from source config")
    for name in network.params:
        if (not np.all(np.isfinite(getattr(network, name)))
                or not np.all(np.isfinite(getattr(network, "t" + name)))):
            raise ValueError("checkpoint NPZ contains nonfinite parameters")


def _validate_npz_fields(path):
    params = ("W1", "b1", "W2", "b2", "W3", "b3")
    expected = set(params)
    expected.update("target_" + name for name in params)
    expected.update(("meta_feature_dim", "meta_hidden", "meta_lr",
                     "meta_grad_clip", "meta_huber_delta",
                     "meta_critic_vehicle_seconds_per_unit"))
    try:
        with np.load(str(path)) as source:
            fields = set(source.files)
    except (IOError, OSError, ValueError) as exc:
        raise ValueError("checkpoint NPZ cannot be read: %s" % exc)
    if fields != expected:
        raise ValueError("checkpoint NPZ fields are uncontracted or incomplete")


def _validate_rewards(records, metrics, label):
    if not isinstance(records, list) or len(records) != 12:
        raise ValueError("%s macro reward trace must contain twelve blocks" % label)
    objective = 0.0
    starts = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {
                "block_start_second", "duration_seconds",
                "raw_objective_vehicle_seconds", "raw_reward_vehicle_seconds",
                "scaled_reward", "network_queue_vehicle_seconds",
                "entry_pending_vehicle_seconds"}:
            raise ValueError("%s macro reward record is invalid" % label)
        start = _integer(record.get("block_start_second"), label + " block start")
        duration = _integer(record.get("duration_seconds"), label + " duration", 1)
        raw = _number(record.get("raw_objective_vehicle_seconds"),
                      label + " raw objective", 0.0)
        reward = _number(record.get("raw_reward_vehicle_seconds"),
                         label + " raw reward")
        scaled = _number(record.get("scaled_reward"), label + " scaled reward")
        network = _number(record.get("network_queue_vehicle_seconds"),
                          label + " network queue", 0.0)
        pending = _number(record.get("entry_pending_vehicle_seconds"),
                          label + " entry pending", 0.0)
        if duration != 300 or not math.isclose(raw, network + pending,
                                               rel_tol=1e-12, abs_tol=1e-8) \
                or not math.isclose(reward, -raw, rel_tol=1e-12, abs_tol=1e-8) \
                or not math.isclose(scaled, -raw / 100000.0,
                                    rel_tol=1e-12, abs_tol=1e-10):
            raise ValueError("%s macro reward contract drift" % label)
        objective += raw
        starts.append(start)
    if starts != list(range(0, 3600, 300)) or not math.isclose(
            objective, float(metrics["queue_integral_vehicle_seconds"]),
            rel_tol=1e-12, abs_tol=1e-6):
        raise ValueError("%s macro rewards do not reconstruct source row" % label)


def _validate_audit(audit, scenario, nodes, horizon, baseline=False):
    label = ("forced macro0" if baseline else "candidate") + " timeline audit"
    if not isinstance(audit, dict):
        raise ValueError("%s is invalid" % label)
    if "macro_events" not in audit:
        raise ValueError("%s macro events are missing" % label)
    if set(audit) != {
            "observed_node_seconds", "phase_divergence_seconds",
            "service_divergence_seconds", "state_divergence_seconds",
            "nonzero_macros", "illegal_requests", "anchor_violations",
            "unlogged_divergence_seconds", "resync_successes", "time_of_day",
            "macro_events", "nonzero_macro_nodes", "abstentions",
            "phase_definition", "service_definition"}:
        raise ValueError("%s fields drift" % label)
    if audit.get("time_of_day") != scenario:
        raise ValueError("%s time-of-day drift" % label)
    if (audit.get("phase_definition") !=
            "lightphase_exposed_during_simulator_step"
            or audit.get("service_definition") !=
            "movement_time_since_service_divergence"):
        raise ValueError("%s definitions are incomplete" % label)
    expected_observations = len(nodes) * horizon
    if _integer(audit.get("observed_node_seconds"), label + " observations") \
            != expected_observations:
        raise ValueError("%s does not cover every signal-second" % label)
    for field in ("phase_divergence_seconds", "service_divergence_seconds",
                  "state_divergence_seconds", "nonzero_macros",
                  "illegal_requests", "anchor_violations",
                  "unlogged_divergence_seconds", "resync_successes"):
        _integer(audit.get(field), label + " " + field)
    events = audit.get("macro_events")
    expected_pairs = [(block, node) for block in range(0, horizon, 300)
                      for node in nodes]
    if not isinstance(events, list) or len(events) != len(expected_pairs):
        raise ValueError("%s macro events are missing or incomplete" % label)
    observed_pairs, active_nodes, nonzero, abstentions = [], set(), 0, {}
    for event in events:
        if not isinstance(event, dict) or set(event) != {
                "node", "block_start_second", "macro_id", "reason",
                "boundary_second", "shift_seconds"}:
            raise ValueError("%s macro events are invalid" % label)
        pair = (event.get("block_start_second"), event.get("node"))
        observed_pairs.append(pair)
        macro = _integer(event.get("macro_id"), label + " macro id")
        if macro >= MAX_MACROS:
            raise ValueError("%s macro id is outside checkpoint contract" % label)
        if macro:
            nonzero += 1
            active_nodes.add(event.get("node"))
            if event.get("reason") != "learned_macro":
                raise ValueError("%s nonzero macro is not a learned action" % label)
            boundary = _integer(event.get("boundary_second"),
                                label + " learned boundary")
            if (boundary < pair[0] or boundary >= pair[0] + 300
                    or event.get("shift_seconds") not in (-10, 10)):
                raise ValueError("%s learned macro descriptor drift" % label)
        else:
            reason = event.get("reason")
            abstentions[reason] = abstentions.get(reason, 0) + 1
            if baseline and reason != (
                    "normal_exact_reference" if scenario == "normal"
                    else "zero_residual_diagnostic"):
                raise ValueError("forced macro0 event reason drift")
            if not baseline and scenario == "normal" \
                    and reason != "normal_exact_reference":
                raise ValueError("normal exact reference event reason drift")
            if event.get("boundary_second") is not None \
                    or event.get("shift_seconds") != 0:
                raise ValueError("%s macro0 event descriptor drift" % label)
    if observed_pairs != expected_pairs:
        raise ValueError("%s macro events do not cover exact node/block order" % label)
    if audit.get("nonzero_macros") != nonzero \
            or audit.get("nonzero_macro_nodes") != sorted(active_nodes):
        raise ValueError("%s nonzero macro counters do not match events" % label)
    if audit.get("abstentions") != abstentions:
        raise ValueError("%s abstention counters do not match events" % label)
    if audit.get("resync_successes") != len(nodes) * (horizon // 300):
        raise ValueError("%s does not prove every terminal resynchronization" % label)
    zeros = _NORMAL_ZERO if baseline or scenario == "normal" else _PEAK_ZERO
    if any(audit.get(field) != 0 for field in zeros):
        raise ValueError("%s required zero field is nonzero" % label)
    return active_nodes, nonzero


def _validate_metric(metric, label):
    if not isinstance(metric, dict) or set(metric) != {
            "queue_integral_vehicle_seconds",
            "network_queue_integral_vehicle_seconds",
            "pending_integral_vehicle_seconds", "completion_rate",
            "insertion_rate", "phase_switches", "max_red_seconds", "step",
            "scheduled", "due", "inserted", "arrived", "running", "pending"}:
        raise ValueError("%s metrics are invalid" % label)
    queue = _number(metric.get("queue_integral_vehicle_seconds"),
                    label + " queue", 0.0)
    network = _number(metric.get("network_queue_integral_vehicle_seconds"),
                      label + " network queue", 0.0)
    pending = _number(metric.get("pending_integral_vehicle_seconds"),
                      label + " pending", 0.0)
    if not math.isclose(queue, network + pending, rel_tol=1e-12,
                        abs_tol=1e-6):
        raise ValueError("%s network queue plus pending differs from objective" % label)
    return {
        "queue": queue,
        "completion": _number(metric.get("completion_rate"),
                              label + " completion", 0.0, 1.0),
        "insertion": _number(metric.get("insertion_rate"),
                             label + " insertion", 0.0, 1.0),
    }


def _validate_timeline(value, nodes, horizon, label):
    if (not isinstance(value, dict)
            or set(value) != {"schema_version", "frame_definition",
                              "observed_node_seconds", "sha256"}
            or value.get("schema_version") != 1
            or value.get("frame_definition") != _TIMELINE_DEFINITION
            or not _SHA256.match(str(value.get("sha256") or ""))):
        raise ValueError("%s per-second timeline digest is invalid" % label)
    if _integer(value.get("observed_node_seconds"), label + " observations") \
            != len(nodes) * horizon:
        raise ValueError("%s per-second timeline is incomplete" % label)
    return copy.deepcopy(value)


def _run_replay(validation_runner, network, step, case, policy):
    if not callable(validation_runner):
        raise ValueError("deterministic validation runner is required")
    try:
        result = validation_runner(network, step, copy.deepcopy(case), policy)
    except Exception as exc:
        raise ValueError("deterministic validation replay failed for %s/%s: %s" %
                         (case.get("case_id"), policy, exc))
    expected = ({"metrics", "timeline"} if policy == "fixed25" else
                {"metrics", "macro_rewards", "policy_audit", "timeline"})
    if not isinstance(result, dict) or set(result) != expected:
        raise ValueError("deterministic validation replay result fields drift")
    return copy.deepcopy(result)


def _replay_checkpoint(validation_runner, network, step, rows, validation,
                       tuned_rows, nodes, prior_baselines, fixed25):
    """Recompute source rows and bind metrics/actions to loaded weights."""
    by_case = dict((row.get("case_id"), row) for row in rows
                   if isinstance(row, dict))
    replay_rows, baselines = [], {}
    for case in validation:
        case_id, scenario = case["case_id"], case["scenario"]
        source = by_case.get(case_id)
        if source is None:
            raise ValueError("deterministic replay source row is missing")
        candidate = _run_replay(
            validation_runner, network, step, case, "candidate")
        baseline = _run_replay(
            validation_runner, network, step, case, "forced_macro0")
        if case_id not in fixed25:
            fixed25[case_id] = _run_replay(
                validation_runner, network, step, case, "fixed25")
        fixed = fixed25[case_id]
        for label, result in (("candidate", candidate),
                              ("forced macro0", baseline),
                              ("fixed25", fixed)):
            _validate_metric(result.get("metrics"), label + " replay")
            _validate_timeline(
                result.get("timeline"), nodes, 3600, label + " replay")
        if candidate["metrics"] != source.get("candidate") \
                or candidate["macro_rewards"] != source.get(
                    "candidate_macro_rewards") \
                or candidate["policy_audit"] != source.get("policy_audit"):
            raise ValueError(
                "candidate source row differs from deterministic checkpoint replay")
        if baseline["metrics"] != source.get("baseline") \
                or baseline["macro_rewards"] != source.get(
                    "baseline_macro_rewards") \
                or baseline["policy_audit"] != source.get(
                    "baseline_policy_audit"):
            raise ValueError(
                "forced macro0 source row differs from deterministic replay")
        tuned = tuned_rows[case_id]
        for field in ("queue_integral_vehicle_seconds", "completion_rate",
                      "insertion_rate"):
            if fixed["metrics"][field] != tuned[field]:
                raise ValueError("fixed25 replay differs from frozen tuning row")
        if baseline["metrics"] != fixed["metrics"] \
                or baseline["timeline"] != fixed["timeline"]:
            raise ValueError(
                "forced macro0 per-second timeline or metrics differ from fixed25")
        if scenario == "normal" and (
                candidate["metrics"] != fixed["metrics"]
                or candidate["timeline"] != fixed["timeline"]):
            raise ValueError(
                "normal candidate per-second timeline or metrics differ from fixed25")
        baselines[case_id] = baseline
        replay_rows.append({
            "case_id": case_id, "scenario": scenario,
            "candidate": candidate, "forced_macro0": baseline,
            "fixed25": fixed,
        })
    if prior_baselines is not None and baselines != prior_baselines:
        raise ValueError(
            "forced macro0 replay depends on checkpoint weights")
    return replay_rows, baselines


def _quality(rows, validation, tuned_rows, nodes, prior_baselines):
    expected = dict((case["case_id"], case["scenario"])
                    for case in validation)
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("residual validation source rows must contain six cases")
    observed = set()
    regrets = {"am_peak": [], "pm_peak": []}
    learned_regimes, learned_nodes = set(), set()
    completion_losses, insertion_losses = [], []
    normal_exact = []
    current_baselines = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
                "case_id", "scenario", "horizon_seconds", "baseline",
                "candidate", "policy_audit", "candidate_macro_rewards",
                "baseline_macro_rewards", "baseline_policy",
                "baseline_policy_audit", "counterfactual_weight_independence",
                "operational_mode_source", "source_manifest_field",
                "operational_time_of_day"}:
            raise ValueError("residual validation source row is invalid")
        case_id, scenario = row.get("case_id"), row.get("scenario")
        if case_id in observed or expected.get(case_id) != scenario \
                or row.get("horizon_seconds") != 3600:
            raise ValueError("residual validation source row identity drift")
        observed.add(case_id)
        if (row.get("baseline_policy") != "forced_macro0_counterfactual"
                or row.get("counterfactual_weight_independence") != _COUNTERFACTUAL):
            raise ValueError("forced macro0 counterfactual weight independence is unproven")
        if (row.get("operational_mode_source") != "preregistered_time_of_day"
                or row.get("source_manifest_field") != "cases[].scenario"
                or row.get("operational_time_of_day") != scenario):
            raise ValueError("operational time-of-day source is not preregistered")
        baseline = _validate_metric(row.get("baseline"), "forced macro0")
        candidate = _validate_metric(row.get("candidate"), "candidate")
        tuned = tuned_rows[case_id]
        for field, key in (("queue_integral_vehicle_seconds", "queue"),
                           ("completion_rate", "completion"),
                           ("insertion_rate", "insertion")):
            if baseline[key] != float(tuned[field]):
                raise ValueError("forced macro0 counterfactual differs from fixed25: " + field)
        _validate_rewards(row.get("baseline_macro_rewards"), row["baseline"],
                          "forced macro0")
        _validate_rewards(row.get("candidate_macro_rewards"), row["candidate"],
                          "candidate")
        _validate_audit(row.get("baseline_policy_audit"), scenario, nodes,
                        3600, baseline=True)
        active_nodes, nonzero = _validate_audit(
            row.get("policy_audit"), scenario, nodes, 3600)
        current_baselines[case_id] = {
            "metrics": row["baseline"],
            "macro_rewards": row["baseline_macro_rewards"],
            "policy_audit": row["baseline_policy_audit"],
            "policy": row["baseline_policy"],
            "weight_independence": row["counterfactual_weight_independence"],
        }
        completion_losses.append(baseline["completion"] - candidate["completion"])
        insertion_losses.append(baseline["insertion"] - candidate["insertion"])
        if scenario == "normal":
            exact = all(candidate[key] == baseline[key]
                        for key in ("queue", "completion", "insertion"))
            if not exact:
                raise ValueError("normal candidate is not exact fixed25")
            normal_exact.append(case_id)
        else:
            if baseline["queue"] <= 0:
                raise ValueError("peak fixed25 queue must be positive for regret")
            regrets[scenario].append(
                100.0 * (candidate["queue"] - baseline["queue"])
                / baseline["queue"])
            if nonzero:
                learned_regimes.add(scenario)
                learned_nodes.update(active_nodes)
    if observed != set(expected):
        raise ValueError("residual validation source rows omit registered cases")
    if prior_baselines is not None and current_baselines != prior_baselines:
        raise ValueError("forced macro0 counterfactual differs between checkpoints")
    regime_means = dict((scenario, sum(values) / len(values))
                        for scenario, values in regrets.items())
    peak_values = regrets["am_peak"] + regrets["pm_peak"]
    mean_peak = sum(peak_values) / len(peak_values)
    gates = {
        "normal_exact_fixed_per_case": len(normal_exact) == 2,
        "normal_timeline_zero": True,
        "peak_regime_queue_noninferiority": all(
            _at_most(value, _GATES[
                "peak_regime_mean_queue_regret_percent_max"])
            for value in regime_means.values()),
        "mean_peak_queue_improvement": _at_most(
            mean_peak, _GATES["mean_peak_queue_regret_percent_max"]),
        "per_case_completion_safety": _at_most(
            max(completion_losses), _GATES["per_case_completion_loss_max"]),
        "per_case_insertion_safety": _at_most(
            max(insertion_losses), _GATES["per_case_insertion_loss_max"]),
        "learned_macros_in_both_peak_regimes": learned_regimes == {
            "am_peak", "pm_peak"},
        "minimum_distinct_nonzero_macro_nodes": len(learned_nodes) >= _GATES[
            "minimum_distinct_nonzero_macro_nodes"],
        "peak_timeline_zero": True,
        "forced_macro0_counterfactual_exact_fixed25": True,
    }
    return {
        "eligible": all(gates.values()), "gates": gates,
        "mean_queue_regret_percent_by_peak_regime": regime_means,
        "mean_peak_queue_regret_percent": mean_peak,
        "maximum_completion_loss": max(completion_losses),
        "maximum_insertion_loss": max(insertion_losses),
        "learned_macro_regimes": sorted(learned_regimes),
        "distinct_nonzero_macro_nodes": sorted(learned_nodes),
        "normal_exact_case_ids": sorted(normal_exact),
    }, current_baselines


def _validate_run(root, spec, config, manifest, baseline, validation,
                  tuned_rows, source_tree, validation_runner):
    run_dir = _inside(root, spec["arm"]["run_dir"], "residual pilot run")
    if not run_dir.is_dir():
        raise ValueError("residual pilot run directory is missing")
    required = ["run-manifest.json", "resolved-config.json",
                "baseline-tuning.json", "learning-curve.json", "summary.json"]
    for step in (2, 4):
        required.extend([
            "validation-step-%04d.json" % step,
            "checkpoints/step-%04d/contract.json" % step,
            "checkpoints/step-%04d/weights.npz" % step])
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise ValueError("residual pilot artifact is missing: " + missing[0])
    _validate_status(run_dir, required, source_tree)
    manifest_hash = canonical_json_sha256(manifest)
    run_manifest = _json(run_dir / "run-manifest.json", "residual run manifest")
    if set(run_manifest) != {
            "schema_version", "controller_family", "mode", "learning_seed",
            "manifest_sha256", "network_sha256", "phase_contract_sha256",
            "runtime", "code_commit", "source_tree", "foundation_verification",
            "training_case_ids", "validation_case_ids", "test_split_accessed",
            "operational_mode", "policy_input_schema"}:
        raise ValueError("residual pilot run manifest fields drift")
    expected_manifest = {
        "schema_version": 1, "controller_family": "schedule_residual_ddqn",
        "mode": "pilot", "learning_seed": 11,
        "manifest_sha256": manifest_hash,
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": manifest["phase_contract"]["sha256"],
        "runtime": manifest["runtime"], "code_commit": source_tree["git_commit"],
        "source_tree": source_tree, "test_split_accessed": False,
        "policy_input_schema": POLICY_INPUT_SCHEMA,
    }
    for field, value in expected_manifest.items():
        if run_manifest.get(field) != value:
            raise ValueError("residual pilot run manifest %s drift" % field)
    expected_operational = {
        "input": "declared_time_of_day",
        "operational_mode_source": "preregistered_time_of_day",
        "source_manifest_field": "cases[].scenario",
        "allowed_values": ["normal", "am_peak", "pm_peak"],
        "inference_inputs": ["current_phase_rows", "current_signal_state",
                             "elapsed_seconds"],
        "case_id_seed_filename_future_flow_features": False,
    }
    if run_manifest.get("operational_mode") != expected_operational:
        raise ValueError("residual operational mode provenance drift")
    _, training_ids = _manifest_cases(manifest)
    if (run_manifest.get("training_case_ids") != training_ids
            or run_manifest.get("validation_case_ids") !=
            [case["case_id"] for case in validation]):
        raise ValueError("residual run case provenance drift")
    foundation = run_manifest.get("foundation_verification", {})
    if (foundation.get("status") != "verified"
            or foundation.get("network_sha256") != manifest["network"]["sha256"]
            or foundation.get("generator_config_sha256") !=
            manifest["generator_config_sha256"]
            or foundation.get("runtime_digest") !=
            manifest["runtime"]["base_image_digest"]):
        raise ValueError("residual foundation provenance drift")
    resolved = _json(run_dir / "resolved-config.json", "residual resolved config")
    if set(resolved) != set(config).union({
            "mode", "learning_seed", "run", "source_tree",
            "manifest_sha256", "baseline_tuning_sha256"}):
        raise ValueError("residual resolved config fields drift")
    for field, value in config.items():
        if resolved.get(field) != value:
            raise ValueError("residual resolved config differs from source config")
    if (resolved.get("mode") != "pilot" or resolved.get("learning_seed") != 11
            or resolved.get("run") != config["tiers"]["pilot"]
            or resolved.get("source_tree") != source_tree
            or resolved.get("manifest_sha256") != manifest_hash
            or resolved.get("baseline_tuning_sha256") != baseline["tuning_sha256"]):
        raise ValueError("residual resolved config identity drift")
    if _json(run_dir / "baseline-tuning.json", "copied baseline tuning") != baseline:
        raise ValueError("residual copied baseline tuning differs from registered source")
    summary = _json(run_dir / "summary.json", "residual pilot summary")
    if (set(summary) != {
            "schema_version", "controller_family", "mode", "learning_seed",
            "episodes", "optimizer_updates", "replay_coverage", "checkpoints",
            "mean_training_loss", "wall_time_seconds", "test_split_accessed",
            "selection"}
            or summary.get("schema_version") != 1
            or summary.get("controller_family") != "schedule_residual_ddqn"
            or summary.get("mode") != "pilot" or summary.get("learning_seed") != 11
            or summary.get("episodes") != 4
            or _integer(summary.get("optimizer_updates"), "optimizer updates", 1) < 1
            or set(summary.get("replay_coverage", {})) != {"am_peak", "pm_peak"}
            or summary.get("test_split_accessed") is not False
            or summary.get("selection") != "requires_preregistered_residual_selector"):
        raise ValueError("residual pilot summary contract drift")
    checkpoint_summaries = summary.get("checkpoints")
    if not isinstance(checkpoint_summaries, list) or len(checkpoint_summaries) != 2:
        raise ValueError("residual pilot summary checkpoint set drift")
    by_step = dict((item.get("training_step"), item)
                   for item in checkpoint_summaries if isinstance(item, dict))
    if set(by_step) != {2, 4}:
        raise ValueError("residual pilot summary checkpoint identity drift")
    qualities, bindings, rerun_checkpoints = {}, {}, {}
    prior_baselines = None
    prior_replay_baselines = None
    fixed25_replays = {}
    for step, name in ((2, "step-2"), (4, "step-4")):
        expected_contract = _expected_contract(
            config, manifest, baseline, source_tree, step)
        directory = run_dir / "checkpoints" / ("step-%04d" % step)
        stored_contract = _json(directory / "contract.json",
                                name + " checkpoint contract")
        if stored_contract != expected_contract:
            raise ValueError("%s checkpoint contract drift" % name)
        record = _checkpoint_record(run_dir, step)
        artifact_path = run_dir / ("validation-step-%04d.json" % step)
        artifact = _json(artifact_path, name + " validation")
        if (set(artifact) != {"schema_version", "controller_family", "mode",
                              "learning_seed", "training_step", "checkpoint",
                              "rows", "reload_score_identity"}
                or artifact.get("schema_version") != 1
                or artifact.get("controller_family") != "schedule_residual_ddqn"
                or artifact.get("mode") != "pilot"
                or artifact.get("learning_seed") != 11
                or artifact.get("training_step") != step):
            raise ValueError("%s validation training step or identity drift" % name)
        if artifact.get("checkpoint") != record:
            raise ValueError("%s checkpoint hash binding drift" % name)
        summary_record = by_step[step]
        if (summary_record.get("training_step") != step
                or summary_record.get("validation_path") != artifact_path.name
                or summary_record.get("checkpoint") != record):
            raise ValueError("%s summary checkpoint binding drift" % name)
        if artifact.get("reload_score_identity") is not True:
            raise ValueError("%s checkpoint reload identity is missing" % name)
        _validate_npz_fields(directory / "weights.npz")
        try:
            network = ResidualDDQN.load_bundle(str(directory), expected_contract)
        except (IOError, KeyError, ValueError, TypeError) as exc:
            raise ValueError("%s checkpoint reload failed: %s" % (name, exc))
        _validate_loaded_network(network, config)
        response = _traffic_feature_response(network)
        quality, current_baselines = _quality(
            artifact.get("rows"), validation, tuned_rows, nodes=
            manifest["network"]["agent_ids"], prior_baselines=prior_baselines)
        prior_baselines = current_baselines
        replay_rows, current_replay_baselines = _replay_checkpoint(
            validation_runner, network, step, artifact.get("rows"), validation,
            tuned_rows, manifest["network"]["agent_ids"],
            prior_replay_baselines, fixed25_replays)
        prior_replay_baselines = current_replay_baselines
        quality["traffic_feature_response"] = response
        quality["gates"]["checkpoint_traffic_feature_response"] = True
        quality["training_step"] = step
        quality["checkpoint"] = record
        quality["validation"] = _record(root, artifact_path,
                                         name + " validation")
        qualities[name] = quality
        bindings[name] = {"checkpoint": record,
                          "validation": quality["validation"]}
        rerun_checkpoints[name] = {
            "training_step": step, "checkpoint": record,
            "rows": replay_rows,
        }
    rerun_evidence = {
        "schema_version": 1, "protocol": _RERUN_PROTOCOL,
        "source_commit": source_tree["git_commit"],
        "config": {"path": _REGISTERED_CONFIG_PATH,
                   "sha256": _REGISTERED_CONFIG_SHA256},
        "manifest_sha256": canonical_json_sha256(manifest),
        "checkpoints": rerun_checkpoints,
        "test_split_accessed": False,
    }
    return qualities, bindings, rerun_evidence


def _git_ancestor(root, ancestor, descendant):
    return subprocess.call(
        ["git", "-C", str(root), "merge-base", "--is-ancestor",
         ancestor, descendant], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE) == 0


def _evaluate(root, spec_path, validation_runner, allow_descendant=False):
    root = Path(root).resolve()
    spec_path, spec = _validate_spec(root, spec_path)
    attestation = _tracked_tree_attestation(str(root))
    config_path = _inside(root, spec["arm"]["config"], "residual source config")
    if sha256_file(config_path) != _REGISTERED_CONFIG_SHA256:
        raise ValueError("residual source config differs from preregistered full SHA256")
    config = _yaml(config_path, "residual source config")
    _validate_config(config)
    manifest_path = _inside(root, spec["manifest"], "experiment manifest")
    manifest = _json(manifest_path, "experiment manifest")
    validation, _ = _manifest_cases(manifest)
    baseline_path = _inside(root, spec["baseline_tuning_artifact"],
                            "baseline tuning artifact")
    baseline = _json(baseline_path, "baseline tuning artifact")
    tuned_rows = _baseline_rows(baseline, validation, config, manifest)
    run_dir = _inside(root, spec["arm"]["run_dir"], "residual pilot run")
    run_manifest = _json(run_dir / "run-manifest.json", "residual run manifest")
    source_tree = run_manifest.get("source_tree")
    if not isinstance(source_tree, dict) or source_tree.get("git_commit") != \
            run_manifest.get("code_commit"):
        raise ValueError("residual pilot source provenance is incomplete")
    if allow_descendant:
        if not _git_ancestor(root, source_tree["git_commit"],
                             attestation["git_commit"]):
            raise ValueError("current tree is not a descendant of residual pilot source")
    elif source_tree != attestation:
        raise ValueError("residual pilot source commit differs from clean selector tree")
    committed_config_sha256 = _committed_file_sha256(
        root, source_tree["git_commit"], _REGISTERED_CONFIG_PATH)
    if committed_config_sha256 != _REGISTERED_CONFIG_SHA256:
        raise ValueError("residual source commit config differs from preregistration")
    frozen_sources = {}
    for label, path in (("selector_spec", spec_path),
                        ("manifest", manifest_path),
                        ("baseline_tuning", baseline_path)):
        current = _record(root, path, label)
        committed = _committed_file_sha256(
            root, source_tree["git_commit"], current["path"])
        if committed != current["sha256"]:
            raise ValueError("%s differs from residual source commit" % label)
        frozen_sources[label] = {
            "path": current["path"], "sha256": committed,
            "git_commit": source_tree["git_commit"],
        }
    frozen_sources["simulation_inputs"] = _frozen_simulation_inputs(
        root, source_tree["git_commit"], manifest, validation)
    qualities, bindings, rerun_evidence = _validate_run(
        root, spec, config, manifest, baseline, validation, tuned_rows,
        source_tree, validation_runner)
    rerun_evidence["frozen_source_inputs"] = copy.deepcopy(frozen_sources)
    eligible = [(quality["mean_peak_queue_regret_percent"],
                 quality["training_step"], name, quality)
                for name, quality in qualities.items() if quality["eligible"]]
    eligible.sort(key=lambda item: (item[0], item[1]))
    winner = None
    if eligible:
        _, step, name, quality = eligible[0]
        winner = {
            "checkpoint": name, "training_step": step,
            "mean_peak_queue_regret_percent":
                quality["mean_peak_queue_regret_percent"],
            "checkpoint_artifacts": bindings[name],
        }
    decision = {
        "schema_version": 1,
        "decision_type": "haichau_residual_pilot_selection",
        "status": "selected" if winner else "rejected",
        "selector_spec": _record(root, spec_path,
                                  "residual selector specification"),
        "source_commit": source_tree["git_commit"],
        "source_tree": source_tree,
        "config": _record(root, config_path, "residual source config"),
        "committed_config": {
            "path": _REGISTERED_CONFIG_PATH,
            "git_commit": source_tree["git_commit"],
            "sha256": committed_config_sha256,
        },
        "frozen_source_inputs": frozen_sources,
        "manifest": _record(root, manifest_path, "experiment manifest"),
        "baseline_tuning": _record(root, baseline_path,
                                    "baseline tuning artifact"),
        "pilot_status": _record(root, run_dir / "status.json",
                                 "residual pilot status"),
        "ranking": list(_RANKING), "gates": copy.deepcopy(_GATES),
        "checkpoints": qualities, "winner": winner,
        "test_split_accessed": False,
    }
    return decision, config, spec, run_dir, rerun_evidence


def _selected_config(root, spec, config, decision):
    selected = copy.deepcopy(config)
    winner = decision["winner"]
    selected["pilot_selection"] = {
        "schema_version": 1,
        "decision_type": decision["decision_type"],
        "decision": {"path": spec["decision_output"]},
        "selector_spec": copy.deepcopy(decision["selector_spec"]),
        "source_commit": decision["source_commit"],
        "committed_config": copy.deepcopy(decision["committed_config"]),
        "frozen_source_inputs": copy.deepcopy(
            decision["frozen_source_inputs"]),
        "pilot_run_dir": spec["arm"]["run_dir"],
        "selected_checkpoint": winner["checkpoint"],
        "training_step": winner["training_step"],
        "mean_peak_queue_regret_percent":
            winner["mean_peak_queue_regret_percent"],
        "checkpoint_artifacts": copy.deepcopy(winner["checkpoint_artifacts"]),
        "pilot_status": copy.deepcopy(decision["pilot_status"]),
        "validation_rerun": copy.deepcopy(decision["validation_rerun"]),
        "ranking": list(_RANKING), "gates": copy.deepcopy(_GATES),
        "test_split_accessed": False,
    }
    return selected


def select_from_spec(root, spec_path, validation_runner=None):
    """Select step2/4 or write a rejection decision and fail closed."""
    root = Path(root).resolve()
    decision, config, spec, _, rerun_evidence = _evaluate(
        root, spec_path, validation_runner, allow_descendant=False)
    decision_path = _inside(root, spec["decision_output"],
                            "residual decision output")
    selected_path = _inside(root, spec["selected_config_output"],
                            "residual selected config output")
    rerun_path = _inside(root, spec["validation_rerun_output"],
                         "residual validation rerun output")
    if decision_path.exists() or selected_path.exists() or rerun_path.exists():
        raise ValueError("residual selector outputs already exist; decisions are immutable")
    _write_json(rerun_path, rerun_evidence)
    decision["validation_rerun"] = _record(
        root, rerun_path, "residual validation rerun output")
    if decision["winner"] is None:
        _write_json(decision_path, decision)
        raise ValueError("no eligible residual checkpoint; selection failed closed")
    selected = _selected_config(root, spec, config, decision)
    _write_yaml(selected_path, selected)
    decision["selected_config"] = _record(
        root, selected_path, "residual selected config")
    _write_json(decision_path, decision)
    return decision


def validate_selected_outputs(root, spec_path, validation_runner=None):
    """Recompute selection semantics from source rows on a descendant commit."""
    root = Path(root).resolve()
    prospective, config, spec, _, recomputed_rerun = _evaluate(
        root, spec_path, validation_runner, allow_descendant=True)
    decision_path = _inside(root, spec["decision_output"],
                            "residual decision output")
    selected_path = _inside(root, spec["selected_config_output"],
                            "residual selected config output")
    rerun_path = _inside(root, spec["validation_rerun_output"],
                         "residual validation rerun output")
    stored_rerun = _json(rerun_path, "residual validation rerun output")
    if stored_rerun != recomputed_rerun:
        raise ValueError("stored validation rerun differs from deterministic replay")
    prospective["validation_rerun"] = _record(
        root, rerun_path, "residual validation rerun output")
    decision = _json(decision_path, "residual decision output")
    if decision.get("status") != "selected" or decision.get("winner") is None:
        raise ValueError("residual decision did not select a checkpoint")
    selected_record = decision.get("selected_config")
    if (not isinstance(selected_record, dict)
            or selected_record.get("path") != spec["selected_config_output"]
            or selected_record.get("sha256") != sha256_file(selected_path)):
        raise ValueError("residual selected config hash drift")
    comparable = ("schema_version", "decision_type", "status", "selector_spec",
                  "source_commit", "source_tree", "config", "manifest",
                  "committed_config", "frozen_source_inputs",
                  "baseline_tuning", "pilot_status",
                  "validation_rerun", "ranking", "gates",
                  "checkpoints", "winner", "test_split_accessed")
    if any(decision.get(field) != prospective.get(field)
           for field in comparable):
        raise ValueError("selected decision drift from recomputed source rows")
    selected = _yaml(selected_path, "residual selected config")
    expected = _selected_config(root, spec, config, decision)
    if selected != expected:
        raise ValueError("selected config differs from recomputed residual decision")
    return decision
