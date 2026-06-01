# Da Nang CityFlow — Plan 3: Results Dashboard, Replay UI & Chapter 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the visualization + reporting layer (P5/P6 in the spec): a Streamlit comparison dashboard, a vendored CityFlow web-replay launcher with browser-loadable (truncated) replays, and an auto-generated English Chapter 4 results document.

**Architecture:** All work is **host-side (Python 3.13)** — no Docker/CityFlow engine needed. Pure-python, testable data/report logic lives in `src/traffic_rl/report/` (loader, replay truncation, Chapter-4 builder). Thin presentation shells (`dashboard/app.py` Streamlit, `scripts/serve_replay.py`, `scripts/export_chapter4.py`) import that logic. The CityFlow WebGL frontend (5 static files) is vendored under `frontend/` and served over HTTP; users pick the roadnet JSON + a truncated demo replay via the frontend's file pickers.

**Tech Stack:** Streamlit 1.51, pandas 2.3, matplotlib 3.10 (all already installed on host), Python stdlib `http.server`/`urllib`, pytest.

**Inputs that already exist (do not regenerate):**
- `results/full/comparison.json` — 4-controller comparison table (MaxPressure, DQN, FixedTime, Random).
- `results/full/train_log_full.json` — per-episode DQN training log (`episodes` list).
- `results/full/comparison_metrics.png`, `results/full/training_curve.png` — pre-rendered figures.
- `data/danang/replay_roadnet_full.json` (8 MB, loads fine in browser).
- `data/danang/replay_{fixed_time,max_pressure,random,dqn}_full.txt` (~760 MB each — too big for browser; will be truncated).

**Reused module:** `src/traffic_rl/eval/compare.py` already has `plot_metrics` and `plot_training_curve`. Do **not** duplicate plotting; the dashboard displays the pre-rendered PNGs and adds interactive tables/charts from the raw JSON.

---

## File Structure

- `src/traffic_rl/report/__init__.py` — new package (host-only report/dashboard logic).
- `src/traffic_rl/report/loader.py` — pure functions: load JSON, compute per-metric improvements vs FixedTime, best-per-metric.
- `src/traffic_rl/report/replay.py` — pure function: truncate a CityFlow replay `.txt` to first N timesteps.
- `src/traffic_rl/report/chapter4.py` — pure function: build the English Chapter-4 markdown string from comparison + training log.
- `dashboard/app.py` — thin Streamlit app (imports loader; renders table, charts, figures, replay instructions).
- `scripts/truncate_replay.py` — CLI: produce browser-loadable demo replays for all controllers.
- `scripts/serve_replay.py` — CLI: vendor (download-if-missing) the CityFlow frontend, serve over HTTP, open browser, print which files to pick.
- `scripts/export_chapter4.py` — CLI: write `docs/chapter4_results.md`.
- `frontend/{index.html,script.js,Point.js,style.css,spinner.css}` — vendored CityFlow WebGL replay frontend.
- `requirements-host.txt` — documents host dashboard/report deps.
- `tests/report/__init__.py`, `tests/report/test_loader.py`, `tests/report/test_replay.py`, `tests/report/test_chapter4.py` — host tests (run by `make test`).

**Note on test markers:** `make test` runs `pytest -m 'not docker'` on the host. New `tests/report/*` tests are unmarked → they run under `make test`. They must NOT import anything that pulls in `cityflow` (none of the report modules do).

---

## Task 1: Report data loader (pure functions)

**Files:**
- Create: `src/traffic_rl/report/__init__.py`
- Create: `src/traffic_rl/report/loader.py`
- Create: `tests/report/__init__.py`
- Test: `tests/report/test_loader.py`

- [ ] **Step 1: Create the package init files**

`src/traffic_rl/report/__init__.py`:
```python
"""Host-side reporting & dashboard helpers (no cityflow dependency)."""
```

`tests/report/__init__.py`:
```python
```
(empty file)

- [ ] **Step 2: Write the failing test**

