# Strengthened Empirical Study — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use `- [ ]` checkboxes.

**Goal:** Add four empirical components (multi-seed CI, DQN↔MP agreement, robustness, neighbor-coordinated state) that strengthen Chapter 4, without touching frozen baselines.

**Architecture:** Host-first. All *logic* is pure-Python/NumPy (3.6-safe) unit-tested on host with `tests/conftest.py::FakeEngine`. Only *result generation* runs in the CityFlow container (`make cf-run CMD="..."`). Perturbations wrap the engine (env is duck-typed over it), so no env edits are needed for C3.

**Tech Stack:** Python 3.6-safe core (NumPy only), CityFlow (container via Colima), pytest (host), matplotlib (host-only plotting).

## Global Constraints (verbatim)
- **3.6-safe:** no f-strings in `src/traffic_rl/**` (matches existing style: `.format()`), no `from __future__ import annotations`, NumPy-only (no torch/sklearn) in code that runs in-container.
- **Do NOT modify** `results/references/**` or the frozen `results/<scen>/comparison.json`, `dqn_<scen>.npz`, `train_log_*.json`. New outputs go to NEW paths only.
- **count_norm MUST match training** at eval (see `run_comparison.py:31-34`).
- Controllers implement `.act(context)` where `context={"observations","waiting_counts","action_masks"}` and expose `.name`.
- Reuse: `eval/runner.py::run_episode`, `eval/compare.py`, `network/flow_gen.py`, env-var overrides in `scripts/train_dqn.py`.

---

## File Structure

- Create `src/traffic_rl/sim/perturbations.py` — `PerturbedEngine` wrapper (noise + incident). [C3]
- Create `src/traffic_rl/eval/agreement.py` — `AgreementLogger` + `run_agreement`. [C2]
- Create `src/traffic_rl/eval/multiseed.py` — `aggregate_seeds`, `summary_stats`. [C1]
- Modify `src/traffic_rl/sim/encoder.py` — add `state_mode="neighbor"`. [C4]
- Modify `src/traffic_rl/network/roadnet.py` — add `upstream_neighbors(inter_id)`. [C4]
- Create scripts: `scripts/exp_multiseed.sh` [C1], `scripts/run_agreement.py` [C2], `scripts/exp_robustness.sh` + `scripts/run_robustness.py` [C3], `scripts/exp_neighbor.sh` [C4].
- Create `src/traffic_rl/report/strengthened.py` — plots: CI error-bars, agreement heatmap, robustness-degradation curves. [host]
- Tests: `tests/sim/test_perturbations.py`, `tests/eval/test_agreement.py`, `tests/eval/test_multiseed.py`, `tests/sim/test_encoder_neighbor.py`, `tests/network/test_roadnet_neighbors.py`.
- Outputs (NEW dirs): `results/multiseed/`, `results/<scen>/agreement/`, `results/<scen>/robustness/`, `results/<scen>/exp_neighbor/`.

---

## C1 — Multi-seed + Confidence Interval  *(FIRST: gates Chapter 4 numbers)*

### Task C1.1: seed aggregation math (host, TDD)
**Files:** Create `src/traffic_rl/eval/multiseed.py`; Test `tests/eval/test_multiseed.py`.
**Interfaces — Produces:**
- `summary_stats(values) -> {"mean":float,"std":float,"ci95":float,"n":int}` (ci95 = 1.96*std/sqrt(n)).
- `aggregate_seeds(per_seed_rows) -> {controller: {metric: summary_stats}}` where `per_seed_rows` is `list[list[row]]` (outer=seed, inner=the `run_episode` rows), metrics = `mean_total_queue`, `wait_hours` (from `compare.cumulative_wait_hours(row["queue_series"],10)[-1]`), `final_average_travel_time`.

