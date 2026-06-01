import json

import pytest

from traffic_rl.sim.engine import CityFlowEngine


@pytest.mark.docker
def test_engine_runs_subarea_and_reports_lane_counts(tmp_path):
    cfg = {
        "interval": 1.0, "seed": 0, "dir": "data/danang/",
        "roadnetFile": "roadnet_subarea.json", "flowFile": "flow_subarea.json",
        "rlTrafficLight": True, "laneChange": False, "saveReplay": False,
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))

    eng = CityFlowEngine(str(cfg_path))
    eng.reset()
    for _ in range(50):
        eng.step()
    counts = eng.lane_vehicle_counts()
    assert isinstance(counts, dict)
    assert eng.vehicle_count() >= 0
