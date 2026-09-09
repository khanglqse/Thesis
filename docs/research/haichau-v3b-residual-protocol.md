# V3-B: executed-schedule residual pilot

This pilot addresses persistent signal-clock drift seen after small V3-A phase
deviations. V3-A training and negative results remain intact. This document
preregisters a separate controller family, `schedule_residual_ddqn`; it does not
claim V3-A DDQN or V3-B already improves traffic outcomes.

## Controller and operational input

The declared `normal`, `am_peak`, or `pm_peak` time-of-day mode is passed directly
from the manifest's scenario enumeration. The model observes present phase rows
and macro descriptors only. Case IDs, seeds, filenames, and future demand do
not enter features or action choice. Normal mode executes the independent
reference schedule from reset, without evaluating model scores. This is an
explicit hybrid controller; exact normal behavior is a design constraint.

The reference is the executed validation-selected fixed-25 policy in a
traffic-free `MultiAgentTrafficEnv`, with the same min-green, maximum-red,
compound-service, yellow/all-red, and decision constraints as the real run.
The shadow never assumes a nominal 50s/75s period. State includes current green,
active lightphase, elapsed green, time since switch, full pending transition,
phase service timers, and every movement service timer.

Each trace row at second `k` records the lightphase actually exposed during
`[k-1,k)` separately from the full signal state after the tick. A transition
may finish at the tick boundary; using only the resulting active phase would
undercount phase exposure. `service_divergence_seconds` explicitly counts
movement-service-timer differences. `scripts/audit_haichau_schedule.py` persists
both streams for the two- and three-green regression nodes.

At each 300s boundary, each peak-mode node selects one compiled macro. Macro0
is the exact reference. Other macros advance or delay one planned request
boundary by 10s, then execute the original reference commands. The compiler
simulates every request on a cloned signal automaton and rejects illegal
requests, changes with no executed effect, or any terminal state mismatch.
Initial and later blocks are compiled from their actual reference anchor.
All selected actions are checked again at runtime; unexpected illegal requests
or anchor mismatch stop the run. Macro0 wins any tie for the highest score
that includes the baseline. Ties among nonbaseline macros use the lowest macro
index deterministically. Nonfinite observations or scores select macro0 and
record the reason. No traffic-dependent state is teleported at an anchor.

## Learning and reward

A shared two-layer MLP scores each available macro using 27 features: 12 current
source-phase features, 12 current target-phase features, boundary position in
the block, signed shift, and baseline indicator. The output head starts at
zero, so the initial greedy controller chooses macro0. Exploration is explicit
and train-only. Decisions occur only at block starts.

Each completed macro receives the same cooperative network reward at every
node: the negative change in `queue_integral_vehicle_seconds`, checked against
network waiting integral plus due-not-inserted entry-pending integral. It covers
all 2,340 network lanes, including roads outside controlled incoming projections.
No future/unreleased vehicles are counted. There is no local-queue or switch
penalty in this objective. Replay and logs retain its exact physical reward;
the critic expresses values in a fixed, preregistered unit of 100,000
vehicle-seconds, so its immediate numerical reward is `-raw_cost / 100000`.
This prevents raw macro costs from all saturating Huber delta1 at initialization.
Physical queue/completion/insertion metrics remain unscaled. Every macro logs
both raw components, raw objective, and scaled reward. Contracts and NPZ
metadata bind the critic unit, sign, and components; a unit mismatch fails on
reload. Targets discount once per 300s macro (`gamma_per_macro=0.99`); terminal
macros never bootstrap.

## Smoke and pilot evidence

Smoke runs two peak training episodes of 600s, then the first declared
validation case in each of normal/AM/PM for 600s. For each, forced macro0 is
compared against a fresh fixed-25 simulation and must match queue integral,
completion, and insertion exactly. A separate scripted-macro test checks legal
execution, bounded phase divergence, terminal resynchronization, and reload.

Pilot uses seed11, four balanced peak training episodes of 3600s, with six
full-hour validation cases at checkpoints2/4. No held-out case is opened by
training or validation. A paired forced-macro0 counterfactual is run once per
validation case and reused across checkpoints; macro0 never reads weights,
so this comparison is independent of checkpoint parameters. The tuned fixed
artifact is hash-verified and must select25s before any run begins.

Selection does not trust that reuse claim. It reruns candidate and forced
macro0 from both reloaded checkpoint bundles and independently reruns fixed25.
The forced-macro0 result must equal fixed25 in every case and must remain
identical when the checkpoint weights change from step2 to step4.

