import numpy as np
from traffic_rl.sim.encoder import ObservationEncoder

class StubNet:
    # two agents with different #incoming/outgoing lanes and #green phases
    def signalized_ids(self): return ["A", "B"]
    def incoming_lanes(self, i): return {"A": ["a0", "a1"], "B": ["b0"]}[i]
    def outgoing_lanes(self, i): return {"A": ["ao0"], "B": ["bo0", "bo1"]}[i]
    def green_phases(self, i): return {"A": [0, 2], "B": [0, 2, 4]}[i]

def test_dims_are_global_max():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    assert enc.max_in == 2 and enc.max_out == 2 and enc.max_green == 3
    assert enc.obs_dim == 2 + 2 + 3  # incoming + outgoing + one-hot

def test_encode_normalizes_pads_and_one_hots():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    # agent B: 1 incoming (queue 5), 2 outgoing (queues 3, 0), 2nd green (index 1)
    v = enc.encode("B", lane_counts={"b0": 5, "bo0": 3}, green_index=1)
    assert v.shape == (7,)
    # incoming [0.5, 0(pad)] | outgoing [0.3, 0.0] | one-hot over 3 [0,1,0]
    assert np.allclose(v, [0.5, 0.0, 0.3, 0.0, 0.0, 1.0, 0.0])

def test_action_mask_marks_valid_greens():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    np.testing.assert_array_equal(enc.action_mask("A"), [True, True, False])
    np.testing.assert_array_equal(enc.action_mask("B"), [True, True, True])


def test_ats_mode_dims_and_running_channel():
    enc = ObservationEncoder(StubNet(), count_norm=10.0, state_mode="ats")
    # incoming queue (2) + incoming running (2) + outgoing queue (2) + green (3)
    assert enc.obs_dim == 2 * 2 + 2 + 3
    # agent A: a0 has 8 total / 5 queued -> running 3; a1 has 4 total / 4 queued -> 0
    all_counts = {"a0": 8, "a1": 4, "ao0": 2}
    waiting = {"a0": 5, "a1": 4, "ao0": 2}
    v = enc.encode("A", all_counts, green_index=0, waiting_counts=waiting)
    assert v.shape == (9,)
    # queue[a0,a1]=.5,.4 | running[a0,a1]=.3,.0 | out queue[ao0,pad]=.2,0 | onehot[1,0,0]
    np.testing.assert_allclose(v, [0.5, 0.4, 0.3, 0.0, 0.2, 0.0, 1.0, 0.0, 0.0])


def test_unknown_state_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        ObservationEncoder(StubNet(), state_mode="bogus")
