"""Validation-only pressure-controller diagnostics; never release evidence.

Use the training environment and its due-demand objective, with the same
per-second metric observer used for the final campaign. Python 3.6 compatible.
"""
from collections import Counter
from pathlib import Path

from traffic_rl.agents.max_pressure import (
    MaxPressureController, HystereticMaxPressureController)
from traffic_rl.eval.checkpoint_selection import relative_regret
from traffic_rl.eval.network_metrics import NetworkMetricsObserver
from traffic_rl.eval.runner import run_episode
from traffic_rl.train.network_trainer import (
    _close, _file_sha256, _git_sha, _load_precomputed_tuning,
    _selected_baseline_rows, _tuning_binding, _validate_precomputed_tuning,
    _write_json, canonical_json_sha256)


CONTROLLER_CONFIGS = {
    "raw_max_pressure": {},
    "hysteretic_max_pressure": {"min_hold_decisions": 3, "switch_threshold": 2.5},
}


def _verify_inputs(root, manifest, cases):
    artifacts = [manifest["network"], manifest["phase_contract"],
                 {"path": manifest["generator_config_path"],
                  "sha256": manifest["generator_config_sha256"]}]
    artifacts.extend({"path": case["flow_path"], "sha256": case["flow_sha256"]}
                     for case in cases)
    for artifact in artifacts:
        path = (root / artifact["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise ValueError("diagnostic input escapes project root")
        if not path.is_file() or _file_sha256(str(path)) != artifact["sha256"]:
            raise ValueError("diagnostic input hash drift: %s" % artifact["path"])


def evaluate_pressure_validation(env_factory, manifest, config, baseline_tuning_artifact,
                                 output_dir, foundation_root):
    """Run two fixed pressure policies on exactly six validation cases.

    A completed output is diagnostic only. Existing directories are never
    overwritten; failures retain partial rows in diagnostic.json.
    """
    output_dir = Path(output_dir).resolve()
    root = Path(foundation_root).resolve()
    if output_dir.exists():
        raise ValueError("refusing to overwrite diagnostic output")
    cases = [case for case in manifest.get("cases", [])
             if case.get("split") == "validation"]
    if (manifest.get("protocol_version") != 2
            or Counter(case.get("scenario") for case in cases)
            != Counter({"normal": 2, "am_peak": 2, "pm_peak": 2})
            or len(set(case.get("case_id") for case in cases)) != 6):
        raise ValueError("diagnostic requires exactly six distinct validation cases")
    if config["run"]["horizon_seconds"] != 3600:
        raise ValueError("diagnostic requires the full 3600-second horizon")
    if config.get("simulation") != manifest["simulation"]:
        raise ValueError("diagnostic simulation differs from manifest")
    binding = _tuning_binding(manifest, cases, 3600, config)
    tuning, provenance = _load_precomputed_tuning(baseline_tuning_artifact)
    _validate_precomputed_tuning(tuning, binding, config, cases)
    _verify_inputs(root, manifest, cases)
    baselines = _selected_baseline_rows(tuning, cases)
    result = {
        "schema_version": 1, "status": "diagnostic_partial",
        "purpose": "validation_only_pressure_diagnostic",
        "eligible_for_release": False, "eligible_for_test_evaluation": False,
        "binding": binding, "code_commit": _git_sha(str(root)),
        "training_config_sha256": canonical_json_sha256(config),
        "controller_configs": CONTROLLER_CONFIGS,
        "baseline_tuning_sha256": tuning["tuning_sha256"],
        "baseline_artifact_provenance": provenance,
        "baseline_selected": tuning["selected"], "rows": [],
    }
    output_dir.mkdir(parents=True)
    output_path = str(output_dir / "diagnostic.json")
    _write_json(output_path, result)
    for controller_id in ("raw_max_pressure", "hysteretic_max_pressure"):
        for case in cases:
            env = env_factory(case, 3600)
            try:
                if len(env.agent_ids) != manifest["network"]["controlled_signals"]:
                    raise ValueError("diagnostic controlled signal count differs")
                lane_to_node = {lane: agent for agent in env.agent_ids
                                for lane in env.roadnet.incoming_lanes(agent)}
                env.network_metric_observer = NetworkMetricsObserver(
                    scheduled_vehicles=int(case["scheduled_vehicles"]),
                    step_seconds=1.0, lane_to_node=lane_to_node,
                    spillback_thresholds={lane: manifest["preprocessing"]["capacity_norm"]
                                         for lane in lane_to_node})
                controller = (MaxPressureController(env.roadnet)
                              if controller_id == "raw_max_pressure" else
                              HystereticMaxPressureController(
                                  env.roadnet, **CONTROLLER_CONFIGS[controller_id]))
                metrics = run_episode(env, controller)
                if metrics.get("observed_seconds") != 3600 or metrics.get("steps") != 3600:
                    raise ValueError("diagnostic rollout did not complete 3600 seconds")
                if metrics.get("completion_rate") is None:
                    raise ValueError("diagnostic completion evidence is missing")
                baseline = baselines[case["case_id"]]
                row = {
                    "case_id": case["case_id"], "scenario": case["scenario"],
                    "split": "validation", "controller_id": controller_id,
                    "flow_sha256": case["flow_sha256"],
                    "demand_seed": case["demand_seed"], "sim_seed": case["sim_seed"],
                    "metrics": metrics, "baseline": baseline,
                    "queue_regret": relative_regret(
                        metrics["queue_integral_vehicle_seconds"],
                        baseline["queue_integral_vehicle_seconds"]),
                    "completion_degradation": (None if baseline["completion_rate"] is None
                                               else baseline["completion_rate"]
                                               - metrics["completion_rate"]),
                }
                result["rows"].append(row)
                _write_json(output_path, result)
            finally:
                _close(env)
    result["status"] = "diagnostic_complete"
    _write_json(output_path, result)
    return result