- [ ] **Step 1 — failing test:**
```python
# tests/eval/test_multiseed.py
from traffic_rl.eval.multiseed import summary_stats, aggregate_seeds

def test_summary_stats_basic():
    s = summary_stats([2.0, 4.0, 6.0])
    assert s["mean"] == 4.0 and s["n"] == 3
    assert abs(s["std"] - 1.632993) < 1e-4          # population-ish std (ddof=0)

def test_aggregate_seeds_groups_by_controller():
    seed0 = [{"controller":"DQN","mean_total_queue":100.0,"queue_series":[10.0]*6,"final_average_travel_time":5.0}]
    seed1 = [{"controller":"DQN","mean_total_queue":120.0,"queue_series":[12.0]*6,"final_average_travel_time":5.0}]
    out = aggregate_seeds([seed0, seed1])
    assert out["DQN"]["mean_total_queue"]["mean"] == 110.0
    assert out["DQN"]["wait_hours"]["n"] == 2
```
- [ ] **Step 2 — run, expect fail:** `PYTHONPATH=src:. python3 -m pytest tests/eval/test_multiseed.py -v` → FAIL (module missing).
- [ ] **Step 3 — implement** `multiseed.py` (NumPy `mean`/`std` ddof=0; `wait_hours` via `compare.cumulative_wait_hours`).
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(eval): multi-seed aggregation + 95% CI`.

### Task C1.2: multi-seed run script + container runs
**Files:** Create `scripts/exp_multiseed.sh`, `scripts/run_multiseed.py`.
- `run_multiseed.py <scenario> <K>`: for seed in 0..K-1 → regenerate flow via `flow_gen` with that seed into `data/danang/flow_<scen>_seed<k>.json` (do NOT overwrite the canonical flow), eval all 4 controllers (reuse frozen `dqn_<scen>.npz`) on that flow, collect rows; write `results/multiseed/<scen>.json` = `aggregate_seeds(...)` + raw per-seed. **Tier-1 = eval-only (fast).**
- [ ] Write `run_multiseed.py` reusing `run_comparison.py::_env` pattern but with per-seed flowFile + `saveReplay:false`.
- [ ] **Tier-2 (headline):** extend to retrain DQN per seed for `haichau_rush` + `haichau` (env `EPISODES`, `SEED`) → captures training variance. Gate behind `RETRAIN=1`.
- [ ] Run in container (Claude): `make cf-run CMD="pip install ... ; PYTHONPATH=src python3 scripts/run_multiseed.py haichau_rush 5"` for all 4 scenarios. Verify each writes `results/multiseed/<scen>.json` with n=5.
- [ ] Commit `feat(exp): multi-seed CI runner + results`.

### Task C1.3: fold CI into Chapter 4
- [ ] Host: `report/strengthened.py::plot_ci_bars(multiseed_json, out_png)` (bar + error bar per controller).
- [ ] Update `paper/chapter4_experiments_results.tex` Table 4.1/4.3 → `mean ± std`; **if a mean shifts materially, correct the number AND narrative**; confirm headline sits inside its CI. Remove "provisional" note from spec §5.
- [ ] Commit `results(ch4): multi-seed CI, numbers finalized`.

---

## C2 — Agreement analysis (DQN ↔ Max-Pressure)

### Task C2.1: agreement logger (host, TDD)
**Files:** Create `src/traffic_rl/eval/agreement.py`; Test `tests/eval/test_agreement.py`.
**Interfaces — Produces:**
- `AgreementLogger()` with `.record(dqn_actions:dict, mp_actions:dict)` and `.summary() -> {"n_decisions","n_pairs","agree","agree_rate", "per_agent":{id:rate}}`.
- `run_agreement(env, dqn_controller, mp_controller, max_decisions) -> summary` — drives DQN (applies DQN actions), at each step also computes `mp_controller.act(ctx)` on the SAME ctx (not applied) and records.

- [ ] **Step 1 — failing test:**
```python
# tests/eval/test_agreement.py
from traffic_rl.eval.agreement import AgreementLogger

def test_agreement_counts():
    lg = AgreementLogger()
    lg.record({"A":0,"B":1}, {"A":0,"B":0})   # A agrees, B differs
    lg.record({"A":1,"B":1}, {"A":1,"B":1})   # both agree
    s = lg.summary()
    assert s["n_pairs"] == 4 and s["agree"] == 3
    assert abs(s["agree_rate"] - 0.75) < 1e-9
    assert s["per_agent"]["B"] == 0.5
