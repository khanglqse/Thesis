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

area = st.sidebar.selectbox(
    "Scenario", ["haichau", "haichau_peak", "full", "subarea"], index=0,
    help="haichau = normal/uniform demand; haichau_peak = rush-hour surge")
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
for qot_name in ("queue_over_time_peak.png", "queue_over_time.png"):
    qot_png = results_dir / qot_name
    if qot_png.exists():
        st.image(str(qot_png), caption="Total queue over time — Fixed-Time accumulates the "
                 "most congestion; adaptive control (DQN, Max-Pressure) stays lower")
        break
cwt_png = results_dir / "cumulative_wait.png"
if cwt_png.exists():
    st.image(str(cwt_png), caption="Cumulative waiting time (vehicle-hours) — the gap to "
             "Fixed-Time is the waiting time the controller saves")

train_log_path = results_dir / "train_log_{}.json".format(area)
if train_log_path.exists():
    st.subheader("Interactive training curves")
    eps = load_json(str(train_log_path)).get("episodes", [])
    if eps:
        tdf = pd.DataFrame(eps).set_index("episode")
        available = [m for m in ["mean_reward", "mean_total_queue", "mean_loss",
                                 "final_average_travel_time", "epsilon"]
                     if m in tdf.columns]
        metric = st.selectbox("Metric", available)
        if metric:
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