The preregistered selector must fail closed unless: normal is exact; mean queue
regret in each peak regime is at most0; maximum case completion/insertion loss
is at most2 percentage points; mean peak regret is at most-1%; learned nonzero
macros occur in both peak regimes at at least two nodes; and illegal requests,
anchor violations, and unexplained execution divergence are all zero. Neither
training return nor smoke performance selects a final model.

The immutable selector specification is
`configs/haichau_residual_pilot_selection_v1.yaml`. It admits only pilot seed11
and checkpoints2/4. Among eligible checkpoints it minimizes the paired mean
peak queue-regret percentage, then chooses the earlier training step on an
exact tie. These ranking fields and their order are part of the registered
schema; changing or rehashing them is rejected.

The selector also pins the complete source configuration at
`configs/haichau_training_v3b_residual.yaml` with raw-file SHA256
`8195782b5d099bd7a04de03bfebfd5206957e7d76ada354047c971cbb3d6e75a`.
It verifies both the working file and the blob read from the declared source
commit. This binds every value, including epsilon and updates per macro. The
selector specification, experiment manifest, baseline tuning artifact,
network, phase contract, and six validation flows must likewise match the
files stored at that source commit and their declared hashes.

The selector recomputes every metric from the six source rows. In normal mode,
queue, completion, and insertion must equal the fixed-25 counterfactual for
each case, and phase, service, full-state, illegal-request, anchor,
unlogged-divergence, and nonzero-macro counts must all be zero. For AM and PM,
each regime mean must be noninferior, the combined paired mean must improve by
at least1%, and every case must stay within2 percentage points for completion
and insertion. Both peak regimes must contain learned nonzero macros spanning
at least two distinct controlled nodes.

For both checkpoints, the selector runs a fresh deterministic CityFlow replay
for every candidate and forced-macro0 row, plus a fresh fixed25 replay for every
case. It compares the complete metrics, macro rewards, policy audit, and macro
event/action sequence with the recorded row. A streaming digest covers every
second and controlled node, including the lightphase served during the second
and the complete future-relevant signal state after it. Normal and forced
macro0 timelines must equal fixed25 exactly. Forced macro0 metrics, actions,
and timelines must also match across both weight bundles. Aggregate counters
alone cannot establish these equalities.

The selector loads the exact hash-bound contract/NPZ, checks all parameter
metadata and finiteness, and perturbs every live source/target demand feature
under deterministic valid-range probes. A descriptor-only fixed-schedule clone
therefore cannot qualify. The replay establishes the separate computational
link that the chosen nonzero macros and reported improvement were produced by
those reloaded weights; the legacy `reload_score_identity` flag is not treated
as evidence.

On success the selector persists the complete replay evidence at the
preregistered `validation_rerun_output`; the decision hash-binds that artifact
and the selected YAML hash-binds its record. The selected YAML keeps a path
back to the decision, avoiding a circular file-hash claim. A later release
validator can call `validate_selected_outputs` from a descendant commit with
the real environment runner. It reloads both original bundles, repeats all
rollouts, compares the persisted replay evidence, and recomputes selection. A
rejected pilot writes a rejection decision and replay evidence, but no selected
configuration.

Every run records immutable source-tree provenance, resolved configuration,
baseline tuning, learning curves, checkpoint contracts/weights, reload-score
identity, independent per-second signal audits, macro events, abstention
reasons, and final artifact hashes. Full final-training and campaign integration
must follow a successful pilot selection and remain a separate release step.

## Commands

Run from a clean tracked tree in the pinned CityFlow image with the project
mounted at its real absolute location (linked-worktree Git provenance also
requires access to the common Git directory):

```sh
PYTHONPATH=src:. python3 scripts/train_haichau_residual.py --mode smoke --learning-seed 11 --config configs/haichau_training_v3b_residual_smoke.yaml --output results/haichau_network_v2/training/smoke-v3b-residual-seed11
PYTHONPATH=src:. python3 scripts/train_haichau_residual.py --mode pilot --learning-seed 11 --output results/haichau_network_v2/training/pilot-v3b-residual-seed11
PYTHONPATH=src:. python3 scripts/select_haichau_residual_pilot.py --spec configs/haichau_residual_pilot_selection_v1.yaml
```

Outputs are immutable; an interrupted run requires a new output directory.