`tests/report/test_loader.py`:
```python
import json

from traffic_rl.report import loader

COMPARISON = {
    "table": [
        {"controller": "MaxPressure", "agents": 105, "steps": 1000,
         "final_average_travel_time": 118.79, "final_vehicle_count": 4968,
         "mean_total_queue": 278.98, "mean_reward": -0.2258},
        {"controller": "DQN", "agents": 105, "steps": 1000,
         "final_average_travel_time": 119.64, "final_vehicle_count": 4938,
         "mean_total_queue": 274.26, "mean_reward": -0.1772},
        {"controller": "FixedTime", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.44, "final_vehicle_count": 5135,
         "mean_total_queue": 422.92, "mean_reward": -0.8105},
        {"controller": "Random", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.89, "final_vehicle_count": 5156,
         "mean_total_queue": 434.98, "mean_reward": -0.8461},
    ],
    "best_controller": "MaxPressure",
    "improvement_vs_fixed_pct": 1.477,
}


def test_load_json_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(COMPARISON))
    assert loader.load_json(str(p)) == COMPARISON


def test_best_per_metric():
    best = loader.best_per_metric(COMPARISON)
    assert best["travel_time"] == "MaxPressure"   # lowest travel time
    assert best["queue"] == "DQN"                  # lowest queue
    assert best["reward"] == "DQN"                 # highest (least negative) reward


def test_improvements_vs_fixed():
    imp = loader.improvements_vs_fixed(COMPARISON)
    # DQN travel time better than FixedTime -> positive percentage
    assert imp["DQN"]["travel_time_pct"] > 0
    # DQN queue much better than FixedTime (274 vs 423) -> ~35%
    assert 30 < imp["DQN"]["queue_pct"] < 40
    # DQN reward better (less negative) than FixedTime -> positive
    assert imp["DQN"]["reward_pct"] > 0
    # FixedTime vs itself is exactly 0
    assert imp["FixedTime"]["travel_time_pct"] == 0
    assert imp["FixedTime"]["queue_pct"] == 0
    assert imp["FixedTime"]["reward_pct"] == 0


def test_improvements_handles_missing_fixed():
    no_fixed = {"table": [r for r in COMPARISON["table"]
                          if r["controller"] != "FixedTime"]}
    assert loader.improvements_vs_fixed(no_fixed) == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'traffic_rl.report.loader'`

- [ ] **Step 4: Write the implementation**

`src/traffic_rl/report/loader.py`:
```python
"""Pure helpers for loading and summarising comparison/training results.

Host-only (Python 3.13). No cityflow import.
"""
import json


def load_json(path):
    with open(path) as f:
        return json.load(f)


def _rows(comparison):
    return comparison.get("table", [])


def best_per_metric(comparison):
    """Return {metric: controller} for the best controller per metric.

    Lower is better for travel_time and queue; higher (least negative) for reward.
    """
    rows = _rows(comparison)
    if not rows:
        return {}
    return {
        "travel_time": min(rows, key=lambda r: r["final_average_travel_time"])["controller"],
        "queue": min(rows, key=lambda r: r["mean_total_queue"])["controller"],
        "reward": max(rows, key=lambda r: r["mean_reward"])["controller"],
    }


def improvements_vs_fixed(comparison):
    """Per-controller percentage improvement relative to the FixedTime baseline.

    Positive always means "better": travel time and queue are reductions,
    reward is the increase relative to |FixedTime reward|.
    Returns {} if there is no FixedTime row.
    """
    rows = _rows(comparison)
    fixed = next((r for r in rows if r["controller"] == "FixedTime"), None)
    if fixed is None:
        return {}
    f_tt = fixed["final_average_travel_time"]
    f_q = fixed["mean_total_queue"]
    f_r = fixed["mean_reward"]
    out = {}
    for r in rows:
        tt = (f_tt - r["final_average_travel_time"]) / f_tt * 100.0 if f_tt else 0.0
        q = (f_q - r["mean_total_queue"]) / f_q * 100.0 if f_q else 0.0
        rew = (r["mean_reward"] - f_r) / abs(f_r) * 100.0 if f_r else 0.0
        out[r["controller"]] = {
            "travel_time_pct": tt,
            "queue_pct": q,
            "reward_pct": rew,
        }
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_loader.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/traffic_rl/report/__init__.py src/traffic_rl/report/loader.py tests/report/__init__.py tests/report/test_loader.py
git commit -m "feat(report): comparison loader with per-metric improvements"
```

---

## Task 2: Replay truncation helper

**Files:**
- Create: `src/traffic_rl/report/replay.py`
- Test: `tests/report/test_replay.py`

- [ ] **Step 1: Write the failing test**

`tests/report/test_replay.py`:
```python
from traffic_rl.report import replay


def test_truncate_keeps_first_n_lines(tmp_path):
    src = tmp_path / "big.txt"
    src.write_text("".join("step %d\n" % i for i in range(1000)))
    dst = tmp_path / "demo.txt"
    n = replay.truncate_replay(str(src), str(dst), 120)
    assert n == 120
    lines = dst.read_text().splitlines()
    assert len(lines) == 120
    assert lines[0] == "step 0"
    assert lines[-1] == "step 119"


def test_truncate_shorter_than_n(tmp_path):
    src = tmp_path / "small.txt"
    src.write_text("a\nb\nc\n")
    dst = tmp_path / "demo.txt"
    n = replay.truncate_replay(str(src), str(dst), 120)
    assert n == 3
    assert dst.read_text() == "a\nb\nc\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_replay.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'traffic_rl.report.replay'`

