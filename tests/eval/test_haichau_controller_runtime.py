import hashlib
import json
import math

import pytest

from traffic_rl.agents.dqn import DQNController, SharedDQN
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import (
    HystereticMaxPressureController, MaxPressureController,
)
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.eval.haichau_controller_runtime import (
    build_controller_runtime, evaluate_run,
)
from traffic_rl.eval.network_campaign import canonical_sha256
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.phase_encoder import FEATURES, PhaseFeatureEncoder


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeRoadNet(object):
    def signalized_ids(self):
        return ["A"]

    def incoming_lanes(self, unused):
        return ["in_0"]

    def outgoing_lanes(self, unused):
        return ["out_0"]

    def green_phases(self, unused):
        return [0, 1]

    def phase_contract(self, unused):
        return {"errors": []}

    def phase_movements(self, unused, phase):
        return (["in_0"], ["out_0"])

    def phase_movement_pairs(self, unused, phase):
        return [("in_0", "out_0")]

    def upstream_neighbors(self, unused):
        return []

    def downstream_neighbors(self, unused):
        return []


class FakeEnv(object):
    instances = []

    def __init__(self, roadnet, engine, **kwargs):
        self.roadnet = roadnet
        self.engine = engine
        self.encoder = kwargs.get("encoder")
        self.network_replay_observer = kwargs.get("network_replay_observer")
        self.kwargs = kwargs
        self.agent_ids = roadnet.signalized_ids()
        self.num_actions = {"A": 2}
        FakeEnv.instances.append(self)

    def reset(self):
        if self.network_replay_observer is not None:
            self.network_replay_observer.reset({"in_0": 0}, {"A": 0})
        return {"A": [0.0]}

    def action_masks(self):
        return {"A": [True, True]}

    def current_waiting_counts(self):
        return {"in_0": 0}

    def step(self, actions):
        if self.network_replay_observer is not None:
            self.network_replay_observer.observe(5, {"in_0": 1}, {"A": 0})
            self.network_replay_observer.observe(10, {"in_0": 0}, {"A": 1})
        nodes = {"A": 0.0}
        final = {
            "observed_steps": 10, "observed_seconds": 10.0,
            "queue_integral_vehicle_seconds": 0.0,
            "network_queue_integral_vehicle_seconds": 0.0,
            "queue_integral_vehicle_hours": 0.0,
            "pending_integral_vehicle_seconds": 0.0,
            "per_node_queue_integral_vehicle_seconds": nodes,
            "per_node_max_queue": nodes, "spillback_lane_seconds": {},
            "scheduled": 0, "inserted": 0, "departed": 0,
            "arrived": 0, "running": 0, "pending": 0, "removed": 0,
            "censored_or_unfinished": 0,
            "completion_denominator": "scheduled", "completion_rate": None,
            "insertion_rate": None, "completed_travel_time_count": 0,
            "phase_switches": 0, "intergreen_seconds": 0.0,
            "max_red_seconds": 0.0,
            "travel_time_completed_mean": None,
            "travel_time_completed_median": None,
            "travel_time_completed_p95": None,
        }
        return {"A": [0.0]}, {"A": 0.0}, True, {
            "step": 10, "total_queue": 0.0, "network_metrics": final,
        }


def _base_files(tmp_path):
    network = tmp_path / "roadnet.json"
    phase = tmp_path / "phase-contract.json"
    demand = tmp_path / "demand.json"
    network.write_text("network")
    phase.write_text("phase")
    demand.write_text("demand")
    return network, phase, demand


