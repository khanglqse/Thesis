"""Frozen Hai Chau controller construction and single-run evaluation.

The campaign runner owns process isolation and provenance.  This module owns
the in-container mapping from a frozen run record to one CityFlow environment
and one of the five thesis controllers.  It remains importable on Python 3.6.
"""

import hashlib
import json
import math
import re
from pathlib import Path

from traffic_rl.agents.dqn import DQNController, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import (
    HystereticMaxPressureController, MaxPressureController,
)
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.network_campaign import CONTROLLERS, canonical_sha256
from traffic_rl.eval.network_metrics import NetworkMetricsObserver
from traffic_rl.eval.network_replay import NetworkReplayObserver
from traffic_rl.eval.runner import run_episode
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.phase_encoder import FEATURES, PhaseFeatureEncoder


LEARNED_CONTROLLERS = frozenset((
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
))


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_file(project_root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s path is required" % label)
    root = Path(project_root).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s path escapes project root" % label)
    if not path.is_file():
        raise ValueError("%s artifact is missing" % label)
    return path


def _verified_file(project_root, relative, expected_sha256, label):
    path = _project_file(project_root, relative, label)
    if _sha256(path) != expected_sha256:
        raise ValueError("%s artifact sha256 mismatch" % label)
    return path


def _dictionary(value, label):
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % label)
    return value


def _positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be positive" % label)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("%s must be finite and positive" % label)
    return number


def _runtime_config(run):
    config = _dictionary(run.get("resolved_config"), "resolved_config")
    simulation = _dictionary(config.get("simulation"), "simulation config")
    normalization = _dictionary(
        config.get("normalization"), "normalization config")
    reward = _dictionary(config.get("reward"), "reward config")
    for field in ("action_interval", "min_green", "maximum_red"):
        _positive(simulation.get(field), "simulation %s" % field)
    for field in ("count_norm", "capacity_norm"):
        _positive(normalization.get(field), "normalization %s" % field)
    for field in ("queue_weight", "downstream_block_weight", "switch_penalty"):
        try:
            float(reward[field])
        except (KeyError, TypeError, ValueError):
            raise ValueError("reward %s must be numeric" % field)
    return config, simulation, normalization, reward


def _legacy_feature_order(encoder):
    if hasattr(encoder, "feature_order"):
        return list(encoder.feature_order)
    return (
        ["incoming_lane_count_%d" % index for index in range(encoder.max_in)]
        + ["outgoing_lane_count_%d" % index for index in range(encoder.max_out)]
        + ["green_phase_%d" % index for index in range(encoder.max_green)])


def _checkpoint(project_root, run, controller_id):
    contract = _dictionary(
        run.get("checkpoint_contract"), "checkpoint contract")
    if contract.get("controller_family") != controller_id:
        raise ValueError("checkpoint controller family mismatch")
    if canonical_sha256(contract) != run.get("checkpoint_contract_sha256"):
        raise ValueError("checkpoint contract sha256 mismatch")
    path = _verified_file(
        project_root, run.get("checkpoint_path"),
        run.get("checkpoint_sha256"), "checkpoint")
    contract_path = path.parent / "contract.json"
    if not contract_path.is_file():
        raise ValueError("checkpoint contract artifact is missing")
    try:
        stored = json.loads(contract_path.read_text())
    except ValueError:
        raise ValueError("checkpoint contract artifact is invalid")
    if stored != contract:
        raise ValueError("checkpoint contract artifact differs from run")
    return path.parent, contract


def _learned_runtime(project_root, run, roadnet, normalization):
    controller_id = run["controller_id"]
    checkpoint_dir, contract = _checkpoint(project_root, run, controller_id)
    if controller_id == "neighbor_phase_ddqn":
        expected_normalization = {
            "count_norm": float(normalization["count_norm"]),
            "capacity_norm": float(normalization["capacity_norm"]),
        }
        if contract.get("normalization") != expected_normalization:
            raise ValueError("checkpoint normalization differs from runtime")
        if list(contract.get("feature_order", ())) != list(FEATURES):
            raise ValueError("neighbor checkpoint feature order mismatch")
        encoder = PhaseFeatureEncoder(
            roadnet, expected_normalization["count_norm"],
            expected_normalization["capacity_norm"])
        network = PhaseScoringDDQN.load_bundle(
            str(checkpoint_dir), contract)
        if network.feature_dim != len(FEATURES):
            raise ValueError("neighbor checkpoint feature dimension mismatch")
    else:
        encoder = ObservationEncoder(
            roadnet, count_norm=float(normalization["count_norm"]),
            state_mode="basic")
        if list(contract.get("feature_order", ())) != _legacy_feature_order(encoder):
            raise ValueError("legacy checkpoint feature order mismatch")
        network = SharedDQN.load_bundle(str(checkpoint_dir), contract)
        if network.obs_dim != encoder.obs_dim \
                or network.n_actions != encoder.max_green:
            raise ValueError("legacy checkpoint dimensions differ from runtime")
    return encoder, network


