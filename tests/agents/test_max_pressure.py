from traffic_rl.agents.max_pressure import MaxPressureController

class StubNet:
    def signalized_ids(self): return ["A"]
    def green_phases(self, i): return [0, 2]
    def phase_movements(self, i, p):
        # green 0 serves rin_0->rout_0 ; green 2 serves rin_1->rout_0
        return {0: (["rin_0"], ["rout_0"]),
                2: (["rin_1"], ["rout_0"])}[p]

def test_picks_phase_with_max_pressure():
    c = MaxPressureController(StubNet())
    ctx = {"waiting_counts": {"rin_0": 1, "rin_1": 9, "rout_0": 0},
           "observations": {}, "action_masks": {}}
    # pressure(green0)=1-0=1 ; pressure(green1)=9-0=9 -> choose index 1
    assert c.act(ctx) == {"A": 1}

def test_ties_pick_lowest_index():
    c = MaxPressureController(StubNet())
    ctx = {"waiting_counts": {"rin_0": 5, "rin_1": 5, "rout_0": 0},
           "observations": {}, "action_masks": {}}
    assert c.act(ctx) == {"A": 0}
