import json
import numpy as np
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode
from tests.conftest import FakeEngine

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": [{"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                          {"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]}],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},
                {"time": 1, "availableRoadLinks": []},
                {"time": 39, "availableRoadLinks": [1]},
                {"time": 1, "availableRoadLinks": []}]},
        }],
        "roads": [{"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
                  {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]}],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data)); return RoadNet.load(str(p))

def test_run_episode_returns_metrics(tmp_path):
    eng = FakeEngine(waiting_counts={"rin_0": 2, "rin_1": 1, "rout_0": 0})
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=2,
                               yellow_time=1, min_green=0, max_steps=6)
    ctrl = FixedTimeController(num_actions=env.num_actions)
    m = run_episode(env, ctrl)
    assert m["controller"] == "FixedTime"
    assert m["steps"] == 6
    assert m["agents"] == 1
    assert "final_average_travel_time" in m
    assert m["mean_total_queue"] == 3.0      # constant 3 each decision
    assert m["queue_integral_vehicle_seconds"] == 18.0  # 3 queued * 6 simulator seconds
    assert m["queue_integral_vehicle_hours"] == 18.0 / 3600.0
    assert "mean_reward" in m
    assert m["scheduled"] is None
    assert m["inserted"] is None
    assert m["arrived"] is None
    assert m["pending"] is None
    assert m["collisions"] is None
