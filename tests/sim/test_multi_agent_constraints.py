import json
import hashlib

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
                {"time": 40, "availableRoadLinks": [0]},
                {"time": 3, "availableRoadLinks": []},
                {"time": 40, "availableRoadLinks": [1]},
                {"time": 3, "availableRoadLinks": []},
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
                               action_interval=10, min_green=0)

    observations = env.reset()

    assert observations["A"].shape == (2, 12)
    np.testing.assert_array_equal(env.action_masks()["A"], [True, True])


def test_reward_weights_local_queue_and_downstream_blocking(tmp_path):
    roadnet = _roadnet(tmp_path)
    engine = FakeEngine(
        vehicle_counts={"rin_0": 3, "rin_1": 2, "rout_0": 4},
        waiting_counts={"rin_0": 3, "rin_1": 2, "rout_0": 4})
    env = MultiAgentTrafficEnv(
        roadnet, engine, action_interval=10, min_green=0,
        reward_type="queue_norm", queue_weight=1.0,
        downstream_block_weight=0.2, switch_penalty=0.0)
    env.reset()

    _, rewards, _, _ = env.step({"A": 0})

    assert rewards["A"] == -3.3  # -mean(3,2) - 0.2 * mean(4)


def test_info_reports_completion_from_active_and_finished_vehicles(tmp_path):
    env = _env(tmp_path, action_interval=10)
    env.engine.finished_vehicle_count = lambda: 6
    env.reset()

    _, _, _, info = env.step({"A": 0})

    assert info["arrived"] == 6
    assert info["active_vehicles"] == 5
    assert info["completion_rate"] == 6.0 / 11.0


def test_info_tracks_completed_vehicle_ids_when_engine_has_no_counter(tmp_path):
    env = _env(tmp_path, action_interval=10)
    env.engine.vehicle_ids = lambda: (
        ["finished", "active"] if env.engine._t == 0 else ["active"])
    env.reset()

    _, _, _, info = env.step({"A": 0})

    assert info["arrived"] == 1
    assert info["active_vehicles"] == 1
    assert info["completion_rate"] == 0.5


def test_minimum_green_wins_after_max_red_forced_switch(tmp_path):
    env = _env(tmp_path, min_green=20, maximum_red=180)
    env.reset()
    env._elapsed_green["A"] = 20
    env._time_since_service["A"] = [0, 181]
    env.step({"A": 1})
    env._time_since_service["A"][0] = 181

    assert env._elapsed_green["A"] == 7.0
    assert env.action_masks()["A"].tolist() == [False, True]


def test_infeasible_maximum_red_configuration_fails_closed(tmp_path):
    with np.testing.assert_raises_regex(ValueError, "maximum_red"):
        _env(tmp_path, min_green=20, maximum_red=10)


def test_maximum_red_feasibility_includes_decision_granularity(tmp_path):
    roadnet = _roadnet(tmp_path)
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[:] = [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 3, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 3, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [0, 1]},
        {"time": 3, "availableRoadLinks": []},
    ]

    with np.testing.assert_raises_regex(ValueError, "maximum_red"):
        MultiAgentTrafficEnv(roadnet, FakeEngine(), action_interval=10,
                             min_green=20, maximum_red=50)


def test_switch_executes_nonempty_transition_without_exposing_it_as_action(tmp_path):
    roadnet = _roadnet(tmp_path)
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[1] = {"time": 5, "availableRoadLinks": [0]}
    engine = FakeEngine()
    env = MultiAgentTrafficEnv(roadnet, engine, action_interval=10,
                               min_green=0, maximum_red=180)
    env.reset()

    _, _, _, info = env.step({"A": 1})

    assert env.num_actions == {"A": 2}
    assert ("set", "A", 1) in engine.calls
    assert len(engine.steps_of("step")) == 10
    assert info["intergreen_vehicle_seconds"] == 0.0
    assert env._time_since_service["A"] == [5.0, 0.0]


def test_compound_service_resets_movements_but_only_clearance_is_lost_time(tmp_path):
    roadnet = _roadnet(tmp_path)
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[:] = [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 3, "availableRoadLinks": [0]},
        {"time": 2, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 2, "availableRoadLinks": []},
    ]
    env = MultiAgentTrafficEnv(roadnet, FakeEngine(), action_interval=10,
                               min_green=0, maximum_red=180)
    env.reset()

    _, _, _, info = env.step({"A": 1})

    assert roadnet.phase_role("A", 1) == "compound_service"
    assert roadnet.phase_role("A", 2) == "all_red"
    assert info["intergreen_vehicle_seconds"] == 2.0
    assert env._time_since_service["A"] == [7.0, 0.0]


