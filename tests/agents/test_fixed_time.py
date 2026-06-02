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


def test_hold_count_rounds_and_is_at_least_one():
    assert FixedTimeController({"A": 2}, green_duration=50, action_interval=10)._hold == 5
    assert FixedTimeController({"A": 2}, green_duration=25, action_interval=10)._hold == 2
    # never below 1 even if green_duration < interval
    assert FixedTimeController({"A": 2}, green_duration=3, action_interval=10)._hold == 1


def test_reset_restarts_cycle():
    c = FixedTimeController(num_actions={"A": 2}, green_duration=10, action_interval=10)
    c.act(CTX); c.reset()
    assert c.act(CTX) == {"A": 0}
