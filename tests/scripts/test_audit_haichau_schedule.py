from scripts.audit_haichau_schedule import build_audit
from tests.sim.test_schedule_residual import network


def test_persisted_audit_exposes_single_masked_deviation_and_long_phase_drift(network):
    artifact = build_audit(network)
    assert len(artifact["nodes"]) == 2
    for node in artifact["nodes"]:
        assert node["masked_reference_disagreements"] == 1
        assert node["independent_audit"]["phase_divergence_seconds"] > 300
        assert len(node["baseline_trace"]) == 600
        assert len(node["single_deviation_trace"]) == 600
        assert node["accepted_macros"]
        assert all(x["illegal_requests"] == 0 for x in node["accepted_macros"])
