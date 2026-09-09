import json
from pathlib import Path

import pytest

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.schedule_residual import (
    ShadowSignal, audit_timelines, compile_block, signal_state)


@pytest.fixture(scope="module")
def network():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "results/haichau_network_v2/experiment-manifest.json").read_text())
    return RoadNet.load(str(root / manifest["network"]["path"]),
                       str(root / manifest["phase_contract"]["path"]),
                       require_phase_contract=True)


def representative(network, count):
    return next(node for node in network.signalized_ids()
                if len(network.green_phases(node)) == count)


@pytest.mark.parametrize("count", [2, 3])
def test_one_deviation_then_nominal_masked_fallback_persists(network, count):
    node = representative(network, count)
    shadow = ShadowSignal(network, node)
    baseline = shadow.reference(0, 600)
    changed = shadow.nominal_with_override(600, {20: 1})
    audit = audit_timelines(baseline["trace"], changed["trace"])
    assert changed["explicit_overrides"] == 1
    assert audit["phase_divergence_seconds"] >= 300
    assert audit["last_phase_divergence_second"] == 600
    assert audit["service_divergence_seconds"] > 0


@pytest.mark.parametrize("count", [2, 3])
def test_early_boundary_template_is_legal_and_fully_rejoins(network, count):
    node = representative(network, count)
    block = compile_block(ShadowSignal(network, node), 0, 300)
    early = next(x for x in block["templates"]
                 if x["boundary_second"] == 30 and x["shift_seconds"] == -10)
    assert early["illegal_requests"] == 0
    assert early["terminal_state"] == block["terminal_state"]
    assert early["audit"]["phase_divergence_seconds"] == (15 if count == 2 else 16)
    assert early["audit"]["last_state_divergence_second"] <= 100
    assert early["commands"][2] == 1
    assert block["templates"][0]["macro_id"] == 0
    for template in block["templates"]:
        assert template["terminal_state"] == block["terminal_state"]
        assert template["illegal_requests"] == 0


@pytest.mark.parametrize("count, accepted", [(2, True), (3, False)])
def test_delayed_boundary_rejects_illegal_repeated_request(network, count, accepted):
    block = compile_block(ShadowSignal(network, representative(network, count)), 0, 300)
    matches = [x for x in block["templates"]
               if x["boundary_second"] == 120 and x["shift_seconds"] == 10]
    assert bool(matches) is accepted
    if not accepted:
        assert any(x["boundary_second"] == 120 and x["shift_seconds"] == 10
                   and x["reason"] == "illegal_request" for x in block["rejected"])


def test_initial_and_later_blocks_bind_full_executed_reference(network):
    shadow = ShadowSignal(network, representative(network, 3))
    first = compile_block(shadow, 0, 300)
    second = compile_block(shadow, 300, 300)
    assert first["terminal_state"] == second["initial_state"]
    assert first["initial_state"] != second["initial_state"]
    assert set(first["initial_state"]) == {
        "green", "active_lightphase", "elapsed_green", "pending_transition",
        "since_switch", "phase_service_timers", "movement_service_timers"}


def test_phase_exposure_audit_distinguishes_served_phase_from_post_transition_state():
    state = {"active_lightphase": 1, "movement_service_timers": []}
    ref = [{"second": 1, "state": state, "served_lightphase": 0}]
    changed = [{"second": 1, "state": state, "served_lightphase": 1}]
    audit = audit_timelines(ref, changed)
    assert audit["phase_divergence_seconds"] == 1
    assert audit["state_divergence_seconds"] == 0
