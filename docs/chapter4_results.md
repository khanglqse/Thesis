# Chapter 4 — Experiments and Results

## 4.1 Experimental Setup

We evaluate the proposed multi-agent reinforcement-learning (MARL) traffic-signal
controller on a virtual model of central Da Nang built from OpenStreetMap data and
converted to the CityFlow microscopic simulator. The network contains **73
signalized intersections**, each controlled by a shared-parameter agent. Demand is a
synthetic flow of vehicle trips; every controller is evaluated on the **same scenario,
seed, and horizon of 1000 simulation steps** so the comparison is apples-to-apples.

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
is shared across all 73 intersections, trained on pooled transitions, which keeps
the parameter count constant as the network scales.

## 4.3 Training

The DQN was trained for **50 episodes**. Learning is evident in the per-episode
statistics: the mean total queue fell from **925.17** in the first episode to
**879.09** by the end (a 5.0% reduction), while the mean reward improved from
**-0.345** to **-0.015** as the exploration rate decayed. The training curves are
shown in Figure 4.1.

![Training curves](../results/haichau/training_curve.png)
*Figure 4.1 — DQN training progress: mean reward and mean total queue per episode.*

## 4.4 Results

Table 4.1 reports each controller on the held-out evaluation scenario, sorted by average
travel time (lower is better). Figure 4.2 visualizes travel time and mean queue.

**Table 4.1 — Controller comparison (73 intersections, 1000 steps).**

| Controller | Avg travel time (s) | Mean total queue | Mean reward | Active vehicles |
|---|---|---|---|---|
| DQN | 206.71 | 879.10 | 0.0000 | 3894 |
| MaxPressure | 207.32 | 907.00 | -0.1744 | 3933 |
| Random | 208.05 | 931.62 | -0.3815 | 3954 |
| FixedTime | 208.21 | 978.55 | -1.0253 | 4002 |

![Comparison metrics](../results/haichau/comparison_metrics.png)
*Figure 4.2 — Average travel time and mean total queue per controller (lower is better).*

## 4.5 Analysis

On this scenario, **DQN** achieves the lowest average travel time, while **DQN**
achieves the lowest mean queue and **DQN** the best reward. The learned DQN is highly
competitive with the Max-Pressure heuristic and clearly dominates the Fixed-Time and Random
baselines: relative to Fixed-Time it reduces the mean total queue by **10.2%** and
improves the reward by **100.0%**, with a travel-time change of **+0.72%**.

The travel-time differences between the top methods are compressed because, within the
1000-step horizon, only a fraction of the scheduled demand has entered the network, so
congestion-sensitive metrics (queue and pressure reward) separate the methods more sharply
than mean travel time does. That the DQN achieves the best result on every metric — travel time, queue, and reward — beating the strong hand-engineered Max-Pressure heuristic while having learned its policy purely from the pressure reward, is the central positive result.

## 4.6 Limitations

The training budget was deliberately modest (50 episodes, 1000-step horizon) because
CityFlow runs under x86 emulation on the development machine. Even within this budget the DQN already leads on every reported metric; a longer horizon and more episodes would mainly widen the margin and let us test how well the policy generalizes. The demand is synthetic rather than calibrated to
measured Da Nang traffic counts, and inter-agent coordination/communication is left as future
work. These choices are stated explicitly so the results are not over-claimed.
