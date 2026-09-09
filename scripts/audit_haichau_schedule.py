#!/usr/bin/env python3
"""Persist traffic-free executed-reference traces and residual compiler evidence."""
import argparse
import json
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.schedule_residual import ShadowSignal, audit_timelines, compile_block
from traffic_rl.train.network_trainer import _file_sha256, _tracked_tree_attestation


ROOT = Path(__file__).resolve().parent.parent


def build_audit(roadnet):
    nodes = []
    for count in (2, 3):
        node = next(node for node in roadnet.signalized_ids()
                    if len(roadnet.green_phases(node)) == count)
        shadow = ShadowSignal(roadnet, node)
        baseline = shadow.reference(0, 600)
        changed = shadow.nominal_with_override(600, {20: 1})
        block = compile_block(shadow, 0)
        nodes.append({"node": node, "selectable_greens": count,
            "intervention": {"second": 20, "requested_phase": 1},
            "masked_reference_disagreements": changed["masked_reference_disagreements"],
            "independent_audit": audit_timelines(baseline["trace"], changed["trace"]),
            "baseline_trace": baseline["trace"], "single_deviation_trace": changed["trace"],
            "initial_state": block["initial_state"], "terminal_state": block["terminal_state"],
            "accepted_macros": block["templates"], "rejected_macros": block["rejected"]})
    return {"schema_version": 1, "diagnostic_only": True,
            "traffic_engine": "empty_signal_engine", "horizon_seconds": 600,
            "network_or_demand_metrics": False, "nodes": nodes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    destination = ROOT / args.output
    if destination.exists():
        raise ValueError("audit output already exists")
    manifest = json.loads((ROOT / args.manifest).read_text())
    roadnet = RoadNet.load(str(ROOT / manifest["network"]["path"]),
        str(ROOT / manifest["phase_contract"]["path"]), require_phase_contract=True,
        expected_phase_contract_sha256=manifest["phase_contract"]["sha256"])
    evidence = build_audit(roadnet)
    evidence["source_tree"] = _tracked_tree_attestation(str(ROOT))
    evidence["network_sha256"] = manifest["network"]["sha256"]
    evidence["phase_contract_sha256"] = manifest["phase_contract"]["sha256"]
    evidence["source_files"] = {relative: _file_sha256(str(ROOT / relative))
        for relative in ("scripts/audit_haichau_schedule.py",
                         "src/traffic_rl/sim/schedule_residual.py",
                         "src/traffic_rl/sim/multi_agent_env.py")}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"artifact": str(destination), "nodes": [
        {"node": node["node"], "audit": node["independent_audit"],
         "accepted_macros": len(node["accepted_macros"])} for node in evidence["nodes"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