```
- [ ] **Step 2 — run, expect fail. Step 3 — implement. Step 4 — pass. Step 5 — commit** `feat(eval): DQN-MP agreement logger`.

### Task C2.2: agreement runs + plot
**Files:** `scripts/run_agreement.py`, `report/strengthened.py::plot_agreement`.
- [ ] `run_agreement.py <scenario>`: build env (state_mode/count_norm matching the ckpt), load `dqn_<scen>.npz` + `MaxPressureController(rn)`, call `run_agreement`, write `results/<scen>/agreement/agreement.json`.
- [ ] Run in container for all 4 scenarios. Verify agree_rate ∈ [0,1] and per_agent populated.
- [ ] Host plot: agreement bar per scenario + per-phase-class breakdown. Add a short "Policy agreement" subsection to Chapter 4 citing overall %.
- [ ] Commit `results(ch4): DQN converges to MP (agreement %)`.

---

## C3 — Robustness study

### Task C3.1: PerturbedEngine wrapper (host, TDD)
**Files:** Create `src/traffic_rl/sim/perturbations.py`; Test `tests/sim/test_perturbations.py`.
**Interfaces — Produces:**
- `PerturbedEngine(inner, noise_std=0.0, noise_kind="gauss", seed=0, incident=None)` — duck-typed engine delegating `reset/step/set_tl_phase/vehicle_count/average_travel_time`.
  - `lane_vehicle_counts()`/`lane_waiting_counts()`: return inner counts with per-lane noise added (gauss: `max(0, round(c + N(0, noise_std*max(1,c))))`; dropout: zero each lane w.p. noise_std). Seeded → reproducible.
  - `incident=(inter_id, t_start, t_end)`: while `t_start <= inner_step < t_end`, intercept `set_tl_phase(inter_id, *)` → force the intersection's all-red/blocking phase (needs all-red phase passed in). Delegate a step counter off inner `.step()`.
  - `noise_std=0 and incident=None` → passthrough identical to inner (regression guard).

- [ ] **Step 1 — failing test:**
```python
# tests/sim/test_perturbations.py
from tests.conftest import FakeEngine
from traffic_rl.sim.perturbations import PerturbedEngine

def test_passthrough_when_off():
    inner = FakeEngine(vehicle_counts={"l":10}, waiting_counts={"l":4})
    pe = PerturbedEngine(inner, noise_std=0.0)
    assert pe.lane_vehicle_counts() == {"l":10}
    assert pe.lane_waiting_counts() == {"l":4}

def test_noise_is_seeded_and_reproducible():
    a = PerturbedEngine(FakeEngine(waiting_counts={"l":20}), noise_std=0.3, seed=1)
    b = PerturbedEngine(FakeEngine(waiting_counts={"l":20}), noise_std=0.3, seed=1)
    assert a.lane_waiting_counts() == b.lane_waiting_counts()   # deterministic

def test_noise_perturbs_counts():
    pe = PerturbedEngine(FakeEngine(waiting_counts={"l":20}), noise_std=0.8, seed=2)
    vals = [pe.lane_waiting_counts()["l"] for _ in range(5)]
    assert any(v != 20 for v in vals) and all(v >= 0 for v in vals)
