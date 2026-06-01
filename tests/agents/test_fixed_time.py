from traffic_rl.agents.fixed_time import FixedTimeController


def test_cycles_phases_each_decision():
    ctrl = FixedTimeController(num_phases={"A": 2, "B": 3})
    assert ctrl.act() == {"A": 0, "B": 0}
    assert ctrl.act() == {"A": 1, "B": 1}
    assert ctrl.act() == {"A": 0, "B": 2}   # A wraps at 2, B continues
    assert ctrl.act() == {"A": 1, "B": 0}   # B wraps at 3


def test_reset_restarts_cycle():
    ctrl = FixedTimeController(num_phases={"A": 2})
    ctrl.act(); ctrl.act()
    ctrl.reset()
    assert ctrl.act() == {"A": 0}
