from traffic_rl.sim.encoder import ObservationEncoder


class StubNetNbr:
    def signalized_ids(self): return ["A", "B"]
    def incoming_lanes(self, i): return {"A": ["a0", "a1"], "B": ["b0"]}[i]
    def outgoing_lanes(self, i): return {"A": ["ao0"], "B": ["bo0"]}[i]
    def green_phases(self, i): return {"A": [0, 2], "B": [0, 2]}[i]
    def upstream_neighbors(self, i): return {"A": [], "B": ["A"]}[i]   # A feeds B


def test_neighbor_dims():
    enc = ObservationEncoder(StubNetNbr(), count_norm=10.0, state_mode="neighbor")
    assert enc.obs_dim == 2 + 1 + 2 + 2          # max_in + max_out + max_green + 2 nbr


def test_neighbor_feature_pools_upstream():
    enc = ObservationEncoder(StubNetNbr(), count_norm=10.0, state_mode="neighbor")
    counts = {"b0": 1, "a0": 10, "a1": 10, "ao0": 4}
    v = enc.encode("B", counts, green_index=0)
    base = enc.max_in + enc.max_out + enc.max_green
    assert abs(v[base] - 1.0) < 1e-6             # nbr incoming mean (10+10)/2/10
    assert abs(v[base + 1] - 0.4) < 1e-6         # nbr outgoing mean 4/1/10


def test_isolated_agent_zero_neighbor_feats():
    enc = ObservationEncoder(StubNetNbr(), count_norm=10.0, state_mode="neighbor")
    v = enc.encode("A", {"a0": 5}, green_index=0)   # A has no upstream neighbours
    base = enc.max_in + enc.max_out + enc.max_green
    assert v[base] == 0.0 and v[base + 1] == 0.0
