import pytest

from traffic_rl.eval.network_metrics import NetworkMetricAccumulator
from traffic_rl.eval.runner import run_episode
from traffic_rl.sim.engine import CityFlowEngine


def _snapshot(**overrides):
    value = {
        "queued": 0,
        "running": 0,
        "departed": 0,
        "arrived": 0,
        "travel_times": [],
        "per_node_queue": {},
        "spillback_lanes": [],
        "phase_switches": 0,
        "intergreen_seconds": 0,
        "max_red_seconds": 0,
    }
    value.update(overrides)
    return value


def test_queue_integral_uses_every_simulation_step():
    metrics = NetworkMetricAccumulator(step_seconds=1)
    metrics.observe(_snapshot(queued=2))
    metrics.observe(_snapshot(queued=2))
    metrics.observe(_snapshot(queued=0))

    result = metrics.finalize()

    assert result["queue_integral_vehicle_seconds"] == 4
    assert result["queue_integral_vehicle_hours"] == pytest.approx(4 / 3600)
    assert result["observed_steps"] == 3


def test_travel_time_is_reported_with_completion_and_pending_accounts():
    metrics = NetworkMetricAccumulator(step_seconds=1)
    metrics.observe(_snapshot(
        departed=10,
        arrived=5,
        running=3,
        travel_times=[20, 30, 40, 50, 60],
    ))

    result = metrics.finalize()

    assert result["completion_rate"] == 0.5
    assert result["pending"] == 5
    assert result["running"] == 3
    assert result["travel_time_completed_mean"] == 40
    assert result["travel_time_completed_median"] == 40
    assert result["travel_time_completed_p95"] == pytest.approx(58)


def test_per_node_and_signal_metrics_cover_the_full_horizon():
    metrics = NetworkMetricAccumulator(step_seconds=2)
    metrics.observe(_snapshot(
        per_node_queue={"A": 2, "B": 1}, spillback_lanes=["A_0"],
        phase_switches=1, intergreen_seconds=2, max_red_seconds=8,
    ))
    metrics.observe(_snapshot(
        per_node_queue={"A": 5, "B": 0}, spillback_lanes=["A_0", "B_0"],
        phase_switches=3, intergreen_seconds=6, max_red_seconds=12,
    ))

    result = metrics.finalize()

    assert result["per_node_max_queue"] == {"A": 5.0, "B": 1.0}
    assert result["per_node_queue_integral_vehicle_seconds"] == {"A": 14.0, "B": 2.0}
    assert result["spillback_lane_seconds"] == {"A_0": 4.0, "B_0": 2.0}
    assert result["phase_switches"] == 3
    assert result["intergreen_seconds"] == 6
    assert result["max_red_seconds"] == 12


def test_invalid_snapshot_fails_closed():
    metrics = NetworkMetricAccumulator(step_seconds=1)
    with pytest.raises(ValueError, match="missing snapshot fields"):
        metrics.observe({"queued": 1})
    with pytest.raises(ValueError, match="non-negative"):
        metrics.observe(_snapshot(queued=-1))


def test_empty_accumulator_reports_no_completed_travel_time():
    result = NetworkMetricAccumulator(step_seconds=1).finalize()
    assert result["completion_rate"] is None
    assert result["travel_time_completed_mean"] is None
    assert result["observed_steps"] == 0


def test_engine_snapshot_groups_lane_queues_without_advancing_simulator():
    class NativeEngine(object):
        def __init__(self):
            self.steps = 0

        def get_lane_waiting_vehicle_count(self):
            return {"a_0": 3, "b_0": 2, "outside_0": 1}

        def get_vehicle_count(self):
            return 4

        def get_finished_vehicle_count(self):
            return 6

        def next_step(self):
            self.steps += 1

    engine = CityFlowEngine.__new__(CityFlowEngine)
    engine._eng = NativeEngine()

    result = engine.network_metric_snapshot(
        lane_to_node={"a_0": "A", "b_0": "B"},
        spillback_lanes={"a_0"},
        phase_switches=7,
        intergreen_seconds=9,
        max_red_seconds=31,
    )

    assert result["queued"] == 6
    assert result["per_node_queue"] == {"A": 3.0, "B": 2.0}
    assert result["departed"] == 10
    assert result["arrived"] == 6
    assert result["spillback_lanes"] == ["a_0"]
    assert engine._eng.steps == 0


def test_runner_preserves_complete_network_metric_contract():
    final_metrics = {
        "observed_steps": 2,
        "queue_integral_vehicle_seconds": 12.0,
        "queue_integral_vehicle_hours": 12.0 / 3600.0,
        "travel_time_completed_mean": 42.0,
        "completion_rate": 0.75,
        "departed": 8,
        "arrived": 6,
        "running": 2,
        "pending": 2,
    }

    class Env(object):
        agent_ids = ["A"]

        def reset(self):
            return {"A": [0]}

        def action_masks(self):
            return {"A": [True]}

        def current_waiting_counts(self):
            return {"a_0": 1}

        def step(self, actions):
            return {"A": [0]}, {"A": 0}, True, {
                "step": 2,
                "total_queue": 6,
                "network_metrics": final_metrics,
            }

    class Controller(object):
        name = "contract-controller"

        def act(self, context):
            return {"A": 0}

    result = run_episode(Env(), Controller())

    assert result["queue_integral_vehicle_seconds"] == 12.0
    assert result["travel_time_completed_mean"] == 42.0
    assert result["completion_rate"] == 0.75
