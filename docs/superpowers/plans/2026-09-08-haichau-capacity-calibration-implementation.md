# Hai Chau Capacity Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hash-bound, validation-only capacity-calibration runner that measures scale-1 failure, a three-scale demand ladder, drain behavior, and full Fixed-Time/Max-Pressure validation without opening test flows.

**Architecture:** A focused `traffic_rl.eval.capacity_calibration` module owns immutable preparation, stage expansion, scaled-flow/free-flow calculations, metric gates, and resumable execution. A thin CLI selects a stage and defaults to prepare-only; the existing environment, `NetworkMetricsObserver`, Fixed-Time controller, and corrected Max-Pressure controller perform explicit Docker execution.

**Tech Stack:** Python 3.6-compatible standard library, NumPy-compatible existing simulator stack, pytest, CityFlow only in the pinned Docker runtime.

**Spec:** `docs/superpowers/specs/2026-09-08-haichau-capacity-calibration-design.md`

## Global Constraints

- Open only manifest cases whose split is exactly `validation`; never hash, parse, or execute a test flow.
- All output must be diagnostic with `eligible_for_release = false` and `eligible_for_test_evaluation = false`.
- Preserve immutable inputs and completed results; resume only when every bound hash matches.
- Support Python 3.6 and do not import CityFlow at module import time.
- Do not run CityFlow or write live result artifacts while implementing this plan.

---

### Task 1: Demand scaling and free-flow eligibility

**Files:**
- Create: `src/traffic_rl/eval/capacity_calibration.py`
- Create: `tests/eval/test_capacity_calibration.py`

**Interfaces:**
- Produces: `scale_flow(flow, scale, profile_bins)`, `scheduled_departures(row)`, and `free_flow_eligible_by_snapshot(flow, roadnet_payload, snapshot_seconds)`.

- [ ] Write tests proving structural preservation, normalized offset scaling, exact scheduled counts, and free-flow counts.
- [ ] Run the focused tests and confirm they fail because the module is absent.
- [ ] Implement the three pure functions with finite positive scale validation.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Validation-only immutable preparation

**Files:**
- Modify: `src/traffic_rl/eval/capacity_calibration.py`
- Modify: `tests/eval/test_capacity_calibration.py`

**Interfaces:**
- Produces: `prepare_campaign(project_root, manifest_path, config_path, output_dir, stage, chosen_scales, drain_horizon)` returning the immutable campaign payload.

- [ ] Write failing tests for exact stage expansion, a missing test-flow sentinel, diagnostic flags, hash bindings, idempotent preparation, and drift refusal.
- [ ] Run focused tests and verify the expected failures.
- [ ] Implement validation selection, stage expansion, artifact hashing, immutable writes, and per-run manifests.
- [ ] Run focused tests and confirm they pass.

### Task 3: Snapshot rollout, gates, and resumable execution

**Files:**
- Modify: `src/traffic_rl/eval/capacity_calibration.py`
- Modify: `tests/eval/test_capacity_calibration.py`

**Interfaces:**
- Produces: `rollout_with_snapshots(env, controller, snapshot_interval)`, `evaluate_run_gates(run, snapshots)`, `evaluate_stage_gates(campaign, completed_results)`, and `execute_campaign(..., run_executor=None)`.

- [ ] Write failing tests for 300-second snapshots, every pre-registered threshold, aggregate PM ordering, partial status persistence, exact resume, and stale-result refusal.
- [ ] Run focused tests and verify the expected failures.
- [ ] Implement the rollout, gate evaluators, default Fixed-Time/Max-Pressure executor, atomic status/result writes, and summary rebuild.
- [ ] Run focused tests and confirm they pass.

### Task 4: Safe CLI and operator commands

**Files:**
- Create: `scripts/calibrate_haichau_capacity.py`
- Create: `tests/scripts/test_calibrate_haichau_capacity.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `prepare_campaign` and `execute_campaign`.
- Produces: CLI stages `scale1`, `ladder`, and `stage-d`, with preparation as the default and explicit `--execute`.

- [ ] Write failing CLI tests for default preparation, explicit execution, chosen-scale parsing, and invalid option rejection.
- [ ] Run CLI tests and verify the expected failures.
- [ ] Implement the thin CLI and document exact host preparation and pinned Docker execution commands.
- [ ] Run CLI and focused library tests and confirm they pass.

### Task 5: Verification and commit

**Files:**
- Verify all files above plus `docs/research/decision-log.md`.

- [ ] Run focused calibration, metrics, environment, pressure-controller, and CLI tests.
- [ ] Run the broader evaluation and script test suites.
- [ ] Compile new Python files under the repository's Python 3.6 compatibility check if available.
- [ ] Review `git diff --check`, diagnostic flags, test-flow sentinel coverage, and confirm no live artifacts or containers were created.
- [ ] Commit the implementation and report commit hash, test counts, artifact hashes, and exact Docker commands.
