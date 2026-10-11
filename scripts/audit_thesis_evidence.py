#!/usr/bin/env python3
"""Reconcile retained thesis evidence; never promote it to a strict release.

Uses standard-library arithmetic and original JSON/CSV files. Does not train,
change experiment artifacts, or infer unavailable field observations.
"""
import argparse
from collections import Counter
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
NETWORK = Path("results/haichau_network_v2")
SUMO = Path("results/danang_protocol_v1")
SNAPSHOT = Path("docs/research/evidence-snapshot-2026-09-23")
SOURCE_PDF = Path("datasets/danang_published/sources/phan2025_make7030065.pdf")
SOURCE_SHA = "26caabea121d7077fba881c40af4d7d01dae52ea1e85e34102f0fc1a67a9bebd"


def audit(root):
    artifacts, checks = {}, []

    def read(path):
        path = Path(path)
        data = (root / path).read_bytes()
        artifacts[str(path)] = {
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        return data

    def load(path):
        return json.loads(read(path))

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    def close(a, b):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-7)

    check("publisher_pdf_identity", hashlib.sha256(read(SOURCE_PDF)).hexdigest() == SOURCE_SHA)
    camera_path = Path("datasets/danang_published/phan2025_camera_hourly_digitized.csv")
    camera = list(csv.DictReader(read(camera_path).decode().splitlines()))
    class_factors = {"car_veh_per_h": 1, "motorcycle_veh_per_h": .3,
                     "truck_veh_per_h": 2.5, "bus_veh_per_h": 2}
    check("camera_48_unique_rows_one_date", len(camera) == 48 and
          len({(r["hour_start"], r["camera"], r["movement"]) for r in camera}) == 48 and
          {r["date_local"] for r in camera} == {"2025-04-01"})
    check("camera_derived_pcu_all_rows", all(close(
        sum(float(r[k]) * factor for k, factor in class_factors.items()),
        r["derived_pcu_per_h"]) for r in camera))
    totals = {hour: sum(sum(float(r[k]) for k in class_factors)
                       for r in camera if r["hour_start"] == hour)
              for hour in sorted({r["hour_start"] for r in camera})}
    check("camera_scenario_totals", all(totals[h] == n for h, n in
          {"08:00": 2330, "13:00": 1395, "17:00": 2400}.items()))
    turning_path = Path("datasets/danang_published/tran2025_peak_turning_movements.csv")
    turning = list(csv.DictReader(read(turning_path).decode().splitlines()))
    # Independently read from Table 1, printed page 8 of the archived PDF.
    published = {"NW-SE": 696, "NW-SW": 318, "NW-NE": 9,
                 "SE-NW": 369, "SE-NE": 711, "SE-SW": 207,
                 "NE-SW": 942, "NE-NW": 96, "NE-SE": 1359,
                 "SW-NE": 1059, "SW-SE": 300, "SW-NW": 105}
    actual = {r["approach"] + "-" + r["destination"]: float(r["pcu_per_hour"])
              for r in turning}
    check("table1_all_twelve_movements", len(turning) == 12 and actual == published)
    check("table1_total_6171_pcu", sum(actual.values()) == 6171)

    primary, sensitivity = [], []
    for directory, rows in (("evaluation", primary), ("sensitivity", sensitivity)):
        for path in sorted((root / SUMO / directory).glob("*.json")):
            data = load(path.relative_to(root))
            if isinstance(data, list):
                rows.extend(data)
    check("sumo_primary_120_full_hours", len(primary) == 120 and
          all(r.get("steps") == 3600 for r in primary))
    check("sumo_primary_75_learned_45_baseline", sum(
        r["train_seed"] is not None for r in primary) == 75 and
        sum(r["train_seed"] is None for r in primary) == 45)
    check("sumo_sensitivity_120_full_hours", len(sensitivity) == 120 and
          all(r.get("steps") == 3600 for r in sensitivity))
    stored = load(SUMO / "summary/final-summary.json")
    primary_means = {}
    for controller in sorted({r["controller_id"] for r in primary}):
        primary_means[controller] = {}
        for regime in ("normal", "am_peak", "pm_peak"):
            rows = [r for r in primary if r["controller_id"] == controller and r["scenario"] == regime]
            mean = statistics.mean(r["queue_integral_vehicle_hours"] for r in rows)
            primary_means[controller][regime] = mean
            check("sumo_mean_" + controller + "_" + regime, close(mean,
                  stored["controllers"][controller][regime]["queue_integral_vehicle_hours"]["mean"]))
    check("sumo_primary_zero_collisions", sum(r["collisions"] for r in primary) == 0)
    check("sumo_primary_zero_emergency_braking", sum(r["emergency_braking"] for r in primary) == 0)
    for regime in ("normal", "am_peak", "pm_peak"):
        baseline = {r["demand_seed"]: r["queue_integral_vehicle_hours"] for r in primary
                    if r["controller_id"] == "published_fixed" and r["scenario"] == regime}
        effects = [statistics.mean(
            r["queue_integral_vehicle_hours"] - baseline[r["demand_seed"]]
            for r in primary if r["controller_id"] == "dueling_n3" and
            r["scenario"] == regime and r["train_seed"] == seed) for seed in range(11, 16)]
        summary = stored["dqn_minus_published_fixed"][regime]
        check("sumo_paired_seed_effects_" + regime,
              summary["n_independent"] == 5 and len(summary["independent_values"]) == 5 and
              all(close(a, b) for a, b in zip(effects, summary["independent_values"])) and
              close(statistics.mean(effects), summary["mean_difference"]) and
              close(100 * statistics.mean(effects) / statistics.mean(baseline.values()),
                    summary["relative_change_percent"]))
    check("sumo_sensitivity_safety_counts", sum(r["collisions"] for r in sensitivity) == 0 and
          sum(r["emergency_braking"] for r in sensitivity) == 4)
    unit_scale = [r for r in sensitivity if float(r["scale"]) == 1]
    repeated = sum(any(r["controller_id"] == a["controller_id"] and
                       r["train_seed"] == a["train_seed"] and
                       r["demand_seed"] == a["demand_seed"] and
                       close(r["queue_integral_vehicle_seconds"], a["queue_integral_vehicle_seconds"])
                       for a in primary if a["scenario"] == "am_peak") for r in unit_scale)
    check("sensitivity_1x_repeats_30_am_outcomes", repeated == 30)
    manifest = load(NETWORK / "experiment-manifest.json")
    splits = dict(Counter(r["split"] for r in manifest["cases"]))
    check("network_split_9_6_15", splits == {"train": 9, "validation": 6, "test": 15})
    check("network_case_hashes", all(hashlib.sha256(read(r["flow_path"])).hexdigest()
                                    == r["flow_sha256"] for r in manifest["cases"]))
    read(Path("datasets/haichau_network_v2/roadnet.json"))
    phase_contract = load(Path("datasets/haichau_network_v2/phase-contract.json"))
    check("network_53_contract_agents", len(phase_contract["agents"]) == 53)
    matrix = load(NETWORK / "final15-controller-matrix-summary.json")
    check("matrix_15_unique_cases", len(matrix["rows"]) == 15 and
          len({r["case_id"] for r in matrix["rows"]}) == 15)
    matrix_totals = {}
    for controller, summary in matrix["controllers"].items():
        total = sum(r[controller]["queue_hours"] for r in matrix["rows"])
        matrix_totals[controller] = total
        check("matrix_total_" + controller, close(total, summary["queue_hours_total"]))
    fixed = {r["case_id"]: r["tuned_fixed"]["queue_hours"] for r in matrix["rows"]}
    names = {12: "seed12-direct", 13: "seed13-full-direct", 14: "seed14-direct",
             15: "seed15-direct", 16: "seed16-full-direct"}
    gate_results, null_horizons = [], {}
    for seed, suffix in names.items():
        data = load(NETWORK / ("final15-regime-gated-" + suffix + "-summary.json"))
        rows = [r for r in data["rows"] if r["controller_id"] == "schedule_residual_ddqn"]
        check("gate_15_unique_cases_seed%d" % seed,
              len(rows) == 15 and {r["case_id"] for r in rows} == set(fixed))
        fallback = [r for r in rows if "pm_peak" not in r["case_id"]]
        check("gate_10_exact_fallback_ties_seed%d" % seed,
              len(fallback) == 10 and all(close(
                  r["queue_integral_vehicle_seconds"] / 3600, fixed[r["case_id"]])
                  for r in fallback))
        # The quick campaign rewrites the unchanged full-hour flow as sorted,
        # indented JSON plus a newline. Source-file and run-file byte hashes
        # differ; compare against the actual documented run serialization.
        case_hashes = {r["case_id"]: hashlib.sha256(
            (json.dumps(load(r["flow_path"]), indent=2, sort_keys=True) + "\n").encode()
        ).hexdigest() for r in manifest["cases"]}
        check("gate_case_hashes_seed%d" % seed, all(
            r["demand_sha256"] == case_hashes[r["case_id"]] for r in rows))
        fixed_hours = sum(fixed[r["case_id"]] for r in rows)
        gated_hours = sum(r["queue_integral_vehicle_seconds"] for r in rows) / 3600
        selection = load(SNAPSHOT / ("seed%d-selection.json" % seed))
        config = load(SNAPSHOT / ("seed%d-resolved-config.json" % seed))
        null_horizons[str(seed)] = sum(r.get("horizon_steps") is None for r in rows)
        gate_results.append({"learning_seed": seed, "case_count": len(rows),
            "pooled_case_improvement_pct": 100 * (fixed_hours - gated_hours) / fixed_hours,
            "case_regressions": sum(r["queue_integral_vehicle_seconds"] / 3600 >
                                    fixed[r["case_id"]] + 1e-8 for r in rows),
            "selection_status": selection["status"],
            "selected_checkpoint": (selection.get("winner") or {}).get("checkpoint"),
            "failed_gates_by_checkpoint": {k: [n for n, passed in v["gates"].items()
                                               if passed is False]
                                            for k, v in selection["checkpoints"].items()},
            "model": config["model"]})
    values = [r["pooled_case_improvement_pct"] for r in gate_results]
    rng = random.Random(20260913)
    means = sorted(statistics.mean(rng.choice(values) for _ in values) for _ in range(10000))
    interval = [means[250], means[9749]]
    gate = load(NETWORK / "final15-regime-gated-direct-multi-seed-summary.json")
    agg = gate["aggregate_across_seed_summaries"]
    check("gate_mean_recomputed", close(statistics.mean(values), agg["mean_derived_full_day_improvement_pct"]))
    check("gate_bootstrap_recomputed", all(close(a, b) for a, b in zip(interval, agg["bootstrap_ci95_pct"])))
    check("selector_rejections_explicit", [r["learning_seed"] for r in gate_results
                                          if r["selection_status"] == "rejected"] == [13, 16])
    check("gate_10_case_regressions", sum(r["case_regressions"] for r in gate_results) == 10)
    snapshot = load(SNAPSHOT / "snapshot-manifest.json")
    check("selection_snapshot_hashes", all(hashlib.sha256(read(r["snapshot_path"])).hexdigest()
                                           == r["sha256"] for r in snapshot["files"]))
    thesis = read(Path("paper/thesis_danang.tex")).decode()
    bib = read(Path("paper/references_verified.bib")).decode()
    cited = {key.strip() for group in re.findall(r"\\cite(?:\[[^]]*\])?\{([^}]+)\}", thesis)
             for key in group.split(",")}
    bibkeys = set(re.findall(r"@\w+\{([^,]+),", bib))
    check("all_thesis_citation_keys_exist", cited <= bibkeys)
    mc = load(Path("results/danang_baseline_mc/summary.json"))
    mc_cells, mc_wins = [], {}
    for regime in ("normal", "am_peak", "pm_peak"):
        check("baseline_mc_1000_realizations_" + regime, mc[regime]["n_realizations"] == 1000)
        for row in mc[regime]["controllers"].values():
            mc_cells.append(f"{row['median']:.2f} [{row['p2_5']:.2f}, {row['p97_5']:.2f}]")
        for pair, result in mc[regime]["paired"].items():
            mc_wins.setdefault(pair, []).append(f"{result['wins']:,}/{result['n']:,}")
            check("baseline_mc_win_count_in_thesis_" + regime + "_" + pair,
                  f"{result['wins']:,}/{result['n']:,}" in thesis)
    check("baseline_mc_table_cells_in_thesis", all(cell in thesis for cell in mc_cells))
    hyst = mc_wins["hysteretic_mp_lower_than_max_pressure"]
    check("baseline_mc_peak_hysteretic_rates_in_thesis",
          all(f"{mc[r]['paired']['hysteretic_mp_lower_than_max_pressure']['rate'] * 100:.1f}\\%" in thesis
              for r in ("am_peak", "pm_peak")) and len(hyst) == 3)
    fixed_vs_raw = sum(mc[r]["paired"]["published_fixed_lower_than_max_pressure"]["wins"] for r in mc)
    fixed_vs_hyst = sum(mc[r]["paired"]["published_fixed_lower_than_hysteretic_mp"]["wins"] for r in mc)
    check("baseline_mc_abstract_totals", fixed_vs_raw == 3000 and fixed_vs_hyst == 2999 and
          "all 3,000 comparisons" in thesis and "2,999 of 3,000" in thesis)
    camera_run = Path("results/camera_counts/caurong_20260711_1716")
    camera_meta = load(camera_run / "meta.json")
    by_class = camera_meta["crossings_by_class"]
    check("camera_yolo_crossing_totals_in_thesis",
          f"{camera_meta['total_crossings']:,} line crossings: {by_class['motorcycle']:,} motorcycles, "
          f"{by_class['car']:,} cars and vans, {by_class['truck']} trucks, and {by_class['bus']} buses"
          in thesis)
    mid = {(r["junction"], r["flow"]): r
           for r in csv.DictReader(read(camera_run / "entries_exits.csv").decode().splitlines())
           if r["line"] == "boulevard_mid"}
    north, south = mid[("J1", "out")], mid[("J1", "in")]
    check("camera_yolo_main_axis_in_thesis",
          f"{int(north['motorcycle']):,} motorcycles and {north['car']} cars northbound and "
          f"{south['motorcycle']} motorcycles and {south['car']} cars southbound" in thesis)
    cars = load(camera_run / "only_car/routes_summary.json")
    j1, j2 = cars["junction_in_out"]["J1"], cars["junction_in_out"]["J2"]
    check("camera_yolo_car_balance_in_thesis",
          f"{j1['in']} cars enter J1 and {j1['out']} leave it, and {j2['in']} enter J2 and "
          f"{j2['out']} leave it" in thesis and
          f"For {cars['completed_routes']} car entries ({round(100 * cars['route_completion_rate'])}\\%)"
          in thesis)
    turns = {(r["junction"], r["from"], r["to"]): r for r in csv.DictReader(
        read(camera_run / "only_car/turning_movements.csv").decode().splitlines())}
    to_bridge = int(turns[("J2", "boulevard_mid", "bridge")]["completed_routes"])
    from_mid = sum(int(r["completed_routes"]) for (j, f, _), r in turns.items()
                   if j == "J2" and f == "boulevard_mid")
    check("camera_yolo_bridge_share_in_thesis",
          f"{round(100 * to_bridge / from_mid)}\\% ({to_bridge} of {from_mid})" in thesis)
    everyone = load(camera_run / "routes_summary.json")
    check("camera_yolo_motorcycle_cordon_in_thesis",
          f"{everyone['vehicles_entering_cordon']['motorcycle']} enter the observed cordon while "
          f"{everyone['vehicles_leaving_cordon']['motorcycle']} leave it" in thesis)
    timing = load(Path("results/camera_counts/realtime_check_m1280_s4/timing.json"))
    check("camera_yolo_realtime_in_thesis",
          f"processed {timing['video_seconds']} seconds of video in "
          f"{round(timing['wall_seconds_end_to_end'])} seconds" in thesis and
          f"about {timing['per_frame_ms_detector_only']['yolov8m_1280']}~ms per frame" in thesis)
    bibliography = load(Path("docs/research/bibliography-metadata-audit.json"))
    check("bibliographic_audit_matches_current_bib", bibliography["bibliography_sha256"] ==
          hashlib.sha256(bib.encode()).hexdigest())
    check("bibliographic_audit_covers_all_entries", bibkeys ==
          {r["key"] for r in bibliography["entries"]})
    read(Path("paper/thesis_danang.pdf"))
    read(Path("scripts/audit_thesis_evidence.py"))
    demo = Path("results/haichau_network_v2/demo-visual")
    demo_manifest = load(demo / "manifest.json")
    check("demo_manifest_file_hashes", all(hashlib.sha256(read(demo / name)).hexdigest() == sha
                                         for name, sha in demo_manifest["files"].items()))
    demo_summary = load(demo / "summary.json")
    source_summary = load(NETWORK / "final15-seed14-step4-summary.json")
    for regime, source in source_summary["by_regime"].items():
        shown = demo_summary["neighbor_phase_ddqn"][regime]["queue_difference_vs_tuned_fixed"]
        ci = source["paired_bootstrap_ci_pct"]
        check("demo_percent_summary_" + regime,
              close(shown["relative_change_percent"], -source["mean_improvement_pct"]) and
              close(shown["bootstrap_ci95"][0], -ci["upper_95_pct"]) and
              close(shown["bootstrap_ci95"][1], -ci["lower_95_pct"]) and
              shown["n_independent"] == source["n"] == 5)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    process = subprocess.run([sys.executable, str(root / "scripts/verify_haichau_thesis.py"),
                              "--root", str(root), "--no-write"], cwd=root, env=environment,
                             capture_output=True, text=True, timeout=120)
    strict = {"returncode": process.returncode}
    try:
        strict.update(json.loads(process.stdout.strip().splitlines()[-1]))
    except (ValueError, IndexError):
        strict["error"] = (process.stdout + process.stderr)[-1500:]
    # Expected strict failures are evidence limitations, not arithmetic failures.
    return {"schema_version": 1, "audit_date": datetime.date.today().isoformat(),
        "scope": "retained_source_identity_and_summary_arithmetic; not confirmatory acceptance",
        "audit_passed": all(r["passed"] for r in checks), "checks": checks,
        "camera": {"rows": len(camera), "hourly_four_movement_totals_veh_per_h": totals,
                   "source": str(SOURCE_PDF), "source_figures": "17-18, printed page 20"},
        "turning_table": {"rows": len(turning), "total_pcu_per_hour": sum(actual.values()),
                          "source": "Table 1, printed page 8; underlying 2022 dataset not obtained"},
        "sumo": {"primary_records": len(primary), "sensitivity_records": len(sensitivity),
                 "primary_mean_queue_vehicle_hours": primary_means,
                 "sensitivity_unit_scale_repeated_am_outcomes": repeated,
                 "independence_limit": "one observed date; headway correction informed by held-out failure"},
        "network": {"case_splits": splits, "controlled_signals": len(phase_contract["agents"]),
                    "run_flow_identity": "full-hour source JSON reserialized with indent=2, sort_keys=True and final newline; see run_haichau_quick_campaign.py",
                    "matrix_queue_hours": matrix_totals, "gate_seeds": gate_results,
                    "gate_mean_pct": statistics.mean(values), "gate_bootstrap_ci95_pct": interval,
                    "compact_rows_without_horizon_steps": null_horizons},
        "strict_release": strict,
        "limitations": ["Gate is post hoc on inspected cases; new independent evaluation is absent.",
                        "Seeds 13 and 16 were rejected by the original residual validation selector.",
                        "Some compact gate rows omit per-row horizon_steps; a header is not raw horizon proof.",
                        "Raw CityFlow replays/checkpoints are not all distributed in Git.",
                        "Digitization coordinate log and detector-error ground truth are unavailable.",
                        "Reading uncertainty is not propagated through the experiments.",
                        "No full-movement, independent-day or district field validation is established."],
        "artifacts": artifacts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("docs/research/thesis-evidence-audit.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    report = audit(root)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"audit_passed": report["audit_passed"], "checks": len(report["checks"]),
                      "failed_checks": [r["name"] for r in report["checks"] if not r["passed"]],
                      "strict_release_complete": report["strict_release"].get("complete"),
                      "output": str(output)}, ensure_ascii=False))
    return 0 if report["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