def _run(tmp_path, controller_id, checkpoint=None, contract=None):
    network, phase, demand = _base_files(tmp_path)
    simulation = {
        "action_interval": 10, "yellow_time": 3,
        "min_green": 20, "maximum_red": 180,
    }
    config = {
        "network_path": network.name,
        "phase_contract_path": phase.name,
        "phase_contract_sha256": _digest(phase),
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "simulation": simulation,
        "reward": {
            "queue_weight": 1.0, "downstream_block_weight": 0.1,
            "switch_penalty": 0.05,
        },
        "green_duration": 30,
        "min_hold_decisions": 3,
        "switch_threshold": 2.5,
    }
    run = {
        "run_id": controller_id + "__case",
        "case_id": "case", "regime": "normal",
        "controller_id": controller_id, "learning_seed": None,
        "demand_seed": 101, "simulator_seed": 201,
        "horizon_steps": 10, "network_sha256": _digest(network),
        "viewer_network_sha256": "v" * 64,
        "demand_sha256": _digest(demand), "demand_path": demand.name,
        "runtime_digest": "sha256:" + "r" * 64,
        "runtime_image": "image@sha256:" + "r" * 64,
        "runtime_image_id": "sha256:" + "r" * 64,
        "runtime_dockerfile_path": "Dockerfile",
        "runtime_dockerfile_sha256": "d" * 64,
        "code_commit": "c" * 40, "fresh_evaluation": True,
        "controlled_signals": 1, "agent_ids": ["A"],
        "scheduled_vehicles": 0,
    }
    if checkpoint is not None:
        run.update({
            "learning_seed": 11,
            "checkpoint_path": str(checkpoint.relative_to(tmp_path)),
            "checkpoint_sha256": _digest(checkpoint),
            "checkpoint_contract": contract,
            "checkpoint_contract_sha256": canonical_sha256(contract),
        })
        config["checkpoint"] = dict((key, run[key]) for key in (
            "checkpoint_path", "checkpoint_sha256", "checkpoint_contract",
            "checkpoint_contract_sha256"))
    run["resolved_config"] = config
    return run


def _dependencies(monkeypatch):
    roadnet = FakeRoadNet()
    monkeypatch.setattr(
        "traffic_rl.eval.haichau_controller_runtime.RoadNet.load",
        lambda *args, **kwargs: roadnet)
    return {
        "engine_factory": lambda path: {"config_path": path},
        "env_class": FakeEnv,
    }


