#!/usr/bin/env python3
"""Build a portable offline demo from the completed bounded Hai Chau runs.

The demo is deliberately labelled as bounded evidence.  It does not create a
false frozen-release manifest and does not require CityFlow during a defense.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"
IMAGE = "traffic-rl-cityflow-research@sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_run(campaign, controller, case_id):
    summary = json.loads((ROOT / campaign / "campaign-summary.json").read_text())
    for record in summary["runs"]:
        if record["returncode"] != 0:
            continue
        metrics = record["result"]["metrics"]
        if metrics["controller_id"] == controller and metrics["case_id"] == case_id:
            return record["result"]["replay"], metrics
    raise ValueError("missing completed run: %s %s" % (controller, case_id))


def build(output):
    output = (ROOT / output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing demo: %s" % output)
    output.mkdir(parents=True)
    for name in ("haichau_network_demo.html", "haichau_network_demo.css",
                 "haichau_network_demo.js", "haichau_network_demo_core.js"):
        shutil.copy2(ROOT / "frontend" / name, output / name)
    shutil.copy2(ROOT / "scripts" / "haichau_demo_launcher.py", output / "launch_demo.py")
    command = output / "launch_demo.command"
    command.write_text("#!/bin/sh\ncd \"$(dirname \"$0\")\"\nexec python3 launch_demo.py --bundle . \"$@\"\n")
    command.chmod(0o755)
    # The existing frontend calls the learned replay "neighbor_phase_ddqn".
    # The bounded demo maps the display label to the schedule-residual replay.
    html = (output / "haichau_network_demo.html").read_text()
    html = html.replace("Neighbor phase DDQN", "Schedule-residual DDQN")
    (output / "index.html").write_text(html)
    (output / "haichau_network_demo.html").unlink()
    network = json.loads((ROOT / "results/haichau_network_v2/release-inputs/viewer-network.json").read_text())
    (output / "network.json").write_text(json.dumps(network, indent=2, sort_keys=True) + "\n")
    (output / "replays").mkdir()
    regimes = ("normal", "am_peak", "pm_peak")
    case_ids = {regime: "test_%s_demand105" % regime for regime in regimes}
    entries = []
    for regime in regimes:
        case_id = case_ids[regime]
        fixed, fixed_metrics = load_run(
            "results/haichau_network_v2/final15-seed12-step8-run2",
            "tuned_fixed", case_id)
        learned, learned_metrics = load_run(
            "results/haichau_network_v2/final15-seed14-step4-residual",
            "schedule_residual_ddqn", case_id)
        fixed_path = output / "replays" / (regime + "__fixed.json")
        learned_path = output / "replays" / (regime + "__ddqn.json")
        fixed_path.write_text(json.dumps(fixed, separators=(",", ":")) + "\n")
        learned_path.write_text(json.dumps(learned, separators=(",", ":")) + "\n")
        for controller, path, metrics in (
                ("tuned_fixed", fixed_path, fixed_metrics),
                ("neighbor_phase_ddqn", learned_path, learned_metrics)):
            entries.append({
                "case_id": case_id, "regime": regime,
                "controller_id": controller,
                "path": str(path.relative_to(output)),
                "sha256": sha256(path),
                "learning_seed": metrics.get("learning_seed"),
            })
    summary = json.loads((ROOT / "results/haichau_network_v2/final15-seed14-step4-summary.json").read_text())
    aggregate = {}
    for regime, row in summary["by_regime"].items():
        ci = row["paired_bootstrap_ci_pct"]
        aggregate[regime] = {
            "queue_difference_vs_tuned_fixed": {
                "relative_change_percent": -row["mean_improvement_pct"],
                "bootstrap_ci95": [-ci["upper_95_pct"], -ci["lower_95_pct"]],
                "n_independent": row["n"],
            }
        }
    aggregate_path = output / "summary.json"
    aggregate_path.write_text(json.dumps({"neighbor_phase_ddqn": aggregate}, indent=2, sort_keys=True) + "\n")
    files = {}
    for path in output.rglob("*"):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output))] = sha256(path)
    manifest = {
        "bundle_version": 2, "controlled_signals": 53,
        "demand_label": DEMAND_LABEL,
        "network_path": "network.json", "aggregate_path": "summary.json",
        "runtime_image": IMAGE, "evidence_scope": "bounded_15_case_matrix_seed14_step4",
        "acceptance": {"accepted": False, "reason": "bounded demo; pending five-seed release verifier"},
        "replays": entries, "files": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"output": str(output.relative_to(ROOT)), "replays": len(entries), "regimes": list(regimes)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/haichau_network_v2/demo-bounded")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
