# RL Traffic Signal Control for Hải Châu, Đà Nẵng

This repository contains the thesis implementation for adaptive traffic-signal
control on an OpenStreetMap-derived 53-signal Hải Châu network in CityFlow.
Demand is synthetic and constrained by Da Nang evidence; it is not a claim of
observed district-wide flows, routes, or signal plans.

The current thesis source is `paper/thesis_danang.tex`. The current demo guide
is `docs/defense/demo-runbook.md`.

## Presentation demo

The only supported browser demo is the self-contained visual replay:

```sh
cd results/haichau_network_v2/demo-visual
python3 launch_demo.py --no-browser --port 8766
```

Open `http://127.0.0.1:8766/index.html`, wait for **Verified replay loaded**,
then press **Reset to guided view**. The guided frame compares the matched
Fixed-time and DDQN runs at junction `420249521`; the panel states the queue
difference directly.

The replay is a recorded PM-peak visualisation. It illustrates controller
behaviour and does not replace the full-horizon evaluation evidence.

## Project layout

```text
src/traffic_rl/                         controller, CityFlow and evaluation code
datasets/haichau_network_v2/            topology inputs
results/haichau_network_v2/             frozen data, replays and results
results/haichau_network_v2/demo-visual/ portable browser demo
scripts/                                data preparation, training, evaluation and packaging
paper/thesis_danang.tex                 thesis source
docs/defense/                           presentation materials
```

## Verification

```sh
PYTHONPATH=src python3 scripts/verify_haichau_thesis.py
node --test tests/replay_ab/haichau_network_demo_core.test.cjs
```

The strict verifier reports the evidence status. Do not turn an exploratory or
partial replay result into a deployment claim.
