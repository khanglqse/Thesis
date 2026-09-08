import json
import numpy as np
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
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=100)
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