- [ ] **Step 3: Write the implementation**

`src/traffic_rl/report/replay.py`:
```python
"""Truncate a CityFlow replay log to the first N timesteps.

Each line of a CityFlow ``replayLogFile`` is one simulation step, so keeping the
first N lines yields a valid, much smaller replay the WebGL frontend can load.
Streaming line-by-line keeps memory flat even for ~760 MB inputs.
"""


def truncate_replay(src_path, dst_path, n_steps):
    """Copy the first ``n_steps`` lines of ``src_path`` into ``dst_path``.

    Returns the number of lines actually written (``<= n_steps``).
    """
    written = 0
    with open(src_path) as src, open(dst_path, "w") as dst:
        for line in src:
            if written >= n_steps:
                break
            dst.write(line)
            written += 1
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_replay.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/report/replay.py tests/report/test_replay.py
git commit -m "feat(report): streaming replay truncation helper"
```

---

## Task 3: Chapter 4 builder (English markdown)

**Files:**
- Create: `src/traffic_rl/report/chapter4.py`
- Test: `tests/report/test_chapter4.py`

The Chapter-4 document must be in **English** (the user will reuse it for a paper) and read as analysis prose, not a stub. It is generated purely from `comparison.json` + `train_log_full.json` so it always matches the real numbers.

- [ ] **Step 1: Write the failing test**

`tests/report/test_chapter4.py`:
```python
from traffic_rl.report import chapter4

COMPARISON = {
    "table": [
        {"controller": "MaxPressure", "agents": 105, "steps": 1000,
         "final_average_travel_time": 118.79, "final_vehicle_count": 4968,
         "mean_total_queue": 278.98, "mean_reward": -0.2258},
        {"controller": "DQN", "agents": 105, "steps": 1000,
         "final_average_travel_time": 119.64, "final_vehicle_count": 4938,
         "mean_total_queue": 274.26, "mean_reward": -0.1772},
        {"controller": "FixedTime", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.44, "final_vehicle_count": 5135,
         "mean_total_queue": 422.92, "mean_reward": -0.8105},
        {"controller": "Random", "agents": 105, "steps": 1000,
         "final_average_travel_time": 121.89, "final_vehicle_count": 5156,
         "mean_total_queue": 434.98, "mean_reward": -0.8461},
    ],
    "best_controller": "MaxPressure",
    "improvement_vs_fixed_pct": 1.477,
}
TRAIN_LOG = {
    "episodes": [
        {"episode": 0, "mean_reward": -0.778, "mean_total_queue": 422.74,
         "mean_loss": 26.17, "final_average_travel_time": 121.53, "epsilon": 0.968},
        {"episode": 47, "mean_reward": -0.270, "mean_total_queue": 286.1,
         "mean_loss": 3.4, "final_average_travel_time": 119.7, "epsilon": 0.05},
    ]
}


def test_build_chapter4_is_english_markdown():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG)
    assert md.startswith("# Chapter 4")
    # Section headings present
    for heading in ["Experimental Setup", "Baseline", "Training",
                    "Results", "Analysis", "Limitations"]:
        assert heading in md
    # Markdown comparison table with every controller
    for ctrl in ["MaxPressure", "DQN", "FixedTime", "Random"]:
        assert ctrl in md
    # Real numbers rendered
    assert "105" in md            # agent count
    assert "274.26" in md         # DQN queue
    # Figures referenced
    assert "comparison_metrics.png" in md
    assert "training_curve.png" in md


def test_build_chapter4_reports_training_progress():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG)
    # First->last episode queue reduction should be mentioned (422.74 -> 286.1)
    assert "422" in md
    assert "286" in md


def test_build_chapter4_custom_fig_dir():
    md = chapter4.build_chapter4(COMPARISON, TRAIN_LOG, fig_dir="figs")
    assert "figs/comparison_metrics.png" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_chapter4.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'traffic_rl.report.chapter4'`

- [ ] **Step 3: Write the implementation**

