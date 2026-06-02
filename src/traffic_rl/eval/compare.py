"""Aggregate per-controller metrics into a comparison table + plots. 3.6-safe core."""
import json


def aggregate(rows):
    table = sorted(rows, key=lambda r: r["final_average_travel_time"])
    best = table[0]["controller"]
    by = {r["controller"]: r["final_average_travel_time"] for r in rows}
    improvement = None
    if "FixedTime" in by and "DQN" in by and by["FixedTime"]:
        improvement = (by["FixedTime"] - by["DQN"]) / by["FixedTime"] * 100.0
    return {"table": table, "best_controller": best,
            "improvement_vs_fixed_pct": improvement}


def write_report(rows, out_json):
    report = aggregate(rows)
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2)
    return report


def plot_metrics(rows, out_png):
    """Bar chart of avg travel time + mean queue per controller."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = [r["controller"] for r in rows]
    tt = [r["final_average_travel_time"] for r in rows]
    q = [r.get("mean_total_queue", 0) for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].bar(names, tt); ax[0].set_title("Avg travel time (s) - lower is better")
    ax[1].bar(names, q); ax[1].set_title("Mean total queue - lower is better")
    for a in ax:
        a.tick_params(axis="x", rotation=20)
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)


def cumulative_wait_hours(queue_series, action_interval=10):
    """Cumulative waiting time (vehicle-hours) from a per-decision queue trace.

    Each decision covers action_interval seconds during which ~queue vehicles are
    waiting, so waiting vehicle-seconds accumulate as queue * action_interval.
    Returns the running total in vehicle-hours (one value per decision).
    """
    cum, acc = [], 0.0
    for q in queue_series:
        acc += q * action_interval / 3600.0
        cum.append(acc)
    return cum


def plot_cumulative_wait_time(rows, out_png, action_interval=10, peak_window=None):
    """Plot cumulative waiting time (vehicle-hours) per controller over time.

    This is the time-based view of the improvement: the gap between Fixed-Time
    and a controller's curve is the waiting time that controller saves. Unlike
    mean travel time (diluted by free-flowing vehicles), it separates clearly.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 5))
    finals = {}
    for r in rows:
        cum = cumulative_wait_hours(r.get("queue_series") or [], action_interval)
        if cum:
            ax.plot(range(len(cum)), cum, label=r["controller"])
            finals[r["controller"]] = cum[-1]
    if peak_window:
        ax.axvspan(peak_window[0], peak_window[1], color="red", alpha=0.10,
                   label="peak window")
    if "FixedTime" in finals and "DQN" in finals and finals["FixedTime"]:
        saved = finals["FixedTime"] - finals["DQN"]
        ax.annotate("DQN saves {:.0f} veh-h (-{:.1f}%) vs Fixed-Time".format(
            saved, 100 * saved / finals["FixedTime"]),
            xy=(0.40, 0.12), xycoords="axes fraction", fontsize=11,
            bbox=dict(boxstyle="round", fc="wheat", alpha=0.7))
    ax.set_xlabel("decision (every action_interval)")
    ax.set_ylabel("cumulative waiting time (vehicle-hours)")
    ax.set_title("Cumulative waiting time - lower is better (gap to Fixed-Time = time saved)")
    ax.legend()
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)


def plot_queue_over_time(rows, out_png, peak_window=None):
    """Plot each controller's total-queue trace over decisions.

    Shows how Fixed-Time spikes during a demand surge while adaptive control
    (DQN, Max-Pressure) stays lower. peak_window=(start,end) shades the peak.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 5))
    for r in rows:
        series = r.get("queue_series") or []
        if series:
            ax.plot(range(len(series)), series, label=r["controller"])
    if peak_window:
        ax.axvspan(peak_window[0], peak_window[1], color="red", alpha=0.10,
                   label="peak window")
    ax.set_xlabel("decision (every action_interval)")
    ax.set_ylabel("total queued vehicles")
    ax.set_title("Network queue over time - lower is better")
    ax.legend()
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)


def plot_training_curve(train_log, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    eps = train_log["episodes"]
    x = [e["episode"] for e in eps]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(x, [e["mean_reward"] for e in eps]); ax[0].set_title("Mean reward / episode")
    ax[1].plot(x, [e["mean_total_queue"] for e in eps]); ax[1].set_title("Mean queue / episode")
    for a in ax:
        a.set_xlabel("episode")
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)
