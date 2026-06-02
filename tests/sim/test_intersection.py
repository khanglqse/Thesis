import pytest

from traffic_rl.sim.intersection import (
    IntersectionState, pressure_reward, queue_reward, queue_norm_reward,
    pressure_norm_reward, make_reward)


def test_observation_concatenates_incoming_counts_and_phase():
    state = IntersectionState(
        inter_id="A",
        incoming_lanes=["r1_0", "r1_1"],
        outgoing_lanes=["r2_0"],
        num_phases=2,
    )
    lane_counts = {"r1_0": 3, "r1_1": 5, "r2_0": 1}
    obs = state.observation(lane_counts, current_phase=1)
    # [count(r1_0), count(r1_1), one-hot phase(2)]
    assert list(obs) == [3.0, 5.0, 0.0, 1.0]


def test_pressure_reward_is_negative_incoming_minus_outgoing():
    state = IntersectionState(
        inter_id="A",
        incoming_lanes=["r1_0"],
        outgoing_lanes=["r2_0"],
        num_phases=2,
    )
    # pressure = |sum_in - sum_out| ; reward = -pressure
    waiting = {"r1_0": 7, "r2_0": 2}
    assert pressure_reward(state, waiting) == -5.0


def test_pressure_reward_is_signed_negative_inflow():
    st = IntersectionState("A", ["i0", "i1"], ["o0"], num_phases=2)
    # incoming queue 5, outgoing queue 2 -> pressure 3 -> reward -3
    assert pressure_reward(st, {"i0": 3, "i1": 2, "o0": 2}) == -3.0


def test_pressure_reward_positive_when_outflow_dominates():
    st = IntersectionState("A", ["i0"], ["o0", "o1"], num_phases=2)
    # incoming 1, outgoing 4 -> pressure -3 -> reward +3 (signed, not abs)
    assert pressure_reward(st, {"i0": 1, "o0": 1, "o1": 3}) == 3.0


def test_queue_reward_ignores_outflow():
    st = IntersectionState("A", ["i0", "i1"], ["o0"], num_phases=2)
    # only incoming counts: -(3+2) = -5, regardless of outgoing queue
    assert queue_reward(st, {"i0": 3, "i1": 2, "o0": 99}) == -5.0


def test_queue_norm_reward_divides_by_incoming_lane_count():
    st = IntersectionState("A", ["i0", "i1"], ["o0"], num_phases=2)
    # -(3+2)/2 incoming lanes = -2.5
    assert queue_norm_reward(st, {"i0": 3, "i1": 2, "o0": 1}) == -2.5


def test_pressure_norm_reward_divides_by_total_lane_count():
    st = IntersectionState("A", ["i0", "i1"], ["o0"], num_phases=2)
    # pressure -(5-2)= -3 over (2 in + 1 out)=3 lanes -> -1.0
    assert pressure_norm_reward(st, {"i0": 3, "i1": 2, "o0": 2}) == -1.0


def test_make_reward_dispatches_and_rejects_unknown():
    assert make_reward("pressure") is pressure_reward
    assert make_reward("queue") is queue_reward
    assert make_reward() is pressure_reward
    with pytest.raises(ValueError):
        make_reward("nope")
