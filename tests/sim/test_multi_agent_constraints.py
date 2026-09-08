import json

import numpy as np

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder
from tests.conftest import FakeEngine


def _roadnet(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": [
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]},
            ],
            "trafficLight": {"lightphases": [
                {"availableRoadLinks": [0]}, {"availableRoadLinks": []},
                {"availableRoadLinks": [1]},
            ]},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "in", "endIntersection": "A",
             "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "out",
             "lanes": [{}]},
        ],
    }
    path = tmp_path / "roadnet.json"
    path.write_text(json.dumps(data))
    return RoadNet.load(str(path))


def _env(tmp_path, **kwargs):
    roadnet = _roadnet(tmp_path)
    engine = FakeEngine(
        vehicle_counts={"rin_0": 3, "rin_1": 2, "rout_0": 0},
        waiting_counts={"rin_0": 3, "rin_1": 2, "rout_0": 0})
    defaults = {"action_interval": 10, "yellow_time": 3, "min_green": 0,
                "maximum_red": 180, "switch_penalty": 0.05}
    defaults.update(kwargs)
    return MultiAgentTrafficEnv(roadnet, engine, **defaults)


def test_hold_action_has_no_clearance_or_switch_penalty(tmp_path):
    env = _env(tmp_path)
    env.reset()
    _, rewards, _, info = env.step({"A": 0})

    assert rewards["A"] == -5.0
    assert info["phase_switches"] == 0
    assert info["intergreen_vehicle_seconds"] == 0


def test_maximum_red_mask_forces_overdue_phase(tmp_path):
    env = _env(tmp_path)
    env.reset()
    env._time_since_service["A"] = [0, 181]

    assert env.action_masks()["A"].tolist() == [False, True]


def test_minimum_green_mask_allows_only_current_phase(tmp_path):
    env = _env(tmp_path, min_green=20)
    env.reset()

    assert env.action_masks()["A"].tolist() == [True, False]


def test_switch_counts_clearance_once_and_updates_service_timers(tmp_path):
    env = _env(tmp_path)
    env.reset()
    observations, rewards, _, info = env.step({"A": 1})

    assert info["phase_switches"] == 1
    assert info["intergreen_vehicle_seconds"] == 3.0
    assert rewards["A"] == -5.05
    assert env._time_since_service["A"] == [10.0, 0.0]
    assert info["max_red_seconds"] == 10.0
    assert info["per_agent_queue"] == {"A": 5.0}
    assert observations["A"].ndim == 1


def test_injected_phase_encoder_produces_phase_rows(tmp_path):
    roadnet = _roadnet(tmp_path)
    encoder = PhaseFeatureEncoder(roadnet, count_norm=20.0, capacity_norm=40.0)
    env = MultiAgentTrafficEnv(roadnet, FakeEngine(), encoder=encoder,
                               action_interval=1, min_green=0)

    observations = env.reset()

    assert observations["A"].shape == (2, 12)
    np.testing.assert_array_equal(env.action_masks()["A"], [True, True])


def test_reward_weights_local_queue_and_downstream_blocking(tmp_path):
    roadnet = _roadnet(tmp_path)
    engine = FakeEngine(
        vehicle_counts={"rin_0": 3, "rin_1": 2, "rout_0": 4},
        waiting_counts={"rin_0": 3, "rin_1": 2, "rout_0": 4})
    env = MultiAgentTrafficEnv(
        roadnet, engine, action_interval=1, min_green=0,
        reward_type="queue_norm", queue_weight=1.0,
        downstream_block_weight=0.2, switch_penalty=0.0)
    env.reset()

    _, rewards, _, _ = env.step({"A": 0})

    assert rewards["A"] == -3.3  # -mean(3,2) - 0.2 * mean(4)


def test_info_reports_completion_from_active_and_finished_vehicles(tmp_path):
    env = _env(tmp_path, action_interval=1)
    env.engine.finished_vehicle_count = lambda: 6
    env.reset()

    _, _, _, info = env.step({"A": 0})

    assert info["arrived"] == 6
    assert info["active_vehicles"] == 5
    assert info["completion_rate"] == 6.0 / 11.0


def test_info_tracks_completed_vehicle_ids_when_engine_has_no_counter(tmp_path):
    env = _env(tmp_path, action_interval=1)
    env.engine.vehicle_ids = lambda: (
        ["finished", "active"] if env.engine._t == 0 else ["active"])
    env.reset()

    _, _, _, info = env.step({"A": 0})

    assert info["arrived"] == 1
    assert info["active_vehicles"] == 1
    assert info["completion_rate"] == 0.5
