import json
import numpy as np
from traffic_rl.eval.network_metrics import NetworkMetricsObserver
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from tests.conftest import FakeEngine

def _net(tmp_path):
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
                {"time": 39, "availableRoadLinks": [0]},   # green idx 0 -> phase 0
                {"time": 6,  "availableRoadLinks": []},     # all-red -> phase 1
                {"time": 39, "availableRoadLinks": [1]},   # green idx 1 -> phase 2
                {"time": 6,  "availableRoadLinks": []},     # return transition
            ]},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]},
        ],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data))
    return RoadNet.load(str(p))

def test_num_actions_and_masks(tmp_path):
    env = MultiAgentTrafficEnv(_net(tmp_path), FakeEngine(),
                               action_interval=10, yellow_time=3, min_green=5)
    assert env.num_actions == {"A": 2}
    np.testing.assert_array_equal(env.action_masks()["A"], [True, True])

def test_keeping_phase_does_not_insert_yellow(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=0)
    env.reset()
    env.step({"A": 0})            # already at green 0 -> no switch
    assert len(eng.steps_of("step")) == 10
    assert ("set", "A", 1) not in eng.calls   # all-red phase never set

def test_switching_inserts_yellow_then_new_green(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=0)
    env.reset()
    env.step({"A": 1})            # switch green 0 -> green 1 (lightphase 2)
    assert ("set", "A", 1) in eng.calls       # all-red inserted
    assert ("set", "A", 2) in eng.calls       # new green lightphase
    assert len(eng.steps_of("step")) == 10

def test_min_green_blocks_early_switch(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10,
                               yellow_time=3, min_green=100, maximum_red=None)
    env.reset()
    env.step({"A": 1})            # min_green not satisfied -> stay on green 0
    assert ("set", "A", 1) not in eng.calls
    assert env._green["A"] == 0

def test_info_has_total_queue(tmp_path):
    eng = FakeEngine(waiting_counts={"rin_0": 2, "rin_1": 1, "rout_0": 0})
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=1, min_green=0)
    env.reset()
    _, rewards, _, info = env.step({"A": 0})
    assert info["total_queue"] == 3      # sum of all waiting lanes
    assert rewards["A"] == -3.0          # signed pressure: -(3 - 0)


def test_network_observer_is_sampled_after_every_engine_step(tmp_path):
    class TimelineEngine(FakeEngine):
        def __init__(self):
            FakeEngine.__init__(self)
            self._timeline = [
                ({"rin_0": 1}, ["v0"]),
                ({"rin_0": 3}, ["v0", "v1"]),
                ({"rin_0": 2}, ["v1"]),
                ({"rin_0": 0}, []),
            ]
            self._active = []

        def reset(self):
            FakeEngine.reset(self)
            self.waiting_counts = {}
            self.vehicle_counts = {}
            self._active = []

        def step(self):
            FakeEngine.step(self)
            waiting, active = self._timeline[self._t - 1]
            self.waiting_counts = dict(waiting)
            self.vehicle_counts = dict(waiting)
            self._active = list(active)

        def vehicle_ids(self):
            return list(self._active)

    observer = NetworkMetricsObserver(
        scheduled_vehicles=2,
        step_seconds=1,
        lane_to_node={"rin_0": "A"},
        spillback_thresholds={"rin_0": 3},
    )
    env = MultiAgentTrafficEnv(
        _net(tmp_path), TimelineEngine(), action_interval=2, max_steps=4,
        min_green=0, network_metric_observer=observer)

    env.reset()
    _, _, done, first = env.step({"A": 0})
    assert done is False
    assert first["network_metrics"]["observed_steps"] == 2
    assert first["network_metrics"]["queue_integral_vehicle_seconds"] == 4

    _, _, done, final = env.step({"A": 0})

    assert done is True
    metrics = final["network_metrics"]
    assert metrics["observed_steps"] == 4
    assert metrics["queue_integral_vehicle_seconds"] == 6
    assert metrics["per_node_queue_integral_vehicle_seconds"] == {"A": 6.0}
    assert metrics["spillback_lane_seconds"] == {"rin_0": 1.0}
    assert metrics["scheduled"] == 2
    assert metrics["inserted"] == 2
    assert metrics["arrived"] == 2
    assert metrics["running"] == 0
    assert metrics["pending"] == 0
    assert metrics["completed_travel_time_count"] == 2
    assert metrics["travel_time_completed_mean"] == 2
    assert final["completion_rate"] == 1.0
    assert final["scheduled"] == 2
