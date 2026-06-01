import json
import numpy as np
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.train.trainer import train
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
                {"time": 6, "availableRoadLinks": []},
                {"time": 39, "availableRoadLinks": [1]}]},
        }],
        "roads": [{"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
                  {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]}],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data)); return RoadNet.load(str(p))

def _env_factory(tmp_path):
    rn = _net(tmp_path)
    def make():
        return MultiAgentTrafficEnv(rn, FakeEngine(waiting_counts={"rin_0": 1, "rin_1": 1}),
                                    action_interval=2, yellow_time=1, min_green=0, max_steps=6)
    return make

def test_train_runs_and_checkpoints(tmp_path):
    cfg = {"episodes": 2, "max_steps": 6, "hidden": 8, "lr": 1e-3, "gamma": 0.9,
           "batch_size": 8, "buffer_capacity": 1000, "train_start": 4,
           "target_sync": 5, "epsilon_start": 1.0, "epsilon_end": 0.1,
           "epsilon_decay_steps": 20, "seed": 0}
    ckpt = tmp_path / "dqn.npz"; log = tmp_path / "log.json"
    net = train(_env_factory(tmp_path), cfg, ckpt_path=str(ckpt), log_path=str(log))
    assert ckpt.exists()
    rec = json.loads(log.read_text())
    assert len(rec["episodes"]) == 2
    assert "mean_reward" in rec["episodes"][0]
    q = net.q_values(np.zeros((1, net.W1.shape[0]), np.float32))
    assert q.shape[1] == net.W3.shape[1]