def test_explicit_yellow_with_movements_is_clearance_not_service(tmp_path):
    _roadnet(tmp_path)
    roadnet_path = tmp_path / "roadnet.json"
    value = json.loads(roadnet_path.read_text())
    value["intersections"][0]["trafficLight"]["lightphases"][1] = {
        "time": 3, "availableRoadLinks": [0]}
    roadnet_path.write_text(json.dumps(value))
    fixture = RoadNet.load(str(roadnet_path))
    roles = ("selectable_green", "clearance_yellow",
             "selectable_green", "all_red")
    contract = {
        "schema_version": 1,
        "dataset_id": "fixture",
        "roadnet_sha256": hashlib.sha256(roadnet_path.read_bytes()).hexdigest(),
        "derivation": {"min_green_seconds": 20},
        "agents": {"A": {
            "selectable_phases": [0, 2],
            "transition_phases": [1, 3],
            "compound_phases": [],
            "phase_semantics": [
                {"phase_index": index, "duration_seconds": duration,
                 "source_state": "y" if role == "clearance_yellow" else "x",
                 "role": role,
                 "movements": fixture.phase_movement_records("A", index)}
                for index, (duration, role) in enumerate(
                    zip((40, 3, 40, 3), roles))],
            "transitions": {
                "0": {"2": [[1, 3]]}, "2": {"0": [[3, 3]]}},
        }},
    }
    contract_path = tmp_path / "phase-contract.json"
    contract_path.write_text(json.dumps(contract))
    roadnet = RoadNet.load(str(roadnet_path), str(contract_path),
                           require_phase_contract=True)
    env = MultiAgentTrafficEnv(roadnet, FakeEngine(), action_interval=10,
                               min_green=0, maximum_red=180)
    env.reset()

    _, _, _, info = env.step({"A": 1})

    assert info["intergreen_vehicle_seconds"] == 3.0
    assert env._time_since_service["A"] == [10.0, 0.0]


def test_long_transition_sequence_continues_across_decision_intervals(tmp_path):
    roadnet = _roadnet(tmp_path)
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[:] = [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 3, "availableRoadLinks": []},
        {"time": 3, "availableRoadLinks": []},
        {"time": 3, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 3, "availableRoadLinks": []},
    ]
    engine = FakeEngine()
    env = MultiAgentTrafficEnv(roadnet, engine, action_interval=5,
                               min_green=0, maximum_red=180)
    env.reset()

    env.step({"A": 1})
    assert env._green["A"] == 0
    assert env.action_masks()["A"].tolist() == [True, False]
    _, _, _, info = env.step({"A": 0})

    assert env._green["A"] == 1
    assert info["step"] == 10
    assert info["intergreen_vehicle_seconds"] == 9.0
    assert env._elapsed_green["A"] == 1.0
    assert ("set", "A", 1) in engine.calls
    assert ("set", "A", 2) in engine.calls
    assert ("set", "A", 3) in engine.calls
    assert ("set", "A", 4) in engine.calls


def test_maximum_red_includes_clearance_and_reports_episode_peak(tmp_path):
    roadnet = _roadnet(tmp_path)
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[:] = [
        {"time": 40, "availableRoadLinks": [0]},
        {"time": 6, "availableRoadLinks": []},
        {"time": 6, "availableRoadLinks": []},
        {"time": 6, "availableRoadLinks": []},
        {"time": 40, "availableRoadLinks": [1]},
        {"time": 6, "availableRoadLinks": []},
    ]
    env = MultiAgentTrafficEnv(roadnet, FakeEngine(), action_interval=10,
                               min_green=20, maximum_red=180, max_steps=400)
    env.reset()
    info = None
    for _ in range(30):
        mask = env.action_masks()["A"]
        action = env._green["A"]
        if not mask[action]:
            action = int(np.flatnonzero(mask)[0])
        _, _, _, info = env.step({"A": action})
        if env._green["A"] == 1 and env._pending_transitions["A"] is None:
            break

    assert env._green["A"] == 1
    assert info["max_red_seconds"] <= 180
    assert info["max_red_seconds"] >= 100
    assert info["max_red_seconds"] > max(env._time_since_service["A"])


def test_maximum_red_bound_serves_multiple_urgent_phases(tmp_path):
    roadnet = _roadnet(tmp_path)
    roadnet._road_by_id["rin"]["lanes"].append({})
    roadnet._by_id["A"]["roadLinks"].append({
        "startRoad": "rin", "endRoad": "rout",
        "laneLinks": [{"startLaneIndex": 2, "endLaneIndex": 0}]})
    phases = roadnet._by_id["A"]["trafficLight"]["lightphases"]
    phases[:] = []
    for movement in ([0], [1], [2]):
        phases.append({"time": 40, "availableRoadLinks": movement})
        phases.extend({"time": 6, "availableRoadLinks": []}
                      for _ in range(3))
    env = MultiAgentTrafficEnv(roadnet, FakeEngine(), action_interval=10,
                               min_green=20, maximum_red=180, max_steps=800)
    env.reset()
    served = {0}
    info = None
    while True:
        mask = env.action_masks()["A"]
        action = env._green["A"]
        if not mask[action]:
            action = int(np.flatnonzero(mask)[0])
        _, _, done, info = env.step({"A": action})
        served.add(env._green["A"])
        assert info["max_red_seconds"] <= 180
        if done:
            break

    assert served == {0, 1, 2}
