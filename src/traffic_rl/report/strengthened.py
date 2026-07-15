"""Plots for the strengthened empirical study (multi-seed CI, agreement, robustness).

Host-only (matplotlib has no Python-3.6 wheel in the CityFlow container). Reads the
aggregate JSONs written by scripts/aggregate_multiseed.py.
"""
import json
from pathlib import Path


def _load(scen_json):
    d = json.loads(Path(scen_json).read_text())
    return d["scenario"], d["n_seeds"], d["aggregate"]


def _impr_pct(agg, ctrl, metric="wait_hours"):
    """Improvement % of ctrl vs FixedTime on metric, plus the DQN CI in % points."""
    fixed = agg["FixedTime"][metric]["mean"]
    if not fixed:
        return 0.0, 0.0
    m = agg[ctrl][metric]["mean"]
    ci = agg[ctrl][metric]["ci95"]
    return 100.0 * (fixed - m) / fixed, 100.0 * ci / fixed


def plot_ci_bars(scen_jsons, out_png):
    """Grouped bars: DQN (mean±95%CI) vs Max-Pressure improvement over Fixed-Time,
    per scenario. Fixed-Time/Random are deterministic (no CI)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scenarios, dqn_m, dqn_ci, mp_m = [], [], [], []
    for sj in scen_jsons:
        scen, n, agg = _load(sj)
        if "DQN" not in agg or "MaxPressure" not in agg:
            continue
        scenarios.append(scen.replace("haichau_", "").replace("haichau", "normal"))
        m, ci = _impr_pct(agg, "DQN")
        dqn_m.append(m); dqn_ci.append(ci)
        mp_m.append(_impr_pct(agg, "MaxPressure")[0])

    import numpy as np
    x = np.arange(len(scenarios))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w / 2, mp_m, w, label="Max-Pressure (heuristic)", color="#718096")
    ax.bar(x + w / 2, dqn_m, w, yerr=dqn_ci, capsize=6,
           label="DQN (learned, mean ± 95% CI)", color="#38a169")
    ax.set_xticks(x); ax.set_xticklabels(scenarios)
    ax.set_ylabel("Waiting-time reduction vs Fixed-Time (%)")
    ax.set_title("Learned DQN vs Max-Pressure — multi-seed (higher = better)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    for xi, m, ci in zip(x + w / 2, dqn_m, dqn_ci):
        ax.annotate("{:.1f}%".format(m), (xi, m), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, fontweight="bold")
    fig.tight_layout(); fig.savefig(out_png, dpi=130); plt.close(fig)
    return {"scenarios": scenarios, "dqn": dqn_m, "dqn_ci": dqn_ci, "mp": mp_m}