def build_controller_runtime(project_root, run, runtime_dir,
                             engine_factory=CityFlowEngine,
                             env_class=MultiAgentTrafficEnv):
    """Build one hash-checked environment/controller pair from a frozen run."""
    if not isinstance(run, dict):
        raise ValueError("run manifest must be an object")
    run_id = str(run.get("run_id", ""))
    if (not re.match(r"^[A-Za-z0-9_.-]+$", run_id)
            or run_id in (".", "..")):
        raise ValueError("unsafe run identifier")
    controller_id = run.get("controller_id")
    if controller_id not in CONTROLLERS:
        raise ValueError("unknown controller: %s" % controller_id)
    config, simulation, normalization, reward = _runtime_config(run)
    network_path = _verified_file(
        project_root, config.get("network_path"), run.get("network_sha256"),
        "network")
    demand_path = _verified_file(
        project_root, run.get("demand_path"), run.get("demand_sha256"),
        "demand")
    phase_path = _verified_file(
        project_root, config.get("phase_contract_path"),
        config.get("phase_contract_sha256"), "phase contract")
    roadnet = RoadNet.load(
        str(network_path), str(phase_path), require_phase_contract=True,
        expected_phase_contract_sha256=config["phase_contract_sha256"])
    if list(roadnet.signalized_ids()) != list(run.get("agent_ids", ())):
        raise ValueError("run agent IDs differ from network")
    if len(run.get("agent_ids", ())) != int(run.get("controlled_signals", -1)):
        raise ValueError("run controlled signal count differs from agent IDs")
    scheduled = run.get("scheduled_vehicles")
    if isinstance(scheduled, bool) or not isinstance(scheduled, int) or scheduled < 0:
        raise ValueError("scheduled_vehicles must be a non-negative integer")

    lane_to_node = {}
    for node_id in roadnet.signalized_ids():
        for lane_id in roadnet.incoming_lanes(node_id):
            lane_to_node[lane_id] = node_id
    spillback_threshold = _positive(
        config.get("spillback_queue_threshold", normalization["capacity_norm"]),
        "spillback_queue_threshold")
    metric_observer = NetworkMetricsObserver(
        scheduled_vehicles=scheduled,
        step_seconds=float(config.get("step_seconds", 1.0)),
        lane_to_node=lane_to_node,
        spillback_thresholds=dict(
            (lane_id, spillback_threshold) for lane_id in lane_to_node))
    replay_observer = NetworkReplayObserver(
        roadnet.signalized_ids(), dict(
            (node_id, roadnet.incoming_lanes(node_id))
            for node_id in roadnet.signalized_ids()), sample_seconds=5)

    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    cityflow_config = {
        "interval": float(config.get("step_seconds", 1.0)),
        "seed": int(run["simulator_seed"]),
        "dir": str(Path(project_root).resolve()) + "/",
        "roadnetFile": str(network_path.relative_to(Path(project_root).resolve())),
        "flowFile": str(demand_path.relative_to(Path(project_root).resolve())),
        "rlTrafficLight": True, "laneChange": False, "saveReplay": False,
    }
    engine_config_path = runtime_dir / (run_id + ".json")
    engine_config_path.write_text(
        json.dumps(cityflow_config, indent=2, sort_keys=True) + "\n")

    encoder = None
    network = None
    if controller_id in LEARNED_CONTROLLERS:
        encoder, network = _learned_runtime(
            project_root, run, roadnet, normalization)
    env = env_class(
        roadnet, engine_factory(str(engine_config_path)),
        action_interval=int(simulation["action_interval"]),
        max_steps=int(run["horizon_steps"]),
        yellow_time=int(simulation.get("yellow_time", 0)),
        min_green=int(simulation["min_green"]),
        maximum_red=int(simulation["maximum_red"]),
        encoder=encoder, reward_type="queue_norm",
        count_norm=float(normalization["count_norm"]),
        queue_weight=float(reward["queue_weight"]),
        downstream_block_weight=float(reward["downstream_block_weight"]),
        switch_penalty=float(reward["switch_penalty"]),
        network_metric_observer=metric_observer,
        network_replay_observer=replay_observer)

    if controller_id == "tuned_fixed":
        controller = FixedTimeController(
            env.num_actions, green_duration=_positive(
                config.get("green_duration"), "green_duration"),
            action_interval=int(simulation["action_interval"]))
    elif controller_id == "max_pressure":
        controller = MaxPressureController(roadnet)
    elif controller_id == "hysteretic_mp":
        controller = HystereticMaxPressureController(
            roadnet,
            min_hold_decisions=int(_positive(
                config.get("min_hold_decisions"), "min_hold_decisions")),
            switch_threshold=float(config.get("switch_threshold", 0.0)))
    else:
        controller = DQNController(network, env.agent_ids)
    return env, controller


def evaluate_run(project_root, run, runtime_dir,
                 engine_factory=CityFlowEngine,
                 env_class=MultiAgentTrafficEnv,
                 episode_runner=run_episode):
    """Execute one fresh frozen run and return the campaign result envelope."""
    env, controller = build_controller_runtime(
        project_root, run, runtime_dir,
        engine_factory=engine_factory, env_class=env_class)
    metrics = episode_runner(env, controller)
    if int(metrics.get("steps", -1)) != int(run["horizon_steps"]):
        raise ValueError("evaluation did not complete the frozen horizon")
    metrics["completed_steps"] = int(run["horizon_steps"])
    for field in (
            "case_id", "regime", "controller_id", "learning_seed",
            "demand_seed", "simulator_seed", "scheduled_vehicles", "network_sha256",
            "viewer_network_sha256", "demand_sha256", "demand_path",
            "runtime_digest", "runtime_image", "runtime_image_id",
            "runtime_dockerfile_path", "runtime_dockerfile_sha256",
            "code_commit", "checkpoint_sha256",
            "checkpoint_contract_sha256"):
        metrics[field] = run.get(field)
    metrics["fresh_evaluation"] = True
    replay = env.network_replay_observer.finalize(metrics)
    return {"resolved_config": run["resolved_config"], "metrics": metrics,
            "replay": replay}
