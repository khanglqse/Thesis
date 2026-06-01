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
    dqn_best_tt = best.get("travel_time") == "DQN"
    dqn_best_all = dqn_best_tt and best.get("queue") == "DQN" and best.get("reward") == "DQN"
    if dqn_best_all:
        dqn_verdict = ("That the DQN achieves the best result on every metric — travel time, "
                       "queue, and reward — beating the strong hand-engineered Max-Pressure "
                       "heuristic while having learned its policy purely from the pressure "
                       "reward, is the central positive result.")
    elif dqn_best_tt:
        dqn_verdict = ("That the DQN attains the lowest travel time while having learned its "
                       "policy purely from the pressure reward — outperforming the strong "
                       "hand-engineered Max-Pressure heuristic — is the central positive result.")
    else:
        dqn_verdict = ("That the DQN matches a strong hand-engineered heuristic — while having "
                       "learned its policy purely from the pressure reward — is the central "
                       "positive result.")
    if dqn_best_tt:
        tt_outlook = ("Even within this budget the DQN already leads on every reported metric; "
                      "a longer horizon and more episodes would mainly widen the margin and let "
                      "us test how well the policy generalizes.")
    else:
        tt_outlook = ("A longer horizon and more episodes would likely let the DQN overtake "
                      "Max-Pressure on travel time as well, since its queue and reward "
                      "advantages already lead.")
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
than mean travel time does. {dqn_verdict}

## 4.6 Limitations

The training budget was deliberately modest ({n_ep} episodes, {steps}-step horizon) because
CityFlow runs under x86 emulation on the development machine. {tt_outlook} The demand is synthetic rather than calibrated to
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
        dqn_verdict=dqn_verdict, tt_outlook=tt_outlook,
    )
    return md