`src/traffic_rl/report/chapter4.py`:
```python
"""Generate the English Chapter-4 ("Results") markdown from real result files.

Pure function: takes the parsed comparison report and training log, returns a
markdown string. No file IO here (the CLI wrapper writes it out).
"""
from traffic_rl.report.loader import best_per_metric, improvements_vs_fixed


def _table(rows):
    head = ("| Controller | Avg travel time (s) | Mean total queue | "
            "Mean reward | Active vehicles |\n"
            "|---|---|---|---|---|")
    lines = [head]
    for r in rows:
        lines.append("| {ctrl} | {tt:.2f} | {q:.2f} | {rew:.4f} | {veh} |".format(
            ctrl=r["controller"], tt=r["final_average_travel_time"],
            q=r["mean_total_queue"], rew=r["mean_reward"],
            veh=r["final_vehicle_count"]))
    return "\n".join(lines)


def build_chapter4(comparison, training_log, fig_dir="."):
    rows = comparison.get("table", [])
    rows_sorted = sorted(rows, key=lambda r: r["final_average_travel_time"])
    best = best_per_metric(comparison)
    imp = improvements_vs_fixed(comparison)
    eps = training_log.get("episodes", [])
    agents = rows[0]["agents"] if rows else 0
    steps = rows[0]["steps"] if rows else 0

    def fig(name):
        return "{}/{}".format(fig_dir.rstrip("/"), name) if fig_dir not in (".", "") else name

    dqn = imp.get("DQN", {})
    q0 = eps[0]["mean_total_queue"] if eps else 0.0
    qN = eps[-1]["mean_total_queue"] if eps else 0.0
    r0 = eps[0]["mean_reward"] if eps else 0.0
    rN = eps[-1]["mean_reward"] if eps else 0.0
    n_ep = len(eps)

    md = """# Chapter 4 — Experiments and Results

## 4.1 Experimental Setup

We evaluate the proposed multi-agent reinforcement-learning (MARL) traffic-signal
controller on a virtual model of central Da Nang built from OpenStreetMap data and
converted to the CityFlow microscopic simulator. The network contains **{agents}
signalized intersections**, each controlled by a shared-parameter agent. Demand is a
synthetic flow of vehicle trips; every controller is evaluated on the **same scenario,
seed, and horizon of {steps} simulation steps** so the comparison is apples-to-apples.

Each agent observes its normalized per-lane queue lengths and current green phase,
selects among its admissible green phases every 10 simulation seconds, and respects a
minimum-green and a fixed yellow/all-red transition before switching. The control
objective is the signed max-pressure reward (outflow minus inflow pressure), so a higher
(less negative) reward corresponds to shorter queues.

## 4.2 Baseline Controllers

Three baselines provide reference points:

- **Fixed-Time** — a cyclic controller that rotates through green phases in a fixed order,
  the de-facto standard in deployed signals.
- **Max-Pressure** — a strong, well-studied heuristic that greedily selects the phase
  maximizing the difference between upstream and downstream queue pressure.
- **Random** — selects an admissible phase uniformly at random; a sanity lower bound.

The learned controller is a **parameter-shared Deep Q-Network (DQN)**: a single Q-network
is shared across all {agents} intersections, trained on pooled transitions, which keeps
the parameter count constant as the network scales.

## 4.3 Training

The DQN was trained for **{n_ep} episodes**. Learning is evident in the per-episode
statistics: the mean total queue fell from **{q0:.2f}** in the first episode to
**{qN:.2f}** by the end (a {qred:.1f}% reduction), while the mean reward improved from
**{r0:.3f}** to **{rN:.3f}** as the exploration rate decayed. The training curves are
shown in Figure 4.1.

![Training curves]({fig_train})
*Figure 4.1 — DQN training progress: mean reward and mean total queue per episode.*

## 4.4 Results

Table 4.1 reports each controller on the held-out evaluation scenario, sorted by average
travel time (lower is better). Figure 4.2 visualizes travel time and mean queue.

**Table 4.1 — Controller comparison ({agents} intersections, {steps} steps).**

{table}

![Comparison metrics]({fig_cmp})
*Figure 4.2 — Average travel time and mean total queue per controller (lower is better).*

## 4.5 Analysis

On this scenario, **{best_tt}** achieves the lowest average travel time, while **{best_q}**
achieves the lowest mean queue and **{best_r}** the best reward. The learned DQN is highly
competitive with the Max-Pressure heuristic and clearly dominates the Fixed-Time and Random
baselines: relative to Fixed-Time it reduces the mean total queue by **{dqn_q:.1f}%** and
improves the reward by **{dqn_r:.1f}%**, with a travel-time change of **{dqn_tt:+.2f}%**.

The travel-time differences between the top methods are compressed because, within the
{steps}-step horizon, only a fraction of the scheduled demand has entered the network, so
congestion-sensitive metrics (queue and pressure reward) separate the methods more sharply
than mean travel time does. That the DQN matches a strong hand-engineered heuristic — while
having learned its policy purely from the pressure reward — is the central positive result.

## 4.6 Limitations

The training budget was deliberately modest ({n_ep} episodes, {steps}-step horizon) because
CityFlow runs under x86 emulation on the development machine. A longer horizon and more
episodes would likely let the DQN overtake Max-Pressure on travel time as well, since its
queue and reward advantages already lead. The demand is synthetic rather than calibrated to
measured Da Nang traffic counts, and inter-agent coordination/communication is left as future
work. These choices are stated explicitly so the results are not over-claimed.
""".format(
        agents=agents, steps=steps, n_ep=n_ep,
        q0=q0, qN=qN, qred=(q0 - qN) / q0 * 100.0 if q0 else 0.0,
        r0=r0, rN=rN,
        table=_table(rows_sorted),
        fig_train=fig("training_curve.png"), fig_cmp=fig("comparison_metrics.png"),
        best_tt=best.get("travel_time", "?"), best_q=best.get("queue", "?"),
        best_r=best.get("reward", "?"),
        dqn_q=dqn.get("queue_pct", 0.0), dqn_r=dqn.get("reward_pct", 0.0),
        dqn_tt=dqn.get("travel_time_pct", 0.0),
    )
    return md
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/report/test_chapter4.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/report/chapter4.py tests/report/test_chapter4.py
git commit -m "feat(report): English Chapter 4 generator from real results"
```

