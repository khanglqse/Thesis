import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]


@pytest.mark.skipif(shutil.which("sumo") is None, reason="SUMO is unavailable")
def test_sumo_env_runs_safe_actions_and_reports_vehicle_accounting():
    from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv

    env = SumoSingleJunctionEnv(
        network_path=ROOT / "results/research_pilot/generated/danang_isolated_published.net.xml",
        route_path=ROOT / "results/research_pilot/generated/observed_normal.rou.xml",
        scheduled_vehicles=1395,
        seed=17,
        action_interval=10,
        max_steps=20,
        yellow_time=7,
        min_green=10,
    )
    try:
        obs = env.reset()
        assert obs["danang_ntn_cmt8_29"].shape == (16,)
        _, _, done, first = env.step({"danang_ntn_cmt8_29": 0})
        assert not done
        _, _, done, second = env.step({"danang_ntn_cmt8_29": 1})
        assert done
        assert env.current_green == 1
        assert second["inserted"] + second["pending"] <= 1395
        assert second["running"] == second["vehicle_count"]
        assert second["queue_integral_vehicle_seconds"] >= first[
            "queue_integral_vehicle_seconds"
        ]
        assert second["collisions"] == 0
        assert second["emergency_braking"] == 0
    finally:
        env.close()


@pytest.mark.skipif(shutil.which("sumo") is None, reason="SUMO is unavailable")
def test_static_mode_preserves_the_published_32_plus_7_second_first_stage():
    from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv

    env = SumoSingleJunctionEnv(
        network_path=ROOT / "results/research_pilot/generated/danang_isolated_published.net.xml",
        route_path=ROOT / "results/research_pilot/generated/observed_normal.rou.xml",
        scheduled_vehicles=1395,
        action_interval=10,
        max_steps=40,
        control_mode="static_program",
    )
    try:
        env.reset()
        info = None
        for _ in range(4):
            _, _, done, info = env.step({"danang_ntn_cmt8_29": 2})
        assert done
        assert env.current_green == 1
        assert env._connection.trafficlight.getPhase("danang_ntn_cmt8_29") == 2
        assert info["phase_switches"] == 1
        env.close()
        assert env.final_safety_metrics() == {
            "collisions": 0,
            "emergency_braking": 0,
        }
    finally:
        env.close()