@pytest.mark.parametrize("controller_id,expected", [
    ("tuned_fixed", FixedTimeController),
    ("max_pressure", MaxPressureController),
    ("hysteretic_mp", HystereticMaxPressureController),
])
def test_builds_each_deterministic_controller_from_frozen_config(
        tmp_path, monkeypatch, controller_id, expected):
    run = _run(tmp_path, controller_id)

    env, controller = build_controller_runtime(
        tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert isinstance(controller, expected)
    assert env.kwargs["max_steps"] == 10
    observer = env.kwargs["network_metric_observer"]
    assert observer.scheduled_vehicles == 0
    assert observer.lane_to_node == {"in_0": "A"}
    assert observer.spillback_thresholds == {"in_0": 40.0}
    assert env.kwargs["network_replay_observer"].sample_seconds == 5
    if controller_id == "tuned_fixed":
        assert controller.green_duration == 30
    if controller_id == "hysteretic_mp":
        assert controller.min_hold_decisions == 3
        assert controller.switch_threshold == 2.5


def test_loads_legacy_ddqn_with_basic_vector_encoder(tmp_path, monkeypatch):
    checkpoint_dir = tmp_path / "legacy"
    contract = {
        "controller_family": "shared_ddqn_legacy",
        "feature_order": [
            "incoming_lane_count_0", "outgoing_lane_count_0",
            "green_phase_0", "green_phase_1",
        ],
        "hidden_size": 4,
        "action_contract": {"n_actions": 2},
    }
    SharedDQN(4, 2, hidden=4, seed=1, dueling=True).save_bundle(
        str(checkpoint_dir), contract)
    run = _run(tmp_path, "shared_ddqn_legacy",
               checkpoint_dir / "weights.npz", contract)

    env, controller = build_controller_runtime(
        tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert isinstance(controller, DQNController)
    assert isinstance(env.encoder, ObservationEncoder)
    assert isinstance(controller.net, SharedDQN)


def test_loads_neighbor_ddqn_with_phase_encoder(tmp_path, monkeypatch):
    checkpoint_dir = tmp_path / "neighbor"
    contract = {
        "controller_family": "neighbor_phase_ddqn",
        "feature_dim": len(FEATURES), "feature_order": list(FEATURES),
        "hidden_size": 4,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
    }
    PhaseScoringDDQN(len(FEATURES), 4, 1e-3, seed=1).save_bundle(
        str(checkpoint_dir), contract)
    run = _run(tmp_path, "neighbor_phase_ddqn",
               checkpoint_dir / "weights.npz", contract)

    env, controller = build_controller_runtime(
        tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert isinstance(controller, DQNController)
    assert isinstance(env.encoder, PhaseFeatureEncoder)
    assert isinstance(controller.net, PhaseScoringDDQN)


def test_loads_v3_neighbor_checkpoint_with_bound_schedule_context(
        tmp_path, monkeypatch):
    from traffic_rl.sim.phase_encoder import SCHEDULE_CONTEXT_FEATURES
    checkpoint_dir = tmp_path / "neighbor-v3"
    observation = {
        "schema_version": 3,
        "type": "phase_rows_fixed_schedule_context",
        "phase_row_identity": "cycle_fraction",
        "global_cycle": {
            "encoding": "sin_cos", "green_duration_seconds": 25,
            "period": "green_duration_times_selectable_green_count"},
    }
    contract = {
        "controller_family": "neighbor_phase_ddqn",
        "obs_schema_version": 3,
        "feature_dim": len(SCHEDULE_CONTEXT_FEATURES),
        "feature_order": list(SCHEDULE_CONTEXT_FEATURES),
        "hidden_size": 4, "observation": observation,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
    }
    PhaseScoringDDQN(
        len(SCHEDULE_CONTEXT_FEATURES), 4, 1e-3, seed=1).save_bundle(
            str(checkpoint_dir), contract)
    run = _run(tmp_path, "neighbor_phase_ddqn",
               checkpoint_dir / "weights.npz", contract)

    env, controller = build_controller_runtime(
        tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert env.encoder.feature_order == list(SCHEDULE_CONTEXT_FEATURES)
    assert env.encoder.schedule_green_duration == 25.0
    assert controller.net.feature_dim == len(SCHEDULE_CONTEXT_FEATURES)


def test_rejects_changed_demand_before_engine_creation(tmp_path, monkeypatch):
    run = _run(tmp_path, "tuned_fixed")
    (tmp_path / "demand.json").write_text("changed")
    calls = []
    dependencies = _dependencies(monkeypatch)
    dependencies["engine_factory"] = lambda path: calls.append(path)

    with pytest.raises(ValueError, match="demand artifact sha256 mismatch"):
        build_controller_runtime(
            tmp_path, run, tmp_path / "runtime", **dependencies)

    assert calls == []


def test_rejects_unsafe_run_id_before_writing_runtime_config(tmp_path, monkeypatch):
    run = _run(tmp_path, "tuned_fixed")
    run["run_id"] = "../escape"

    with pytest.raises(ValueError, match="unsafe run identifier"):
        build_controller_runtime(
            tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert not (tmp_path / "escape.json").exists()


def test_rejects_non_finite_frozen_numeric_config(tmp_path, monkeypatch):
    run = _run(tmp_path, "tuned_fixed")
    run["resolved_config"]["simulation"]["action_interval"] = math.nan

    with pytest.raises(ValueError, match="action_interval must be finite and positive"):
        build_controller_runtime(
            tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))


def test_evaluate_run_binds_metrics_to_run_identity(tmp_path, monkeypatch):
    run = _run(tmp_path, "tuned_fixed")

    result = evaluate_run(
        tmp_path, run, tmp_path / "runtime", **_dependencies(monkeypatch))

    assert result["resolved_config"] == run["resolved_config"]
    assert result["metrics"]["completed_steps"] == 10
    for field in (
            "case_id", "regime", "controller_id", "learning_seed",
            "demand_seed", "simulator_seed", "network_sha256",
            "demand_sha256", "runtime_digest", "runtime_image",
            "runtime_image_id", "runtime_dockerfile_path",
            "runtime_dockerfile_sha256", "code_commit",
            "viewer_network_sha256", "demand_path",
            "checkpoint_sha256", "checkpoint_contract_sha256"):
        assert result["metrics"].get(field) == run.get(field)
    assert result["metrics"]["fresh_evaluation"] is True
    assert [frame["t"] for frame in result["replay"]["frames"]] == [0, 5, 10]