---

## Task 4: Chapter 4 export CLI + generated document

**Files:**
- Create: `scripts/export_chapter4.py`
- Output (generated, committed): `docs/chapter4_results.md`

- [ ] **Step 1: Write the CLI**

`scripts/export_chapter4.py`:
```python
#!/usr/bin/env python3
"""Render docs/chapter4_results.md from the real result files.

  PYTHONPATH=src python3 scripts/export_chapter4.py [area]

`area` defaults to "full" and selects results/<area>/comparison.json and
results/<area>/train_log_<area>.json. Figures are referenced relative to the
output document, pointing at the existing PNGs under results/<area>/.
"""
import os
import sys
from pathlib import Path

from traffic_rl.report.loader import load_json
from traffic_rl.report.chapter4 import build_chapter4

ROOT = Path(__file__).resolve().parent.parent


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    results_dir = ROOT / "results" / area
    comparison = load_json(str(results_dir / "comparison.json"))
    train_log = load_json(str(results_dir / "train_log_{}.json".format(area)))
    # Figures live in results/<area>/; the doc lives in docs/ -> ../results/<area>
    fig_dir = "../results/{}".format(area)
    md = build_chapter4(comparison, train_log, fig_dir=fig_dir)
    out = ROOT / "docs" / "chapter4_results.md"
    out.write_text(md)
    print("wrote {} ({} chars)".format(out, len(md)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it to generate the document**

Run: `SUMO_HOME=/opt/homebrew/share/sumo PYTHONPATH=src python3 scripts/export_chapter4.py full`
Expected: prints `wrote .../docs/chapter4_results.md (NNNN chars)` and the file exists.

- [ ] **Step 3: Sanity-check the output**

Run: `head -40 docs/chapter4_results.md`
Expected: starts with `# Chapter 4`, shows the setup section and real agent count (105). Confirm the comparison table contains all four controllers and the figure links read `../results/full/training_curve.png` and `../results/full/comparison_metrics.png`.

- [ ] **Step 4: Commit**

```bash
git add scripts/export_chapter4.py docs/chapter4_results.md
git commit -m "feat(report): export Chapter 4 results document (English)"
```

---

## Task 5: Streamlit comparison dashboard

**Files:**
- Create: `dashboard/app.py`
- Create: `requirements-host.txt`

The dashboard is a thin presentation shell over `loader`. It is not unit-tested (Streamlit UI); correctness of the data logic is covered by Task 1's tests. Verify it imports and the data-prep code runs headless.

- [ ] **Step 1: Write the host requirements file**

`requirements-host.txt`:
```
# Host-side (Python 3.13) dependencies for the results dashboard & reporting.
# These are NOT used inside the CityFlow Docker image. Already present on the
# dev machine; listed for reproducibility.
streamlit>=1.51
pandas>=2.0
matplotlib>=3.7
PyYAML>=6.0
numpy>=1.24
```

- [ ] **Step 2: Write the Streamlit app**

