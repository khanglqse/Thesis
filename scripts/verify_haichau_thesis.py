#!/usr/bin/env python3
"""Fail-closed release audit for the Hai Chau network thesis extension."""

import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path

from traffic_rl.eval.network_campaign import verify_campaign


DEMAND_LABEL = "synthetic network demand constrained by Da Nang evidence"
REQUIRED_CONTROLLERS = {
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
}
REQUIRED_REGIMES = {"normal", "am_peak", "pm_peak"}
REQUIRED_FALLBACKS = {
    "demo-walkthrough.mp4", "result-summary.pdf", "network-overview.png",
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summary_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _gate(passed, detail, evidence=None):
    return {
        "passed": bool(passed),
        "detail": detail,
        "evidence": evidence if evidence is not None else {},
    }


def _json(path):
    return json.loads(path.read_text())


def _inside(root, relative):
    if not relative:
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _protocol(root):
    path = root / "results/haichau_network_v2/final/frozen-protocol.json"
    return (_json(path), path) if path.is_file() else (None, path)


def _network_gate(root, protocol):
    if not protocol:
        return _gate(False, "frozen-protocol.json is missing")
    path = _inside(root, protocol.get("network_manifest_path"))
    expected = protocol.get("network_manifest_sha256")
    if not path or not path.is_file() or not expected:
        return _gate(False, "frozen network manifest path/hash is missing")
    if _sha256(path) != expected:
        return _gate(False, "frozen network manifest hash mismatch")
    manifest = _json(path)
    count = manifest.get("controlled_signals")
    if count is None:
        count = manifest.get("counts", {}).get("controlled_signals")
    agents = manifest.get("agent_ids", [])
    passed = count == 53 and (not agents or len(agents) == 53)
    return _gate(passed, "network manifest must declare exactly 53 signals", {
        "path": str(path.relative_to(root)), "controlled_signals": count,
    })


def _case_gate(root, protocol):
    if not protocol:
        return _gate(False, "frozen-protocol.json is missing")
    path = _inside(root, protocol.get("case_manifest_path"))
    expected = protocol.get("case_manifest_sha256")
    if not path or not path.is_file() or not expected:
        return _gate(False, "frozen case manifest path/hash is missing")
    if _sha256(path) != expected:
        return _gate(False, "frozen case manifest hash mismatch")
    manifest = _json(path)
    cases = manifest.get("cases", [])
    hashes = {}
    valid = len(cases) == 30
    for case in cases:
        split = case.get("split")
        demand_hash = case.get("demand_sha256")
        if split not in {"train", "validation", "test"} or not demand_hash:
            valid = False
            continue
        prior = hashes.setdefault(demand_hash, split)
        valid = valid and prior == split
    splits = dict((name, sum(case.get("split") == name for case in cases))
                  for name in ("train", "validation", "test"))
    valid = valid and all(splits.values())
    return _gate(valid, "case manifest must have 30 split-safe cases", {
        "path": str(path.relative_to(root)), "case_count": len(cases),
        "split_counts": splits,
    })


def _runtime_gate(protocol):
    digest = str((protocol or {}).get("runtime_digest", ""))
    passed = bool(re.fullmatch(r"sha256:[0-9a-f]{64}", digest))
    return _gate(passed, "CityFlow runtime must use a full sha256 digest", {
        "runtime_digest": digest,
    })


def _checkpoint_gate(root, protocol):
    entries = (protocol or {}).get("checkpoints", [])
    seeds, valid = set(), len(entries) == 5
    evidence = []
    for entry in entries:
        seed = entry.get("learning_seed")
        path = _inside(root, entry.get("path"))
        expected = entry.get("sha256")
        okay = (seed in {11, 12, 13, 14, 15} and path is not None
                and path.is_file() and expected and _sha256(path) == expected
                and entry.get("validation_eligible") is True
                and isinstance(entry.get("checkpoint_contract"), dict))
        valid = valid and bool(okay)
        if seed is not None:
            seeds.add(seed)
        evidence.append({"learning_seed": seed, "valid": bool(okay)})
    valid = valid and seeds == {11, 12, 13, 14, 15}
    return _gate(valid, "five validation-eligible checkpoint contracts are required", {
        "seeds": sorted(seeds), "checkpoints": evidence,
    })


def _campaign_gates(root):
    campaign_dir = root / "results/haichau_network_v2/final"
    try:
        verified = verify_campaign(campaign_dir)
        campaign = _json(campaign_dir / "campaign-manifest.json")
    except Exception as exc:
        detail = "campaign verification failed: %s" % exc
        return (
            _gate(False, detail), _gate(False, detail), _gate(False, detail),
        )
    runs = campaign.get("runs", [])
    controllers = set(run.get("controller_id") for run in runs)
    regimes = set(run.get("regime") for run in runs)
    grouped = {}
    fresh = True
    horizons = True
    for run in runs:
        key = (run.get("case_id"), run.get("regime"))
        grouped.setdefault(key, []).append(run)
        metrics = _json(campaign_dir / "runs" / run["run_id"] / "metrics.json")
        fresh = fresh and metrics.get("fresh_evaluation") is True \
            and not metrics.get("source_run_dir")
        horizons = horizons and metrics.get("completed_steps") == run.get("horizon_steps")
    matched = controllers == REQUIRED_CONTROLLERS and bool(grouped)
    for values in grouped.values():
        counts = dict((controller, 0) for controller in REQUIRED_CONTROLLERS)
        for run in values:
            counts[run["controller_id"]] += 1
        matched = matched and all(
            counts[controller] == (5 if controller in {
                "shared_ddqn_legacy", "neighbor_phase_ddqn"} else 1)
            for controller in REQUIRED_CONTROLLERS)
    return (
        _gate(matched and fresh, "every case needs fresh matched controller coverage", {
            "verified_runs": verified.get("complete", 0),
            "controllers": sorted(value for value in controllers if value),
        }),
        _gate(regimes.issuperset(REQUIRED_REGIMES),
              "normal, AM peak and PM peak test regimes are required", {
                  "regimes": sorted(value for value in regimes if value),
              }),
        _gate(horizons and bool(runs), "all run horizons must be complete", {
            "run_count": len(runs),
        }),
    )


def _summary_gates(root):
    path = root / "results/haichau_network_v2/final/summary.json"
    if not path.is_file():
        missing = _gate(False, "frozen summary.json is missing")
        return missing, missing
    summary = _json(path)
    document = summary.get("summary", {})
    candidate = document.get("neighbor_phase_ddqn", {})
    units = [value.get("statistical_unit") for value in candidate.values()
             if isinstance(value, dict)]
    stats_ok = bool(units) and all(
        value == "learning_seed_after_matched_case_mean" for value in units)
    stats_gate = _gate(stats_ok, "RL inference must use learning-seed units", {
        "statistical_units": units,
    })
    acceptance = summary.get("acceptance", {})
    fields = {
        "accepted", "normal_point_noninferiority", "normal_ci_noninferiority",
        "peak_improvement", "completion_preserved", "five_learning_seeds",
    }
    accepted_ok = fields.issubset(acceptance) and all(
        isinstance(acceptance[field], bool) for field in fields)
    acceptance_gate = _gate(
        accepted_ok, "all predeclared acceptance outcomes must be reported",
        dict((field, acceptance.get(field)) for field in sorted(fields)),
    )
    return stats_gate, acceptance_gate


def _thesis_gate(root):
    summary_path = root / "results/haichau_network_v2/final/summary.json"
    artifact_path = root / "paper/generated/haichau_network/artifact-manifest.json"
    pdf_path = root / "paper/thesis_danang.pdf"
    if not all(path.is_file() for path in (summary_path, artifact_path, pdf_path)):
        return _gate(False, "summary-derived thesis manifest/PDF is missing")
    summary = _json(summary_path)
    artifacts = _json(artifact_path)
    passed = artifacts.get("summary_sha256") == _summary_hash(summary)
    output_dir = artifact_path.parent
    for name in artifacts.get("artifacts", []):
        passed = passed and (output_dir / name).is_file()
    return _gate(passed, "thesis artifacts must derive from the frozen summary", {
        "summary_sha256": _summary_hash(summary),
        "pdf": str(pdf_path.relative_to(root)),
    })


def audit_demo(root):
    root = Path(root)
    demo = root / "results/haichau_network_v2/demo"
    manifest_path = demo / "manifest.json"
    if not manifest_path.is_file():
        return _gate(False, "offline demo manifest is missing")
    try:
        manifest = _json(manifest_path)
        if manifest.get("controlled_signals") != 53 \
                or manifest.get("demand_label") != DEMAND_LABEL:
            return _gate(False, "offline demo scope/label is invalid")
        files = manifest.get("files", {})
        actual_files = {
            str(path.relative_to(demo)) for path in demo.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if set(files) != actual_files:
            return _gate(False, "offline demo file set differs from its hash manifest", {
                "unlisted": sorted(actual_files - set(files)),
                "missing": sorted(set(files) - actual_files),
            })
        for relative, expected in files.items():
            path = _inside(demo, relative)
            if not path or not path.is_file() or _sha256(path) != expected:
                return _gate(False, "offline demo file hash mismatch: %s" % relative)
        network = _json(demo / manifest["network_path"])
        if network.get("controlled_signals") != 53 \
                or len(network.get("nodes", [])) != 53:
            return _gate(False, "offline demo network does not contain 53 signals")
        fallbacks = manifest.get("fallbacks", {})
        if set(fallbacks) != REQUIRED_FALLBACKS:
            return _gate(False, "offline demo fallbacks are incomplete")
        for relative in fallbacks.values():
            path = _inside(demo, relative)
            if not path or not path.is_file() or relative not in files:
                return _gate(False, "offline demo fallback is not hash-verified")
        frontend = [path for path in demo.iterdir()
                    if path.suffix.lower() in {".html", ".css", ".js"}]
        for path in frontend:
            if re.search(r"https?://|(?<!:)//[A-Za-z0-9]", path.read_text()):
                return _gate(False, "offline demo has a remote dependency: %s" % path.name)
        replays = manifest.get("replays", [])
        regimes = set(entry.get("regime") for entry in replays)
        if not regimes.issuperset(REQUIRED_REGIMES):
            return _gate(False, "offline demo lacks normal/AM/PM replay pairs")
        for regime in REQUIRED_REGIMES:
            entries = [entry for entry in replays if entry.get("regime") == regime]
            if set(entry.get("controller_id") for entry in entries) != {
                    "tuned_fixed", "neighbor_phase_ddqn"} \
                    or len(set(entry.get("case_id") for entry in entries)) != 1:
                return _gate(False, "offline demo replay pair is not matched: %s" % regime)
        frozen_summary = root / "results/haichau_network_v2/final/summary.json"
        if not frozen_summary.is_file() or _json(
                demo / manifest["aggregate_path"]) != _json(frozen_summary):
            return _gate(False, "offline aggregate does not match frozen summary")
        return _gate(True, "offline demo, replay pairs and fallbacks are hash-valid", {
            "replay_count": len(replays), "fallbacks": sorted(fallbacks),
        })
    except Exception as exc:
        return _gate(False, "offline demo verification failed: %s" % exc)


def _clean_checkout_gate(root, protocol):
    path = root / "results/haichau_network_v2/verification/clean-checkout.json"
    if not path.is_file():
        return _gate(False, "clean-checkout verification record is missing")
    record = _json(path)
    expected_commit = (protocol or {}).get("code_commit")
    passed = record.get("passed") is True and bool(record.get("commands")) \
        and bool(record.get("tool_versions")) and bool(record.get("wall_time_seconds"))
    if expected_commit:
        passed = passed and record.get("commit") == expected_commit
    return _gate(passed, "release path must pass from a clean checkout", record)


def verify_project(root):
    root = Path(root).resolve()
    protocol, protocol_path = _protocol(root)
    matched, scenarios, horizons = _campaign_gates(root)
    statistics_gate, acceptance_gate = _summary_gates(root)
    gates = {
        "network_53_signals": _network_gate(root, protocol),
        "thirty_case_split": _case_gate(root, protocol),
        "runtime_pinned": _runtime_gate(protocol),
        "five_learning_seeds": _checkpoint_gate(root, protocol),
        "fresh_matched_runs": matched,
        "scenario_coverage": scenarios,
        "horizon_complete": horizons,
        "hierarchical_statistics": statistics_gate,
        "acceptance_reported": acceptance_gate,
        "thesis_artifacts": _thesis_gate(root),
        "offline_demo": audit_demo(root),
        "clean_checkout": _clean_checkout_gate(root, protocol),
    }
    failed = [name for name, value in gates.items() if not value["passed"]]
    return {
        "verification_version": 2,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_path": str(protocol_path.relative_to(root)),
        "complete": not failed,
        "failed_gates": failed,
        "gates": gates,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument(
        "--output",
        default="results/haichau_network_v2/verification/final-report.json")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    report = verify_project(root)
    output = _inside(root, args.output)
    if output is None:
        raise ValueError("output must remain inside the project root")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "complete": report["complete"],
        "failed_gates": report["failed_gates"],
        "report": str(output.relative_to(root)),
    }, sort_keys=True))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
