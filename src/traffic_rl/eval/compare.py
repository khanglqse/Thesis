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
