#!/usr/bin/env python3
"""Audit the current evidence-aware Hai Chau thesis bundle.

This audit deliberately reports both the presentation-ready exploratory gate
and the independent fail-closed strict verifier. It never turns exploratory
evidence into a strict acceptance claim.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "results/haichau_network_v2/final15-regime-gated-direct-multi-seed-summary.json"
OUTPUT = ROOT / "results/haichau_network_v2/verification/gated-thesis-audit.json"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_json(command):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=environment)
    for line in reversed(result.stdout.splitlines()):
        try:
            return json.loads(line), result.returncode
        except json.JSONDecodeError:
            continue
    return {"error": result.stdout[-2000:]}, result.returncode


def main():
    summary = json.loads(SUMMARY.read_text())
    foundation, foundation_rc = run_json(
        ["python3", "scripts/verify_haichau_foundation.py"])
    strict, strict_rc = run_json(
        ["python3", "scripts/verify_haichau_thesis.py", "--no-write"])
    seed_results = summary["seed_results"]
    artifact_paths = {
        "thesis_pdf": ROOT / "paper/thesis_danang.pdf",
        "defense_deck": ROOT / "presentation/thesis_defense_danang.pptx",
        "demo_manifest": ROOT / "results/haichau_network_v2/demo-bounded/manifest.json",
        "gate_summary": SUMMARY,
    }
    artifacts = {
        name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
        for name, path in artifact_paths.items() if path.is_file()
    }
    full_case_seeds = [row["learning_seed"] for row in seed_results
                       if row["coverage"] == "full_15_cases"]
    all_positive = all(row["derived_full_day_improvement_pct"] > 0
                       for row in seed_results)
    audit = {
        "schema_version": 1,
        "profile": "exploratory_regime_gated_thesis_audit",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "presentation_ready": bool(artifacts) and len(artifacts) == 4,
        "foundation": {"passed": foundation.get("status") == "verified",
                       "returncode": foundation_rc, "result": foundation},
        "exploratory_gate": {
            "passed": all_positive,
            "learning_seeds": summary["learning_seeds"],
            "full_15_case_seeds": full_case_seeds,
            "pm_only_seeds": [row["learning_seed"] for row in seed_results
                              if row["coverage"] == "pm_5_cases"],
            "mean_derived_full_day_improvement_pct": summary[
                "aggregate_across_seed_summaries"]["mean_derived_full_day_improvement_pct"],
            "bootstrap_ci95_pct": summary["aggregate_across_seed_summaries"][
                "bootstrap_ci95_pct"],
            "case_level_regressions": {
                str(row["learning_seed"]): row["case_level_regressions"]
                for row in seed_results},
        },
        "strict_confirmatory": {
            "passed": strict.get("complete") is True and strict_rc == 0,
            "returncode": strict_rc,
            "failed_gates": strict.get("failed_gates", []),
        },
        "artifacts": artifacts,
        "interpretation": (
            "The gate is presentation-ready exploratory evidence: fixed-time is "
            "retained in normal/AM and the residual policy is enabled in PM. "
            "Seeds 13 and 16 have PM-only fresh coverage. The strict verifier "
            "remains the authority for a confirmatory release and is intentionally "
            "reported separately."),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)),
                      "presentation_ready": audit["presentation_ready"],
                      "exploratory_gate": audit["exploratory_gate"]["passed"],
                      "strict_confirmatory": audit["strict_confirmatory"]["passed"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
