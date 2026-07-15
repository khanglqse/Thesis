#!/usr/bin/env python3
"""Emit Chapter-4 LaTeX table rows (tab:waiting, tab:queue) from the multi-seed
aggregates in results/multiseed/<scen>.json, with mean +/- 95% CI on the DQN row.

Baselines (FixedTime/MaxPressure/Random) are deterministic replays -> zero CI, so we
print their means only. DQN varies by training seed -> we print mean and CI95.

  PYTHONPATH=src python3 scripts/emit_ch4_tables.py            # all four scenarios
  PYTHONPATH=src python3 scripts/emit_ch4_tables.py haichau_rush haichau_calib

Prints the rows in the SAME order/format as the existing hand-written tables so the
finalization edit is a copy-paste. Percentages are reductions vs tuned Fixed-Time
(+ = DQN better). Scenarios missing an aggregate are reported as "(pending re-run)".
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENS = ["haichau", "haichau_calib", "haichau_peak", "haichau_rush"]
TEX = {"haichau": r"\texttt{haichau}", "haichau_calib": r"\texttt{haichau\_calib}",
       "haichau_peak": r"\texttt{haichau\_peak}", "haichau_rush": r"\texttt{haichau\_rush}"}


def load(scen):
    p = ROOT / "results" / "multiseed" / (scen + ".json")
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    # Stale-guard: the aggregate is only trustworthy if its n_seeds matches the
    # number of exp_ms*/comparison.json actually on disk. An orphaned old aggregate
    # (source exp_ms deleted by a re-run) has n_seeds > on-disk count -> STALE.
    on_disk = len(list((ROOT / "results" / scen).glob("exp_ms*/comparison.json")))
    d["_on_disk_seeds"] = on_disk
    d["_stale"] = (on_disk != d.get("n_seeds"))
    return d


def pct(fixed, val):
    """Reduction of `val` vs `fixed` in percent (+ = val lower = better)."""
    return 100.0 * (fixed - val) / fixed if fixed else 0.0


def fmt_pct(x):
    return ("$+%.1f$\\%%" % x) if x >= 0 else ("$-%.1f$\\%%" % abs(x))


def waiting_row(scen, agg, n_seeds):
    """cumulative waiting time (wait_hours) + reduction vs Fixed-Time."""
    def w(c):
        return agg[c]["wait_hours"]["mean"]
    fx = w("FixedTime")
    dqn_ci = agg["DQN"]["wait_hours"]["ci95"]
    cells = [
        "%.1f (0\\%%)" % fx,
        "%.1f (%s)" % (w("Random"), fmt_pct(pct(fx, w("Random")))),
        "\\textbf{%.1f (%s)}" % (w("MaxPressure"), fmt_pct(pct(fx, w("MaxPressure")))),
        "%.1f$\\pm$%.1f (%s)" % (w("DQN"), dqn_ci, fmt_pct(pct(fx, w("DQN")))),
    ]
    return "%-24s & %s \\\\  %% n=%d" % (TEX[scen], " & ".join(cells), n_seeds)


def queue_row(scen, agg, n_seeds):
    def q(c):
        return agg[c]["mean_total_queue"]["mean"]
    dqn_ci = agg["DQN"]["mean_total_queue"]["ci95"]
    cells = [
        "%.1f" % q("FixedTime"),
        "%.1f" % q("Random"),
        "\\textbf{%.1f}" % q("MaxPressure"),
        "%.1f$\\pm$%.1f" % (q("DQN"), dqn_ci),
    ]
    return "%-24s & %s \\\\  %% n=%d" % (TEX[scen], " & ".join(cells), n_seeds)


def main():
    scens = sys.argv[1:] or SCENS
    loaded = {s: load(s) for s in scens}

    def tag(d):
        if d["_stale"]:
            return "  <-- STALE: aggregate n=%d but %d exp_ms on disk; re-aggregate before use" % (
                d.get("n_seeds"), d["_on_disk_seeds"])
        return ""

    stale_any = any(d and d["_stale"] for d in loaded.values())
    print("%% ==== tab:waiting rows (cumulative waiting time, veh-hours; + = vs Fixed-Time) ====")
    for s in scens:
        d = loaded[s]
        if d is None:
            print("%% %s: (pending re-run)" % s)
        else:
            print(waiting_row(s, d["aggregate"], d["n_seeds"]) + tag(d))
    print()
    print("%% ==== tab:queue rows (mean total queue) ====")
    for s in scens:
        d = loaded[s]
        if d is None:
            print("%% %s: (pending re-run)" % s)
        else:
            print(queue_row(s, d["aggregate"], d["n_seeds"]) + tag(d))
    if stale_any:
        print("\n%% WARNING: one or more rows are STALE (old pre-fix aggregate). "
              "Re-aggregate with scripts/aggregate_multiseed.py after the re-run before "
              "pasting into Chapter 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
