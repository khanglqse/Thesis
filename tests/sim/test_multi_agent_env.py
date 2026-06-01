import json

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

SAMPLE = {
    "intersections": [
        {"id": "A", "virtual": False, "roads": ["r1", "r2"],
         "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": [1]}]},
         "roadLinks": [{"startRoad": "r1", "endRoad": "r2"}]},
        {"id": "V1", "virtual": True, "roads": ["r1"]},
        {"id": "V2", "virtual": True, "roads": ["r2"]},
    ],
    "roads": [
        {"id": "r1", "startIntersection": "V1", "endIntersection": "A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "r2", "startIntersection": "A", "endIntersection": "V2",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


class FakeEngine:
    def __init__(self):
        self.steps = 0
        self.phases = {}
    def reset(self): self.steps = 0
    def step(self): self.steps += 1
    def set_tl_phase(self, i, p): self.phases[i] = p
    def lane_vehicle_counts(self): return {"r1_0": 4, "r2_0": 1}
    def lane_waiting_counts(self): return {"r1_0": 4, "r2_0": 1}
    def vehicle_count(self): return 5
    def average_travel_time(self): return 12.0


def _env(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    return MultiAgentTrafficEnv(rn, FakeEngine(), action_interval=5)


def test_reset_returns_obs_per_agent(tmp_path):
    env = _env(tmp_path)
    obs = env.reset()
    assert list(obs.keys()) == ["A"]
    assert obs["A"].shape == (1 + 2,)   # 1 incoming lane + 2 phases


def test_step_applies_phase_and_returns_rewards(tmp_path):
    env = _env(tmp_path)
    env.reset()
    obs, rewards, done, info = env.step({"A": 1})
    assert env.engine.phases["A"] == 1
    assert env.engine.steps == 5         # action_interval sub-steps
    assert rewards["A"] == -3.0          # -|4 - 1|
    assert "A" in obs and not done


def test_agent_ids_are_signalized_only(tmp_path):
    env = _env(tmp_path)
    assert env.agent_ids == ["A"]
