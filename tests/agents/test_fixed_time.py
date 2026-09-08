import pytest

from traffic_rl.agents.fixed_time import FixedTimeController

CTX = {"observations": {}, "waiting_counts": {}, "action_masks": {}}


def test_round_robin_when_green_equals_interval():
    # green_duration == action_interval -> hold=1 -> switch every decision (legacy)
    c = FixedTimeController(num_actions={"A": 2, "B": 3}, green_duration=10,
                            action_interval=10)
    assert c.act(CTX) == {"A": 0, "B": 0}
    assert c.act(CTX) == {"A": 1, "B": 1}
    assert c.act(CTX) == {"A": 0, "B": 2}   # A wraps at 2, B continues
    assert c.act(CTX) == {"A": 1, "B": 0}   # B wraps at 3


def test_holds_each_phase_for_green_duration():
    # 30s green / 10s interval -> hold each phase for 3 decisions before advancing
    c = FixedTimeController(num_actions={"A": 2}, green_duration=30,
                            action_interval=10)
    assert [c.act(CTX)["A"] for _ in range(7)] == [0, 0, 0, 1, 1, 1, 0]


@pytest.mark.parametrize("duration,expected", [
    (25, [0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0]),
    (35, [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0]),
])
def test_nonmultiple_duration_keeps_nominal_cycle(duration, expected):
    controller = FixedTimeController({"A": 2}, duration, action_interval=10)
    assert [controller.act(CTX)["A"] for _ in expected] == expected


def test_masked_requests_use_valid_phase_without_resetting_schedule():
    controller = FixedTimeController({"A": 3}, 10, action_interval=10)
    masked = {"action_masks": {"A": [False, False, True, False]}}
    assert controller.act(masked) == {"A": 2}
    assert controller.act(masked) == {"A": 2}
    assert controller.act(CTX) == {"A": 2}
    assert controller.act(CTX) == {"A": 0}


def test_short_duration_keeps_at_least_one_decision_per_phase():
    controller = FixedTimeController({"A": 3}, 3, action_interval=10)
    assert [controller.act(CTX)["A"] for _ in range(4)] == [0, 1, 2, 0]


def test_reset_restarts_cycle():
    c = FixedTimeController(num_actions={"A": 2}, green_duration=10, action_interval=10)
    c.act(CTX); c.reset()
    assert c.act(CTX) == {"A": 0}
