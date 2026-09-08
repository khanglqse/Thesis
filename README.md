# RL for Multi-Intersection Traffic Signal Control — Hải Châu, Đà Nẵng

A master's-thesis study of **reinforcement learning for urban traffic signal control**.
The empirical study reconstructs one published Da Nang intersection in SUMO. The spatial
extension evaluates 53 signals on an **OpenStreetMap-derived Hải Châu topology** in
[CityFlow](https://cityflow-project.github.io/) with synthetic demand constrained by the
available Da Nang evidence. It does not claim observed district-wide flows or signal plans.

> **Current thesis:** `paper/thesis_danang.tex`.
> **Evidence limits:** `docs/research/foundation-handoff.md` and
> `docs/research/legacy-claims-audit.md`.

## Evidence namespaces

The checked-in results described below are the legacy study. They remain available for
reproduction and defense use, but they do not count as evidence for the new 53-signal
neighbor-aware DDQN extension.

The extension uses the separate `haichau_network_v2` namespace. Its demand label is always
**synthetic network demand constrained by Da Nang evidence**. A result becomes releasable
only when `scripts/verify_haichau_thesis.py` reports `"complete": true`; a failed acceptance
outcome is still reported as a valid negative result once every evidence gate is complete.
At present the final five-seed checkpoints, frozen case manifest and fresh campaign have to
be supplied by the foundation/model pipeline before that verifier can pass.

The exact campaign, thesis, offline-demo and clean-checkout procedure is in
`docs/defense/demo-runbook.md`.

## Legacy-study headline finding

The learned controller's advantage tracks **network saturation**, and we report the whole
spectrum rather than a single flattering point:

| Regime (measured load) | DQN vs tuned Fixed-Time | Reading |
|---|---|---|
| `haichau_rush` — legacy synthetic load (~50k scheduled departures, ~2.9k concurrent, 42% stopped) | **best legacy improvement** | historical result; not empirical calibration |
| `haichau_calib` — moderately heavy (51% stopped) | positive | |
| `haichau_peak` / `haichau` — (grossly) oversaturated (65–68% stopped) | **degrades, can lose to Fixed** | no local policy can drain a gridlocked network |

Two robust, honestly-reported conclusions:
1. The legacy DQN **clears Fixed-Time and Random and converges to roughly Max-Pressure-level
   performance at one synthetic load — but never beats Max-Pressure** on this arterial
   network, where local pressure is nearly sufficient (Max-Pressure is throughput-optimal on
   the local information a single agent sees).
2. Under **gross oversaturation** the local value-based controller **degrades below Fixed-Time**
   — reported as a limitation, not hidden.

Exact multi-seed means ± 95% CI are in `paper/chapter4_experiments_results.tex`
(`tab:waiting`, `tab:queue`). Those historical runs did not implement neighbor-aware
coordination. The `haichau_network_v2` extension now implements a mean-pooled neighbor
phase-scoring DDQN as a separate candidate; it does not implement learned graph attention,
and it has no releasable performance claim until the final verifier passes.

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

## Reproduce the legacy results

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

## Legacy live demo

A browser demo replays recorded episodes and lets you switch (scenario × controller) live,
with an always-on projector-legible HUD and a cumulative-waiting scoreboard.

```sh
# serve the repo root; demo at http://localhost:8080/frontend/index.html
nohup python3 -m http.server 8080 --directory "$PWD" >/tmp/demo.log 2>&1 &
```
Pick a legacy preset and a controller; the view
auto-zooms to the busiest signalized junction so moving vehicles and switching lights are
visible. Preset/HUD logic: `frontend/demo-presets.js`. Treat the displayed demand as a
synthetic simulator scenario; scheduled departures, concurrent vehicles, and completed
vehicles are separate quantities.

## Tests

```sh
make test        # host unit tests (no CityFlow needed): pytest -m 'not docker'
make cf-test     # engine integration tests inside the CityFlow container
```

The fail-closed audit for the 53-signal extension is:

```sh
PYTHONPATH=src python3 scripts/verify_haichau_thesis.py
```

It writes `results/haichau_network_v2/verification/final-report.json` and exits nonzero
until the network, split, ten learned checkpoint bundles (two controller families × five
seeds), fresh matched runs, statistics, paper, offline demo and clean-checkout record are all
hash-valid.

### Pre-final Hai Chau capacity calibration

Before final learning, prepare and run the pre-registered validation-only capacity checks.
Preparation is the CLI default and does not import or start CityFlow:

```sh
PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py \
  --stage scale1 \
  --output results/haichau_network_v2/diagnostics/capacity-scale1
PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py \
  --stage ladder \
  --output results/haichau_network_v2/diagnostics/capacity-ladder
```

Execute those immutable inputs in the pinned research image. Repeating either command resumes
only missing or failed runs after checking all bound hashes:

```sh
docker run --rm --platform linux/amd64 -v "$PWD":/work -w /work \
  traffic-rl-cityflow-research:v2 sh -lc \
  'PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py --stage scale1 --output results/haichau_network_v2/diagnostics/capacity-scale1 --execute'
docker run --rm --platform linux/amd64 -v "$PWD":/work -w /work \
  traffic-rl-cityflow-research:v2 sh -lc \
  'PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py --stage ladder --output results/haichau_network_v2/diagnostics/capacity-ladder --execute'
```

After reviewing only the ladder's validation diagnostics, prepare stage D with one or more of
the registered scales `0.25`, `0.30`, and `0.35`. This exact example advances `0.25` and
`0.30`; replace both occurrences together if the recorded validation decision selects a
different registered set:

```sh
PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py \
  --stage stage-d --chosen-scales 0.25,0.30 \
  --output results/haichau_network_v2/diagnostics/capacity-stage-d-s025-s030
docker run --rm --platform linux/amd64 -v "$PWD":/work -w /work \
  traffic-rl-cityflow-research:v2 sh -lc \
  'PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py --stage stage-d --chosen-scales 0.25,0.30 --output results/haichau_network_v2/diagnostics/capacity-stage-d-s025-s030 --execute'
```

The optional extended drain probe is a separate immutable stage directory:

```sh
docker run --rm --platform linux/amd64 -v "$PWD":/work -w /work \
  traffic-rl-cityflow-research:v2 sh -lc \
  'PYTHONPATH=src python3 scripts/calibrate_haichau_capacity.py --stage scale1 --drain-horizon 7200 --output results/haichau_network_v2/diagnostics/capacity-scale1-drain7200 --execute'
```

Every output is marked diagnostic and ineligible for release or test evaluation. The runner
filters the case manifest to the six validation records before opening flows; it never reads
the test flow paths. Passing calibration authorizes a later pre-final scale decision, not a
thesis result by itself.

The verifier recomputes the numeric summary and acceptance decision from the hash-verified
run metrics. It also requires exact frozen run identity (flow hash, simulator seed,
checkpoint, code commit, inspected Docker image and resolved config). Each learned family
must contain seeds 11--15, and every seed must contain the exact tuned-fixed
demand/simulator cells, with at least two cells in every gated regime. The current checkout
must be clean, descend from the frozen
40-character commit and leave `src/`, `scripts/`, `frontend/`, `docker/` and build config
unchanged. Paper/demo artifacts are content-hashed; `pdfinfo`/`pdftoppm`, `ffprobe` and a
full `ffmpeg -xerror` decode must parse/render the PDFs, PNGs and MP4, and replays cover the
full horizon. `scripts/attest_haichau_release.py` generates the clean-checkout evidence with
exact command results, tool versions and hashed stdout/stderr logs; the final verifier
rejects hand-written summary records, reads artifacts from the attested Git commit and
directly re-runs the release command contract. Campaign release verification also requires
the stopped Docker containers so it can inspect their real image/config/exit state and logs.
Release execution uses detached `docker run` plus `docker wait`: `stdout.log` and
`stderr.log` come only from `docker logs`, while Docker CLI/daemon stderr (such as the
Apple Silicon x86-image platform warning) is hashed separately in
`docker-cli-diagnostics.json`.

## Scope: empirical anchor vs scale experiment

The empirical evidence supports a **single demand-matched SUMO junction** reconstructed from
four camera movement lines, a published timing plan and audited geometry. Its findings are
site- and regime-specific.

The `haichau_network_v2` work is a **53-signal synthetic CityFlow scale experiment**. It
implements both a legacy parameter-shared vector DDQN and a mean-pooled neighbor-aware
phase-scoring DDQN, evaluated against validation-tuned fixed-time and two Max-Pressure
baselines. It can test software scalability and coordination behavior inside the frozen task
family. It is not empirical validation of district-wide traffic, signal timing or field
performance, and its result section remains conditional until
`scripts/verify_haichau_thesis.py` reports `"complete": true`. Learned graph attention,
measured district OD demand and field-calibrated multi-signal operation remain future work.
