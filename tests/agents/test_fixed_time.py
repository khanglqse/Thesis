from traffic_rl.agents.fixed_time import FixedTimeController

def test_round_robin_over_green_choices():
    c = FixedTimeController(num_actions={"A": 2, "B": 3})
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    assert c.act(ctx) == {"A": 0, "B": 0}
    assert c.act(ctx) == {"A": 1, "B": 1}
    assert c.act(ctx) == {"A": 0, "B": 2}   # A wraps at 2, B continues
    assert c.act(ctx) == {"A": 1, "B": 0}   # B wraps at 3

def test_reset_restarts_cycle():
    c = FixedTimeController(num_actions={"A": 2})
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    c.act(ctx); c.reset()
    assert c.act(ctx) == {"A": 0}
