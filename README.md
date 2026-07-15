# RL for Multi-Intersection Traffic Signal Control — Hải Châu, Đà Nẵng

A master's-thesis study of **reinforcement learning for urban traffic signal control**,
evaluated on a **real arterial network of Hải Châu district, Đà Nẵng** (53 signalized
intersections) modeled in the [CityFlow](https://cityflow-project.github.io/) microscopic
simulator. A single **parameter-shared Deep Q-Network** (implemented from scratch in NumPy)
controls all intersections and is compared against tuned **Fixed-Time**, **Max-Pressure**,
and **Random** baselines across a spectrum of demand regimes.

> **Full write-up:** `paper/trafic_rf.tex` (Chapter 4 = experiments & results).
> **Scenario framing & honest numbers:** `docs/scenario_regimes.md`.

## Headline finding

The learned controller's advantage tracks **network saturation**, and we report the whole
spectrum rather than a single flattering point:

| Regime (measured load) | DQN vs tuned Fixed-Time | Reading |
|---|---|---|
| `haichau_rush` — realistic arterial peak (~50k trips, ~2.9k concurrent, 42% stopped) | **best improvement** (headline) | queues form but clear — control has leverage |
| `haichau_calib` — moderately heavy (51% stopped) | positive | |
| `haichau_peak` / `haichau` — (grossly) oversaturated (65–68% stopped) | **degrades, can lose to Fixed** | no local policy can drain a gridlocked network |

Two robust, honestly-reported conclusions:
1. The DQN **clears Fixed-Time and Random and converges to roughly Max-Pressure-level
   performance at realistic demand — but never beats Max-Pressure** on this small arterial
   network, where local pressure is nearly sufficient (Max-Pressure is throughput-optimal on
   the local information a single agent sees).
2. Under **gross oversaturation** the local value-based controller **degrades below Fixed-Time**
   — reported as a limitation, not hidden.

Exact multi-seed means ± 95% CI are in `paper/chapter4_experiments_results.tex`
(`tab:waiting`, `tab:queue`). Coordination (neighbor-aware state / graph attention) is the
identified route to surpassing Max-Pressure and is future work.

## Repository map

```
src/traffic_rl/        core library (pure Python, container-safe)
  agents/              controllers: DQN, Max-Pressure, Fixed-Time, Random
  network/             OSM -> CityFlow roadnet building, arterial scoping, neighbors
  sim/                 CityFlow engine wrapper, state encoder, reward, perturbations
  train/               from-scratch NumPy DQN + trainer (replay, target net, greedy-eval)
  eval/                comparison, multi-seed CI, agreement, cumulative-waiting metric
  report/              plots & presentation figures
scripts/               entry points (train, eval, aggregate, batch experiments, demo server)
data/danang/           roadnets + flow scenarios (haichau_rush, _calib, _peak, haichau, ...)
results/<scenario>/    comparison.json, training curves, demo replays, exp_* variant runs
frontend/              browser demo (CityFlow viewer + preset launcher + HUD)
paper/                 LaTeX thesis (trafic_rf.tex) + chapter4 + references.bib
docs/                  results write-ups, ablation, scenario framing, analysis
configs/               network.yaml, training.yaml
tests/                 33 test files (host + container-marked)
Makefile               cf-run / test / cf-test / cf-smoke targets
```

## Environment

CityFlow ships as an x86 Python-3.6 image and is run via Docker. On Apple Silicon we use
**Colima** (Virtualization.Framework) as the Docker runtime; the container runs under x86
emulation (slow but correct, and it survives host sleep).

```sh
# one-time: start the Docker runtime (Colima) and pull the image
colima start
docker pull cityflowproject/cityflow:latest
make cf-smoke          # -> "cityflow OK"

# host-side tooling (reporting, dashboard, aggregation) uses Python 3.13
pip install -r requirements-host.txt
```

All simulator work runs inside the container through one wrapper:

```sh
make cf-run CMD="PYTHONPATH=src python3 scripts/<script>.py <args>"
```

## Reproduce the results

Scenarios live in `data/danang/` as `roadnet_<scen>.json` + `flow_<scen>.json`
(`haichau_rush`, `haichau_calib`, `haichau_peak`, `haichau`). Each result is written to
`results/<scen>/comparison.json` (and `exp_<tag>/` for variants), never overwriting frozen
baselines in `results/references/`.

**1. Baselines + a single DQN, one scenario:**
```sh
make cf-run CMD="PYTHONPATH=src python3 scripts/run_comparison.py haichau_rush"
```

**2. Train the best-config DQN and evaluate it (fixed report-horizon checkpoint selection):**
```sh
make cf-run CMD="EXP_TAG=best REWARD_TYPE=queue_norm REWARD_SCALE=0.5 COUNT_NORM=5 \
  EPISODES=120 EVAL_EVERY=5 PYTHONPATH=src python3 scripts/train_dqn.py haichau_rush"
make cf-run CMD="EXP_TAG=best MAX_STEPS=1000 PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_rush"
```
Per-scenario best configs are in `scripts/exp_multiseed_tier2.sh::cfg_for` and in Chapter 4
`tab:dqncfg`.

**3. Multi-seed CI (the headline numbers) — retrain best config × K seeds, then aggregate:**
```sh
# detached, resumable (skips seeds whose exp_ms<k>/comparison.json exists)
docker run -d --name ms -v "$PWD":/work -w /work cityflowproject/cityflow:latest \
  sh -lc 'sh scripts/exp_multiseed_tier2.sh'
# when done, on the host:
PYTHONPATH=src python3 scripts/aggregate_multiseed.py haichau_rush   # -> results/multiseed/*.json
PYTHONPATH=src python3 scripts/emit_ch4_tables.py                    # -> LaTeX rows (+CI), stale-guarded
```

**4. Robustness (sensor noise / incidents / demand shift) and DQN↔Max-Pressure agreement:**
```sh
make cf-run CMD="PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush"
make cf-run CMD="PYTHONPATH=src python3 scripts/run_agreement.py haichau_rush"
```

## Live demo

A browser demo replays recorded episodes and lets you switch (scenario × controller) live,
with an always-on projector-legible HUD and a cumulative-waiting scoreboard.

```sh
# serve the repo root; demo at http://localhost:8080/frontend/index.html
nohup python3 -m http.server 8080 --directory "$PWD" >/tmp/demo.log 2>&1 &
```
Pick a preset (e.g. *Hải Châu — cao điểm thực tế ~50k xe*) and a controller; the view
auto-zooms to the busiest signalized junction so moving vehicles and switching lights are
visible. Preset/HUD logic: `frontend/demo-presets.js`. Grounding of the on-screen vehicle
count vs the real Đà Nẵng fleet: `docs/danang_peak_demo_scenario.md`.

## Tests

```sh
make test        # host unit tests (no CityFlow needed): pytest -m 'not docker'
make cf-test     # engine integration tests inside the CityFlow container
```

## Scope: validated vs proposed

The thesis specifies an ambitious **coordination-aware multi-agent RL framework**; what is
**empirically validated here** is its core **parameter-shared DQN instance** on the Hải Châu
network against strong baselines, with a systematic ablation over reward, state, and
architecture. Neighbor-coordinated observations (CoLight-style attention), effective-range
demand features, and residual/KL-regularized learning on a Max-Pressure warm-start are
**specified as future work** and demarcated as such in the paper (see the "Limitations of the
Empirical Study" section). This validated-vs-proposed boundary is stated explicitly so the
results are not over-claimed.
