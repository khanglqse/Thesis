import numpy as np
from traffic_rl.sim.encoder import ObservationEncoder

class StubNet:
    # two agents with different #incoming lanes and #green phases
    def signalized_ids(self): return ["A", "B"]
    def incoming_lanes(self, i): return {"A": ["a0", "a1"], "B": ["b0"]}[i]
    def green_phases(self, i): return {"A": [0, 2], "B": [0, 2, 4]}[i]

def test_dims_are_global_max():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    assert enc.max_in == 2 and enc.max_green == 3
    assert enc.obs_dim == 2 + 3  # padded lanes + padded one-hot

def test_encode_normalizes_pads_and_one_hots():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    # agent B has 1 lane (queue 5) and is at its 2nd green phase (green index 1)
    v = enc.encode("B", lane_counts={"b0": 5}, green_index=1)
    assert v.shape == (5,)
    # lane part: [0.5, 0(pad)] ; phase one-hot over 3: [0,1,0]
    assert np.allclose(v, [0.5, 0.0, 0.0, 1.0, 0.0])

def test_action_mask_marks_valid_greens():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    np.testing.assert_array_equal(enc.action_mask("A"), [True, True, False])
    np.testing.assert_array_equal(enc.action_mask("B"), [True, True, True])