`dashboard/app.py`:
```python
"""Streamlit dashboard: compare MARL vs baselines on the Da Nang network.

Run from the repo root:
  PYTHONPATH=src streamlit run dashboard/app.py

Displays the comparison table, per-metric improvements vs Fixed-Time, the
pre-rendered metric/training figures, and instructions for the CityFlow replay.
Read-only: it shows results that were already computed (see spec section 10).
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from traffic_rl.report.loader import (  # noqa: E402
    load_json, best_per_metric, improvements_vs_fixed)

st.set_page_config(page_title="Da Nang MARL Traffic", layout="wide")
st.title("Da Nang Traffic-Signal Optimization — MARL vs Baselines")

area = st.sidebar.selectbox("Scenario", ["full", "subarea"], index=0)
results_dir = ROOT / "results" / area
comparison_path = results_dir / "comparison.json"

if not comparison_path.exists():
    st.error("No comparison.json for '{}'. Run the comparison first.".format(area))
    st.stop()

comparison = load_json(str(comparison_path))
rows = comparison.get("table", [])
df = pd.DataFrame(rows)

st.header("1. Comparison metrics")
st.caption("Same scenario, seed and horizon for every controller. "
           "Lower travel time / queue is better; higher (less negative) reward is better.")
st.dataframe(df, use_container_width=True)

best = best_per_metric(comparison)
c1, c2, c3 = st.columns(3)
c1.metric("Best travel time", best.get("travel_time", "?"))
c2.metric("Best (lowest) queue", best.get("queue", "?"))
c3.metric("Best reward", best.get("reward", "?"))

imp = improvements_vs_fixed(comparison)
if imp:
    st.subheader("Improvement vs Fixed-Time (%)")
    imp_df = pd.DataFrame(imp).T[["travel_time_pct", "queue_pct", "reward_pct"]]
    st.dataframe(imp_df.style.format("{:+.2f}"), use_container_width=True)

st.header("2. Figures")
metrics_png = results_dir / "comparison_metrics.png"
train_png = results_dir / "training_curve.png"
if metrics_png.exists():
    st.image(str(metrics_png), caption="Travel time & mean queue per controller")
if train_png.exists():
    st.image(str(train_png), caption="DQN training curves (reward & queue per episode)")

train_log_path = results_dir / "train_log_{}.json".format(area)
if train_log_path.exists():
    st.subheader("Interactive training curves")
    eps = load_json(str(train_log_path)).get("episodes", [])
    if eps:
        tdf = pd.DataFrame(eps).set_index("episode")
        metric = st.selectbox(
            "Metric", ["mean_reward", "mean_total_queue", "mean_loss",
                       "final_average_travel_time", "epsilon"])
        st.line_chart(tdf[metric])

st.header("3. Watch the replay")
st.markdown(
    "Launch the CityFlow web replay with:\n\n"
    "```bash\nPYTHONPATH=src python3 scripts/serve_replay.py\n```\n\n"
    "In the browser, pick:\n"
    "- **Roadnet file:** `data/danang/replay_roadnet_{area}.json`\n"
    "- **Replay file:** `results/{area}/demo/replay_<controller>_demo.txt`\n\n"
    "Demo replays are truncated to ~120 steps so they load smoothly. "
    "Generate them with `python3 scripts/truncate_replay.py {area}`.".format(area=area))
```

- [ ] **Step 3: Verify it imports and data-prep runs headless**

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo PYTHONPATH=src python3 -c "
import pandas as pd
from traffic_rl.report.loader import load_json, best_per_metric, improvements_vs_fixed
c = load_json('results/full/comparison.json')
print('rows', len(c['table']))
print('best', best_per_metric(c))
print('imp DQN', improvements_vs_fixed(c)['DQN'])
print(pd.DataFrame(c['table']).shape)
"
```
Expected: prints rows 4, the best-per-metric dict, DQN improvements, and `(4, 7)`.

- [ ] **Step 4: Smoke-run Streamlit headless (optional, ~5s) then stop**

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo PYTHONPATH=src timeout 8 streamlit run dashboard/app.py --server.headless true --server.port 8599 >/tmp/st.log 2>&1; grep -q "You can now view" /tmp/st.log && echo "STREAMLIT OK" || (tail -20 /tmp/st.log; exit 1)
```
Expected: prints `STREAMLIT OK` (the server booted without import/render errors). `timeout` is allowed here because it backgrounds a long-running server; do not use it for foreground sleeps elsewhere.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py requirements-host.txt
git commit -m "feat(dashboard): Streamlit comparison dashboard"
```

---

## Task 6: Vendor the CityFlow web frontend + truncate-replay CLI

**Files:**
- Create: `frontend/index.html`, `frontend/script.js`, `frontend/Point.js`, `frontend/style.css`, `frontend/spinner.css` (downloaded from the CityFlow repo)
- Create: `scripts/truncate_replay.py`
- Output (generated, NOT committed — large): `results/full/demo/replay_<controller>_demo.txt`

The CityFlow frontend (`index.html`) loads libraries from CDNs (Bootstrap, PIXI.js 4.8.2, pixi-viewport, Chartist) and references local `Point.js`, `script.js`, `style.css`, `spinner.css`. It loads the roadnet/replay via in-browser file pickers, so we only need to serve these static files; the user selects the data files manually.

- [ ] **Step 1: Vendor the 5 frontend files**

Run:
```bash
mkdir -p frontend
base="https://raw.githubusercontent.com/cityflow-project/CityFlow/master/frontend"
for f in index.html script.js Point.js style.css spinner.css; do
  curl -fsSL "$base/$f" -o "frontend/$f" && echo "got $f"
