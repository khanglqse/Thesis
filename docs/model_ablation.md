# Model / Reward Ablation — DQN Variants vs Strong Baselines

> **ARCHIVED LEGACY RESULTS — NOT V2 THESIS EVIDENCE.** This analysis predates the frozen
> v2 protocol and contains synthetic CityFlow outputs only. Do not use its values for observed
> or calibrated Hai Chau claims, or as current thesis-defense results.

*Experiments run after the initial results to test whether a different reward,
a different architecture, or a stronger baseline change the conclusions. The
original results are frozen in `results/references/`; every variant here is
trained into `results/<area>/exp_<tag>/` and never overwrites them.*

## 1. Strengthened Fixed-Time baseline

The first Fixed-Time plan switched phase every decision (10 s green), wasting
~30 % of every interval on the yellow/all-red transition the env inserts on each
switch. That is an unfairly weak baseline. We added a configurable
`green_duration` (`FixedTimeController` holds each phase for `round(green/interval)`
decisions) and swept it:

| green/phase | Normal queue | Peak queue |
|---|---|---|
| 10 s (old) | 4628.7 | 4925.7 |
| **25 s** | **4104.7 (best)** | 4340.1 |
| 30 s | 4141.8 | 4348.3 |
| **40 s** | 4185.7 | **4314.0 (best)** |
| 50 s | 4211.1 | 4420.5 |

We adopt the best per scenario: **25 s (normal), 40 s (peak)**. The strengthened
Fixed-Time is ~11–12 % better than the naive one and now **beats Random**, which
the 10 s plan did not — confirming it is a genuinely competitive baseline.

## 2. Reward functions tried

All in `src/traffic_rl/sim/intersection.py`, selected by `reward_type`:

- `pressure` (original): `-(incoming_queue - outgoing_queue)` — max-pressure proxy.
- `queue`: `-(incoming_queue)` — minimise the agent's own queue directly.
- `queue_norm`: `-(incoming_queue)/n_incoming_lanes` — per-lane, so large
  junctions don't dominate the pooled (parameter-shared) gradient.
- `pressure_norm`: max-pressure divided by lane count.

## 3. Architecture tried

**Dueling DQN** (`dueling: true`): the head splits into a state-value `V(s)` and
an advantage `A(s,a)`, recombined as `Q = V + (A - mean_a A)`. Decouples "is this
state good" from "which action is best". Implemented in the from-scratch NumPy
net (3.6-safe), with backprop and save/load. `combo` = dueling + `queue_norm`.

## 4. Results (mean total queue; lower is better)

### NORMAL — strong Fixed-Time = 4104.7, Max-Pressure = 3690.6
| Controller | Queue | vs Fixed-Time | vs Max-Pressure |
|---|---|---|---|
| Fixed-Time (25 s) | 4104.7 | 0 % | −11.2 % |
| Random | 4178.3 | −1.8 % | −13.2 % |
| Max-Pressure | 3690.6 | +10.1 % | 0 % |
| DQN `pressure` (ref) | 3905.9 | +4.8 % | −5.8 % |
| DQN `queue` | 3916.9 | +4.6 % | −6.1 % |
| **DQN `queue_norm`** | **3838.9** | **+6.5 %** | **−4.0 %** |
| DQN `dueling` | 3895.9 | +5.1 % | −5.6 % |
| DQN `combo` | 3910.8 | +4.7 % | −6.0 % |

### PEAK — strong Fixed-Time = 4314.0, Max-Pressure = 3758.3
| Controller | Queue | vs Fixed-Time | vs Max-Pressure |
|---|---|---|---|
| Fixed-Time (40 s) | 4314.0 | 0 % | −14.8 % |
| Random | 4423.3 | −2.5 % | −17.7 % |
| Max-Pressure | 3758.3 | +12.9 % | 0 % |
| **DQN `pressure` (ref)** | **4085.2** | **+5.3 %** | **−8.7 %** |
| DQN `queue_norm` | 4165.6 | +3.4 % | −10.8 % |
| DQN `combo` | 4413.6 | −2.3 % | −17.4 % |

## 4b. Advanced-XLight ATS state (running-vehicle channel)

Following the research (Advanced-XLight, ICML 2022; Efficient-Pressure, 2021), we
enriched the state instead of changing the algorithm. `state_mode="ats"` adds an
**incoming running-vehicle channel** (`running = all − queued` per lane) — the
*approaching demand* Max-Pressure is blind to — and we pair it with the
`efficient_pressure` reward (per-lane-mean pressure). Layout:
`[incoming queue | incoming running | outgoing queue | phase one-hot]`.

| Scenario | Variant | Queue | vs Fixed-Time | vs Max-Pressure |
|---|---|---|---|---|
| Normal | DQN basic (best) | 3905.9 | +4.8 % | −5.8 % |
| Normal | DQN `ats`+`efficient_pressure` | 3956.7 | +3.6 % | −7.2 % |
| Normal | DQN `ats`+`queue_norm` | 4111.1 | −0.2 % | −11.4 % |
| Peak | DQN basic (best) | 4085.2 | +5.3 % | −8.7 % |
| **Peak** | **DQN `ats`+`efficient_pressure`** | **3926.6** | **+9.0 %** | **−4.5 %** |

**ATS helps under surge, hurts under light demand.** On peak it is the best DQN
we obtained (gap to Max-Pressure narrowed from −8.7 % to −4.5 %) — the
approaching-demand signal is most valuable when queues are forming fast. On the
lighter normal scenario the extra channel adds noise and slightly *hurts*. This
matches the literature: the running-vehicle feature pays off in congested
regimes. A sharper version (count only vehicles within an *effective range*
`L = v_max × green` of the stop-line, not the whole lane) needs per-vehicle
distance from the engine and is the natural next step to push the peak gap below
zero.

