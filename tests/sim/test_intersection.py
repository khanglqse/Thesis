from traffic_rl.sim.intersection import IntersectionState, pressure_reward


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