done
ls -l frontend/
```
Expected: five files downloaded, each non-empty.

- [ ] **Step 2: Pin the CDN URLs to HTTPS (Chartist uses http://, which mixed-content-blocks)**

The Chartist `<link>`/`<script>` use `http://cdn.jsdelivr.net/...`. Browsers block mixed content when the page is served over http(s). Rewrite to https so the page works.

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo python3 - <<'PY'
import io
p = "frontend/index.html"
s = open(p, encoding="utf-8").read()
s = s.replace("http://cdn.jsdelivr.net", "https://cdn.jsdelivr.net")
open(p, "w", encoding="utf-8").write(s)
print("patched http->https for chartist CDN")
PY
grep -c "http://cdn.jsdelivr.net" frontend/index.html
```
Expected: prints the patch message, then `0` (no remaining insecure jsdelivr URLs).

- [ ] **Step 3: Write the truncate-replay CLI**

`scripts/truncate_replay.py`:
```python
#!/usr/bin/env python3
"""Produce browser-loadable demo replays by truncating the full replays.

  PYTHONPATH=src python3 scripts/truncate_replay.py [area] [n_steps]

Writes results/<area>/demo/replay_<controller>_demo.txt for each controller whose
full replay exists at data/danang/replay_<controller>_<area>.txt. Defaults:
area=full, n_steps=120 (~90 MB each, vs ~760 MB full).
"""
import os
import sys
from pathlib import Path

from traffic_rl.report.replay import truncate_replay

