import pytest

from traffic_rl.agents.max_pressure import (
    HystereticMaxPressureController,
    MaxPressureController,
)

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


def test_hysteretic_pressure_waits_and_requires_improvement_margin():
    c = HystereticMaxPressureController(StubNet(), min_hold_decisions=2,
                                        switch_threshold=2)
    weak = {"waiting_counts": {"rin_0": 5, "rin_1": 6, "rout_0": 0},
            "observations": {}, "action_masks": {}}
    strong = {"waiting_counts": {"rin_0": 1, "rin_1": 9, "rout_0": 0},
              "observations": {}, "action_masks": {}}
    assert c.act(strong) == {"A": 0}
    assert c.act(strong) == {"A": 0}
    assert c.act(weak) == {"A": 0}  # improvement is below threshold
    assert c.act(strong) == {"A": 1}
    c.reset()
    assert c.act(strong) == {"A": 0}



@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_forced_mask_overrides_pressure_and_hysteretic_hold(controller_class):
    controller = controller_class(StubNet())
    context = {"waiting_counts": {"rin_0": 100, "rin_1": 0},
               "action_masks": {"A": [False, True]}}

    assert controller.act(context) == {"A": 1}


@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_no_valid_real_action_fails_closed(controller_class):
    controller = controller_class(StubNet())
    context = {"waiting_counts": {}, "action_masks": {"A": [False, False, True]}}

    with pytest.raises(ValueError, match="valid.*A"):
        controller.act(context)


class ThreePhaseNet(StubNet):
    def green_phases(self, i):
        return [0, 2, 4]

    def phase_movements(self, i, p):
        return (["rin_%d" % (p // 2)], ["rout_0"])


@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_invalid_current_uses_highest_pressure_valid_action(controller_class):
    controller = controller_class(ThreePhaseNet())
    context = {"waiting_counts": {"rin_0": 100, "rin_1": 1, "rin_2": 2},
               "action_masks": {"A": [False, True, True]}}

    assert controller.act(context) == {"A": 2}


@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_masked_fallback_ties_use_lowest_valid_index(controller_class):
    controller = controller_class(ThreePhaseNet())
    context = {"waiting_counts": {"rin_0": 100, "rin_1": 2, "rin_2": 2},
               "action_masks": {"A": [False, True, True]}}

    assert controller.act(context) == {"A": 1}


def test_hysteretic_hold_and_margin_apply_among_valid_actions_after_forcing():
    controller = HystereticMaxPressureController(
        ThreePhaseNet(), min_hold_decisions=2, switch_threshold=2)
    forced = {"waiting_counts": {}, "action_masks": {"A": [False, True, False]}}
    valid = {"waiting_counts": {"rin_0": 100, "rin_1": 2, "rin_2": 10},
             "action_masks": {"A": [False, True, True]}}

    assert controller.act(forced) == {"A": 1}
    assert controller.act(valid) == {"A": 1}  # hold survives mask release
    valid["waiting_counts"]["rin_2"] = 3
    assert controller.act(valid) == {"A": 1}  # margin is insufficient
    valid["waiting_counts"]["rin_2"] = 10
    assert controller.act(valid) == {"A": 2}


@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_pressure_controllers_obey_environment_maximum_red(tmp_path, controller_class):
    from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
    from tests.conftest import FakeEngine
    from tests.sim.test_multi_agent_env import _net

    roadnet = _net(tmp_path)
    engine = FakeEngine(waiting_counts={"rin_0": 100, "rin_1": 0, "rout_0": 0})
    env = MultiAgentTrafficEnv(roadnet, engine, action_interval=10, min_green=20,
                               maximum_red=180, max_steps=400)
    controller = controller_class(roadnet)
    observations = env.reset()
    done = False
    while not done:
        masks = env.action_masks()
        actions = controller.act({"waiting_counts": env.current_waiting_counts(),
                                  "observations": observations, "action_masks": masks})
        assert all(masks[agent][action] for agent, action in actions.items())
        observations, _, done, info = env.step(actions)

    assert info["phase_switches"] > 0
    assert info["max_red_seconds"] <= 180


@pytest.mark.parametrize("controller_class", [MaxPressureController,
                                               HystereticMaxPressureController])
def test_sumo_all_valid_mask_preserves_unmasked_pressure_decisions(controller_class):
    from pathlib import Path
    from traffic_rl.sim.sumo_single_junction import SumoSingleJunctionEnv

    pytest.importorskip("sumolib")
    root = Path(__file__).parents[2]
    env = SumoSingleJunctionEnv(
        root / "results/research_pilot/generated/danang_isolated_published.net.xml",
        root / "results/research_pilot/generated/observed_normal.rou.xml", 1395)
    masked = controller_class(env.roadnet)
    historical = controller_class(env.roadnet)
    assert env.action_masks()[env.tls_id].tolist() == [True, True, True]
    lanes = [lane for movements in masked._mov[env.tls_id]
             for lane in movements[0]]
    for tick in range(12):
        waiting = {lane: (index * 7 + tick * 3) % 19
                   for index, lane in enumerate(lanes)}
        assert masked.act({"waiting_counts": waiting, "action_masks": env.action_masks()}) \
            == historical.act({"waiting_counts": waiting})