```
- [ ] **Step 2 — fail. Step 3 — implement** (own `np.random.RandomState(seed)`; never negative). **Step 4 — pass. Step 5 — commit** `feat(sim): PerturbedEngine (sensor noise + incident)`.

### Task C3.2: robustness runner + sweeps
**Files:** `scripts/run_robustness.py`, `scripts/exp_robustness.sh`.
- [ ] `run_robustness.py <scenario> <mode>`: mode ∈ {noise,incident,shift}. For noise: sweep `noise_std ∈ {0,0.1,0.2,0.4,0.8}`, wrap engine in `PerturbedEngine`, eval all 4 controllers, write `results/<scen>/robustness/<mode>.json` (rows per level). For shift: load `dqn_<scenA>.npz`, eval on scenB flow. For incident: single run with `incident=(pick_arterial_id, T0, T1)`, compare recovery (queue_series post-T1).
- [ ] Run in container for `haichau_rush` (headline) + `haichau_peak`: noise + shift first (eval-only), incident last.
- [ ] Host plot: `plot_robustness_degradation` (x=noise_std, y=wait_hours per controller) — expect Fixed-Time flat, MP+DQN rising, **DQN rising slower than MP = the win**.
- [ ] Add a "Robustness" section to Chapter 4 with the degradation figure + incident recovery. Commit `results(ch4): robustness (noise/incident/shift)`.

---

## C4 — Neighbor-coordinated state (beat-MP attempt)

### Task C4.1: upstream_neighbors on roadnet (host, TDD)
**Files:** Modify `src/traffic_rl/network/roadnet.py`; Test `tests/network/test_roadnet_neighbors.py`.
**Interfaces — Produces:** `RoadNet.upstream_neighbors(inter_id) -> List[str]` — signalized intersections whose outgoing roads feed `inter_id`'s incoming roads (via existing road start/end + `_next`/`_road_by_id`). Empty list if none.
- [ ] Test on the existing small roadnet fixture (follow `tests/network/test_roadnet.py` construction): a 2-intersection line → downstream node's `upstream_neighbors` == [upstream node]; boundary node → `[]`.
- [ ] Implement, test pass, commit `feat(net): roadnet.upstream_neighbors`.

### Task C4.2: neighbor state_mode (host, TDD)
**Files:** Modify `src/traffic_rl/sim/encoder.py`; Test `tests/sim/test_encoder_neighbor.py`.
**Interfaces:** `state_mode="neighbor"` → `obs_dim = max_in + max_out + max_green + 2` (basic + [mean neighbor incoming occupancy, mean neighbor incoming pressure]). Encoder precomputes per-agent neighbor incoming/outgoing lanes from `roadnet.upstream_neighbors`. `encode(...)` appends the two pooled features (0 if no neighbors).
- [ ] Test: obs_dim == basic+2; agent with a known neighbor gets non-zero neighbor feature when that neighbor's lanes have counts; isolated agent → 0.
- [ ] Implement, test pass, commit `feat(state): neighbor-coordinated observation (CoLight-lite)`.

### Task C4.3: train + eval neighbor DQN
**Files:** `scripts/exp_neighbor.sh` (mirror `scripts/exp_rush.sh` with `STATE_MODE=neighbor`, `EXP_TAG=neighbor`).
- [ ] Container: train `STATE_MODE=neighbor EXP_TAG=neighbor ... train_dqn.py <scen>` then eval via `run_experiment_eval.py` (matches the ATS eval path; confirm it passes state_mode). Scenarios: `haichau_rush`, `haichau_peak`, `haichau` (where MP-gap matters).
- [ ] Compare vs MP. Add a `neighbor` row to Chapter 4 ablation Table (Section 4.3). **Report honestly whether it closes the gap** (either outcome is a result).
- [ ] Commit `results(ch4): neighbor-coordinated DQN vs Max-Pressure`.

---

## Cross-cutting

### Task X.1: frozen-baseline regression guard
- [ ] Before any container run, snapshot: `git stash` not needed — instead assert new scripts write ONLY to new paths. Add `tests/test_frozen_paths.py` that greps the new scripts for writes to `results/references` or canonical `comparison.json` and fails if found (static check).
- [ ] After all runs, `git status results/references/` must be clean.

### Task X.2: host test suite stays green
- [ ] `make test` (host, `-m 'not docker'`) passes after every code task; the existing 66 tests must not regress.

---

## Self-Review notes
- **Spec coverage:** C1↔§3.C1 (tiers), C2↔§3.C2, C3↔§3.C3 (noise/incident/shift), C4↔§3.C4 (mean-pool, no attention). Robustness incident has the spec's fallback (demand-shock) if forcing all-red proves infeasible — add as C3.2 alt if the incident run errors.
- **Isolation:** all outputs to new paths; X.1 guards frozen baselines.
- **Sequence:** C1 → C2 → C3 → C4 (compute cost + Ch4-gating order).
- **Compute owner:** Claude runs all `make cf-run` jobs (Colima up; cityflow OK verified).