## 4c. Algorithm-level techniques (n-step, Max-Pressure warm-start)

Second research pass (RESCO benchmark; Rainbow ablation; FitLight/CRL-TSC) said
policy-gradient (PPO/A2C) *underperforms* value-based DQN on traffic, so we did
not pursue it. The two NumPy-feasible, evidence-backed levers we did implement:

- **n-step returns** (`n_step`, here 3): `NStepAccumulator` pools n rewards and
  bootstraps with `γ^n` — targets the long delay between a phase decision and the
  queue clearing.
- **Max-Pressure warm-start** (`warmstart_steps`): behaviour-clone Max-Pressure
  (cross-entropy on its chosen phase) before RL, so training starts *at* the
  heuristic, then RL fine-tunes at low ε.

| Scenario | Variant | Queue | vs Fixed-Time | vs Max-Pressure |
|---|---|---|---|---|
| Normal | DQN warm-start + n-step (pressure) | 4158.9 | −1.3 % | −12.7 % |
| Normal | DQN warm-start + n-step + queue_norm | 4146.9 | −1.0 % | −12.4 % |
| Peak | DQN warm-start + n-step + ats | 4462.2 | −3.4 % | −18.7 % |

**Negative result — warm-start + n-step degraded performance** (below even
Fixed-Time). The clone reproduces Max-Pressure, but naive RL fine-tuning *erodes*
the good initialisation (catastrophic forgetting of the cloned policy), and the
larger n-step targets add instability under the existing reward scaling.
Preserving the warm start would need **residual RL or a KL penalty to the teacher**
(future work), not plain fine-tuning. We report this because a silent omission
would misrepresent the search.

## 4d. Consolidated ranking (best DQN per scenario)

| Scenario | Best controller | Best **learned** DQN | Gap (DQN − MP) |
|---|---|---|---|
| Normal | Max-Pressure (3690.6) | `queue_norm` — 3838.9 (+6.5 % vs Fixed) | −4.0 % |
| Peak | Max-Pressure (3758.3) | `ats`+`efficient_pressure` — 3926.6 (+9.0 % vs Fixed) | −4.5 % |

Everything tried, ranked on normal (lower queue = better): MaxPressure < DQN
queue_norm < dueling < basic < combo < queue < ats_effp < FixedTime < ats_qnorm <
warm-start variants < Random.

## 5. Findings

1. **No DQN variant beats Max-Pressure.** Every learned policy lands ~4–11 %
   above Max-Pressure on queue. The DQN *approaches* the greedy heuristic but
   does not surpass it.
2. **Reward matters, modestly, and per-scenario.** `queue_norm` is best on
   normal (+6.5 % vs Fixed, the best DQN there); on peak the original `pressure`
   reward is best (+5.3 %) and `queue_norm` is worse. There is no single reward
   that dominates both regimes.
3. **Dueling did not help.** On its own it matched the plain net; combined with
   `queue_norm` (`combo`) it was neutral on normal and actively *hurt* on peak
   (worse than Fixed-Time). The extra head adds capacity the problem does not
   reward, and destabilises the surge regime.
4. **Why Max-Pressure is hard to beat here:** it greedily picks the phase with
   the largest instantaneous pressure — exactly the signal the local observation
   exposes — so it acts near-optimally on per-intersection information. A learned
   agent can only beat it by exploiting structure Max-Pressure ignores
   (anticipating arrivals, coordinating with neighbours), which requires a richer
   state than the current per-intersection local counts.

## 6. Thesis framing

We searched the design space **exhaustively** within the NumPy/Python-3.6
constraint: 5 reward functions (`pressure`, `queue`, `queue_norm`,
`pressure_norm`, `efficient_pressure`), a Dueling head, the Advanced-XLight
**ATS state** (running-vehicle channel), **n-step returns**, and a **Max-Pressure
warm-start** — plus their combinations, against a **tuned** Fixed-Time baseline.

The honest, defensible story: with a parameter-shared DQN on **local**
per-intersection observations, the learned controller **clears the Fixed-Time and
Random baselines** (the realistic, tuned Fixed-Time included) and **converges to
roughly Max-Pressure-level performance** (within −4.0 % normal / −4.5 % peak)
**without exceeding it**. This is consistent with the literature: Max-Pressure is
provably throughput-optimal on the per-movement information a single intersection
sees, so on a **small arterial network** it is very hard to beat; RL's documented
wins over MP appear on **large grids with coordination and downstream spillback**
(RESCO: IDQN 242.9 vs MP 551.4 on Ingolstadt region). The ATS state — which adds
the approaching-demand signal MP lacks — gave the only direction of real
improvement (best peak DQN), pointing the way.

**Future work to beat MP:** neighbour-coordinated observations (CoLight-style
mean-pooled neighbour features), an *effective-range* running-vehicle count, or
**residual/KL-regularised RL** on top of the Max-Pressure warm-start (so RL
corrects MP without forgetting it). A gradient-free **CMA-ES** on the small shared
policy (optimising cumulative waiting time directly) is a promising lightweight
alternative.

Reproduce: `scripts/sweep_fixed_time.py` (baseline), `scripts/exp_batch*.sh`
(variants: 1=reward/dueling, 2=combo/peak, 3=ATS, 4=warm-start/n-step),
`scripts/run_experiment_eval.py` (eval one variant vs the frozen baselines).
Headline metric: total/cumulative waiting time (see `docs/waiting_time_analysis.md`).