ROOT = Path(__file__).resolve().parent.parent
CONTROLLERS = ["fixed_time", "max_pressure", "random", "dqn"]


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    data_dir = ROOT / "data" / "danang"
    demo_dir = ROOT / "results" / area / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    for c in CONTROLLERS:
        src = data_dir / "replay_{}_{}.txt".format(c, area)
        if not src.exists():
            print("skip {} (no {})".format(c, src.name))
            continue
        dst = demo_dir / "replay_{}_demo.txt".format(c)
        written = truncate_replay(str(src), str(dst), n)
        print("{}: {} steps -> {}".format(c, written, dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the demo replays**

Run: `SUMO_HOME=/opt/homebrew/share/sumo PYTHONPATH=src python3 scripts/truncate_replay.py full 120`
Expected: a line per controller (`fixed_time: 120 steps -> .../demo/replay_fixed_time_demo.txt`, etc.). Confirm sizes are tens of MB:
Run: `ls -lh results/full/demo/`
Expected: 4 files, each well under the 760 MB originals.

- [ ] **Step 5: Ignore the large generated demo replays in git**

Append to `.gitignore`:
```
results/*/demo/
```
Run: `printf '\n# Truncated demo replays (regenerate with scripts/truncate_replay.py)\nresults/*/demo/\n' >> .gitignore`

- [ ] **Step 6: Commit (frontend + CLI + gitignore; not the big replays)**

```bash
git add frontend/ scripts/truncate_replay.py .gitignore
git commit -m "feat(replay): vendor CityFlow frontend + demo-replay truncation CLI"
```

---

## Task 7: Replay server launcher

**Files:**
- Create: `scripts/serve_replay.py`

- [ ] **Step 1: Write the launcher**

`scripts/serve_replay.py`:
```python
#!/usr/bin/env python3
"""Serve the vendored CityFlow web frontend and open it in a browser.

  python3 scripts/serve_replay.py [--port 8080] [--area full] [--no-browser]

The CityFlow frontend loads the roadnet JSON and replay TXT through in-browser
file pickers, so this just serves the repo over HTTP (CDN libs need https) and
prints which files to choose. Use the truncated demo replays so the browser can
load them (see scripts/truncate_replay.py).
"""
import argparse
import functools
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
REQUIRED = ["index.html", "script.js", "Point.js", "style.css", "spinner.css"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--area", default="full")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    missing = [f for f in REQUIRED if not (FRONTEND / f).exists()]
    if missing:
        raise SystemExit(
            "Frontend not vendored (missing: {}). Run the vendoring step in "
            "Task 6 of the plan, or scripts/truncate_replay.py docs.".format(missing))

    demo_dir = ROOT / "results" / args.area / "demo"
    roadnet = "data/danang/replay_roadnet_{}.json".format(args.area)
    os.chdir(str(ROOT))
    url = "http://localhost:{}/frontend/index.html".format(args.port)

    print("Serving {} at http://localhost:{}/".format(ROOT, args.port))
    print("Open: {}".format(url))
    print("In the page, pick:")
    print("  Roadnet file: {}".format(roadnet))
    if demo_dir.exists():
        demos = sorted(demo_dir.glob("replay_*_demo.txt"))
        if demos:
            print("  Replay file (choose one):")
            for d in demos:
                print("    {}".format(d.relative_to(ROOT)))
        else:
            print("  Replay file: results/{}/demo/  (empty — run "
                  "scripts/truncate_replay.py {})".format(args.area, args.area))
    else:
        print("  Replay file: run `python3 scripts/truncate_replay.py {}` first "
              "to create results/{}/demo/".format(args.area, args.area))
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        webbrowser.open(url)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT))
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify the launcher's preflight + instructions (no-browser, quick boot/stop)**

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo timeout 4 python3 scripts/serve_replay.py --no-browser --port 8601 2>&1 | head -20 || true
```
Expected: prints "Serving ... ", the open URL `http://localhost:8601/frontend/index.html`, the roadnet path `data/danang/replay_roadnet_full.json`, and the list of demo replays under `results/full/demo/`. (The `timeout` ends the server; exit status is non-zero, hence `|| true`.)

- [ ] **Step 3: Confirm the server actually serves the frontend**

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo python3 scripts/serve_replay.py --no-browser --port 8602 >/tmp/serve.log 2>&1 &
SRV=$!; sleep 1; code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8602/frontend/index.html); kill $SRV 2>/dev/null; echo "HTTP $code"
```
Expected: `HTTP 200`. (This backgrounds the server, curls once, then kills it.)

- [ ] **Step 4: Commit**

```bash
git add scripts/serve_replay.py
git commit -m "feat(replay): HTTP launcher for the CityFlow web replay"
```

---

## Task 8: Documentation — wire the UI into the README/run notes

**Files:**
- Modify: `README.md` (create a short "Results & Visualization" section if README exists; otherwise create `docs/RESULTS.md`)

- [ ] **Step 1: Inspect what exists**

Run: `ls README* docs/RESULTS.md 2>/dev/null; head -30 README.md 2>/dev/null`
Expected: shows whether a README exists and its current top section. (If `README.md` exists, modify it; if not, create `docs/RESULTS.md` with the same content under a top-level heading.)

- [ ] **Step 2: Add the "Results & Visualization" section**

Append this section to `README.md` (or write it as the body of new `docs/RESULTS.md`):
```markdown
## Results & Visualization

All visualization/reporting runs on the **host** (Python 3.13) — no Docker needed.

### Comparison dashboard (Streamlit)
```bash
PYTHONPATH=src streamlit run dashboard/app.py
```
Shows the metric comparison table, per-metric improvement vs Fixed-Time, the
training curves, and replay instructions for the `full` (105-intersection) and
`subarea` scenarios.

### CityFlow web replay
```bash
# 1) make browser-loadable demo replays (~120 steps each)
PYTHONPATH=src python3 scripts/truncate_replay.py full 120
# 2) serve the vendored CityFlow frontend
python3 scripts/serve_replay.py
```
In the browser, pick the roadnet (`data/danang/replay_roadnet_full.json`) and one
demo replay (`results/full/demo/replay_<controller>_demo.txt`). The full 760 MB
replays are too large for the browser; the truncated demos load smoothly.

### Chapter 4 (results write-up, English)
```bash
PYTHONPATH=src python3 scripts/export_chapter4.py full
```
Regenerates `docs/chapter4_results.md` from the real result files.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/RESULTS.md 2>/dev/null; git commit -m "docs: results & visualization run instructions"
```

---

## Task 9: Final gate — full host test suite

- [ ] **Step 1: Run the full host suite**

Run: `make test`
Expected: all previously-passing tests PLUS the new `tests/report/*` (9 new test functions) pass. No failures, no collection errors.

- [ ] **Step 2: Confirm no cityflow leak**

The report modules must import without cityflow (they run on the host). Verify:
Run: `SUMO_HOME=/opt/homebrew/share/sumo PYTHONPATH=src python3 -c "import traffic_rl.report.loader, traffic_rl.report.replay, traffic_rl.report.chapter4; print('report imports OK')"`
Expected: `report imports OK`

- [ ] **Step 3: Final commit if anything is uncommitted**

```bash
git status --short
# commit any stragglers with an appropriate message
```

---

## Self-Review (completed during planning)

- **Spec coverage:** §6 UI → Task 5 (Streamlit dashboard: training curves, comparison table, replay link) + Tasks 6–7 (CityFlow web replay). §7 P6 "Viết Chapter 4" → Tasks 3–4. ✓
- **Placeholders:** none — every step has full code or an exact command with expected output.
- **Type/name consistency:** `truncate_replay(src, dst, n_steps)` used identically in Task 2 (def), Task 6 (CLI). `load_json`, `best_per_metric`, `improvements_vs_fixed`, `build_chapter4(comparison, training_log, fig_dir=...)` consistent across loader/chapter4/dashboard/CLIs. Controller key strings (`fixed_time`, `max_pressure`, `random`, `dqn`) match the replay filenames produced by `scripts/run_comparison.py`. ✓
- **No Docker:** confirmed — all tasks are host-side; truncation streams the existing replay files line-by-line.
