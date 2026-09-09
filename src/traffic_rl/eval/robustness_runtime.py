"""Runtime helpers for the preregistered V3 robustness appendix."""

import hashlib
import json
import math
from pathlib import Path

from traffic_rl.eval.haichau_controller_runtime import evaluate_run
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.robustness_perturbations import (
    KeyedSensorEngine, LaneRestrictionIncidentEngine,
)


def scheduled_departures(row):
    start = float(row["startTime"])
    end = float(row["endTime"])
    interval = float(row["interval"])
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("flow interval must be finite and positive")
    return 0 if start > end else 1 + int(math.floor((end - start) / interval))


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def materialize_demand_plus20(source_path, target_path, multiplier=1.2):
    factor = float(multiplier)
    if not math.isfinite(factor) or factor != 1.2:
        raise ValueError("V3 demand stress multiplier must equal 1.20")
    source = json.loads(Path(source_path).read_text())
    if not isinstance(source, list) or not source:
        raise ValueError("source flow must be a non-empty JSON list")
    scaled = []
    for row in source:
        item = dict(row)
        item["vehicle"] = dict(row["vehicle"])
        item["route"] = list(row["route"])
        item["interval"] = float(row["interval"]) / factor
        scaled.append(item)
    target = Path(target_path)
    if target.exists():
        raise ValueError("refusing to replace immutable demand stress input")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(scaled, indent=2, sort_keys=True) + "\n")
    return {
        "path": str(target),
        "sha256": _sha256(target),
        "source_sha256": _sha256(source_path),
        "source_scheduled_vehicles": sum(scheduled_departures(row) for row in source),
        "scheduled_vehicles": sum(scheduled_departures(row) for row in scaled),
    }


def evaluate_robustness_run(project_root, run, runtime_dir,
                            engine_factory=CityFlowEngine):
    condition = run.get("robustness_condition")
    if not isinstance(condition, dict):
        raise ValueError("robustness run requires a frozen condition")

    def wrapped_engine(config_path):
        inner = engine_factory(config_path)
        kind = condition.get("kind")
        if kind == "sensor_gaussian":
            return KeyedSensorEngine(
                inner, "gaussian", condition["sigma"], run["perturbation_seed"])
        if kind == "sensor_dropout":
            return KeyedSensorEngine(
                inner, "dropout", condition["probability"],
                run["perturbation_seed"])
        if kind == "lane_restriction_incident":
            target = condition["target"]
            return LaneRestrictionIncidentEngine(
                inner, target["closed_lane_ids"], condition["start_step"],
                condition["end_step"])
        return inner

    result = evaluate_run(
        project_root, run, runtime_dir, engine_factory=wrapped_engine)
    result["metrics"]["condition_id"] = run["condition_id"]
    result["metrics"]["study_role"] = "exploratory_appendix"
    result["metrics"]["perturbation_seed"] = run["perturbation_seed"]
    return result
