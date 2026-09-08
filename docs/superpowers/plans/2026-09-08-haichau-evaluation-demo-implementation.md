# Hai Chau Evaluation, Thesis, and Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the frozen five-seed Hai Chau campaign, compute honest matched-case statistics, regenerate thesis evidence, and deliver an offline 53-node defense demo with end-to-end verification.

**Architecture:** A campaign runner expands the committed test manifest into fresh controller runs and records immutable run bundles. Statistical code aggregates at the correct learning-seed unit and evaluates predeclared acceptance gates. The same verified summaries feed figures, LaTeX tables, replay exports and the offline browser demo.

**Tech Stack:** CityFlow pinned Docker runtime, Python/NumPy statistics, matplotlib, LaTeX, vanilla JavaScript/Canvas replay, Node test runner, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-haichau-network-marl-design.md`

## Global Constraints

- Data/runtime and model completion gates must pass before final campaign.
- Test cases and acceptance rules are immutable once final training begins.
- Every controller is run fresh on matched network/demand/simulator cases.
- Statistical independence is learning seed for RL and demand seed for deterministic baselines.
- Travel-time claims always include completion and pending/active accounting.
- Demo is an illustration; aggregate frozen runs support conclusions.
- Existing one-junction empirical results remain separate from 53-node synthetic-demand results.

---

## File Structure

- `src/traffic_rl/eval/network_metrics.py`: per-step and terminal metric contract.
- `src/traffic_rl/eval/network_campaign.py`: fresh matched controller execution.
- `src/traffic_rl/eval/network_statistics.py`: hierarchical aggregation and gates.
- `scripts/run_haichau_campaign.py`: resume-safe campaign CLI.
- `scripts/summarize_haichau_campaign.py`: frozen CSV/JSON/figures.
- `scripts/export_haichau_replays.py`: network replay bundle export.
- `scripts/verify_haichau_thesis.py`: final project verifier.
- `frontend/haichau_network_demo.*`: offline 53-node viewer.
- `results/haichau_network_v2/final/`: immutable final evidence.

### Task 1: Network metric contract without survivorship bias

**Files:**
- Create: `src/traffic_rl/eval/network_metrics.py`
- Modify: `src/traffic_rl/eval/runner.py`
- Modify: `src/traffic_rl/sim/engine.py`
- Test: `tests/eval/test_network_metrics.py`

**Interfaces:**
- `NetworkMetricAccumulator(step_seconds).observe(snapshot)` and `.finalize() -> dict`.
- Snapshot fields: `queued`, `running`, `departed`, `arrived`, `travel_times`, `per_node_queue`, `spillback_lanes`, `phase_switches`, `intergreen_seconds`, `max_red_seconds`.

- [ ] **Step 1: Write failing integral and censoring tests**

```python
def test_queue_integral_uses_every_simulation_step():
    m = NetworkMetricAccumulator(step_seconds=1)
    m.observe(snapshot(queued=2)); m.observe(snapshot(queued=2))
    m.observe(snapshot(queued=0))
    assert m.finalize()["queue_integral_vehicle_seconds"] == 4

def test_travel_time_is_reported_with_completion():
    m.observe(snapshot(departed=10, arrived=5, travel_times=[20, 30, 40, 50, 60]))
    result = m.finalize()
    assert result["completion_rate"] == 0.5
    assert result["travel_time_completed_mean"] == 40
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py -v`

- [ ] **Step 3: Implement engine snapshot support and accumulator**

Expose counts without changing simulator state. Calculate queue integral per engine step, per-node maximum queue, spillback duration, switches, lost time, mean/median/p95 completed travel time, departed/arrived/running and completion.

- [ ] **Step 4: Verify regression and commit**

Run: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py tests/eval/test_runner.py -v`

```bash
git add src/traffic_rl/eval/network_metrics.py src/traffic_rl/eval/runner.py src/traffic_rl/sim/engine.py tests/eval/test_network_metrics.py
git commit -m "feat: measure complete Hai Chau network outcomes"
```

### Task 2: Resume-safe fresh matched campaign runner

**Files:**
- Create: `src/traffic_rl/eval/network_campaign.py`
- Create: `scripts/run_haichau_campaign.py`
- Test: `tests/eval/test_network_campaign.py`

**Interfaces:**
- `expand_runs(manifest, learning_seeds, controller_ids) -> list[dict]`.
- `run_pending(campaign_dir, executor) -> dict`.
- Controllers: `tuned_fixed`, `max_pressure`, `hysteretic_mp`, `shared_ddqn_legacy`, `neighbor_phase_ddqn`.

- [ ] **Step 1: Write failing run-expansion and resume tests**

```python
def test_deterministic_baseline_is_not_multiplied_by_learning_seed(manifest):
    runs = expand_runs(manifest, [11, 12, 13, 14, 15], ["tuned_fixed"])
    assert len(runs) == len(test_cases(manifest))

def test_resume_rechecks_hash_before_skipping(tmp_path, complete_run):
    complete_run.metrics_path.write_text("corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_pending(tmp_path, fake_executor)
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/eval/test_network_campaign.py -v`

- [ ] **Step 3: Implement immutable run directories**

Write each run to `final/runs/<run_id>/` with `status.json`, `resolved-config.json`, `metrics.json`, stdout/stderr and hashes. Write status `complete` only after horizon, controller, case and artifact verification. A crashed run may resume only from scratch inside its own directory.

- [ ] **Step 4: Verify and commit**

Run: `PYTHONPATH=src pytest tests/eval/test_network_campaign.py -v`

```bash
git add src/traffic_rl/eval/network_campaign.py scripts/run_haichau_campaign.py tests/eval/test_network_campaign.py
git commit -m "feat: run fresh matched Hai Chau evaluation campaign"
```

### Task 3: Hierarchical statistics and acceptance gates

**Files:**
- Create: `src/traffic_rl/eval/network_statistics.py`
- Create: `scripts/summarize_haichau_campaign.py`
- Test: `tests/eval/test_network_statistics.py`

**Interfaces:**
- `paired_bootstrap(differences, seed=20260908, samples=10000) -> (low, high)`.
- `aggregate_campaign(runs) -> dict`.
- `evaluate_acceptance(summary) -> dict`.

- [ ] **Step 1: Write failing statistical-unit tests**

```python
def test_rl_aggregation_averages_demands_inside_learning_seed():
    summary = aggregate_campaign(two_learning_seeds_with_three_demands_each())
    assert summary["neighbor_phase_ddqn"]["normal"]["n_independent"] == 2

def test_peak_gate_requires_ci_below_zero():
    result = evaluate_acceptance(summary_with_pm_difference_ci(-20, -5))
    assert result["peak_improvement"] is True
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py -v`

- [ ] **Step 3: Implement deterministic paired bootstrap and gates**

Use matched queue differences. For RL, average demand/simulator realizations inside each learning seed before bootstrap. Report raw values, mean, median, sample SD, CI and relative effect. Implement normal point estimate `<= 0`, normal upper CI CI `<= +0.05 × baseline mean`, peak CI `< 0`, and completion degradation `<= 0.02`.

- [ ] **Step 4: Verify and commit**

Run: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py tests/eval/test_multiseed.py -v`

```bash
git add src/traffic_rl/eval/network_statistics.py scripts/summarize_haichau_campaign.py tests/eval/test_network_statistics.py
git commit -m "feat: summarize Hai Chau campaign with paired inference"
```

### Task 4: Freeze training and execute the five-seed campaign

**Files:**
- Create: `results/haichau_network_v2/final/frozen-protocol.json`
- Create: generated checkpoints under `results/haichau_network_v2/final/checkpoints/`
- Create: generated runs under `results/haichau_network_v2/final/runs/`
- Create: generated `summary.json` and `summary.csv`.

**Interfaces:**
- Consumes: all prior tasks and learning seeds `[11, 12, 13, 14, 15]`.
- Produces: immutable final campaign evidence.

- [ ] **Step 1: Freeze protocol before test execution**

Copy exact model config, selected hyperparameters, validation evidence, case manifest hashes, acceptance rules, code commit and runtime digest into `frozen-protocol.json`. Verify no test metric is present in checkpoint selection inputs.

- [ ] **Step 2: Train five final learning seeds**

Run:

```bash
for seed in 11 12 13 14 15; do
  make haichau-train-final LEARNING_SEED="$seed"
done
```

Every output must pass checkpoint-contract reload and validation eligibility before continuing.

- [ ] **Step 3: Run all fresh test evaluations**

Run: `make haichau-evaluate-final`

Expected: every expanded run is complete; no controller row comes from `results/haichau*` legacy directories.

- [ ] **Step 4: Summarize without changing frozen inputs**

Run: `PYTHONPATH=src python3 scripts/summarize_haichau_campaign.py`

Expected: summary contains normal/AM/PM raw values and CI, completion, runtime, acceptance gate outcomes and negative results.

- [ ] **Step 5: Verify campaign completeness and commit evidence**

Run: `PYTHONPATH=src python3 scripts/run_haichau_campaign.py --verify-only`

```bash
git add results/haichau_network_v2/final
git commit -m "results: freeze five-seed Hai Chau network campaign"
```

### Task 5: Regenerate thesis tables, figures and claims

**Files:**
- Create: `src/traffic_rl/report/haichau_network.py`
- Create: `scripts/build_haichau_thesis_artifacts.py`
- Modify: `paper/thesis_danang.tex`
- Modify: `paper/references.bib`
- Test: `tests/report/test_haichau_network.py`

**Interfaces:**
- `build_tables(summary) -> dict[str, str]`.
- `validate_claims(tex, summary) -> list[str]` returns unsupported claim errors.

- [ ] **Step 1: Write failing provenance and claim tests**

```python
def test_network_table_labels_demand_synthetic(summary):
    table = build_tables(summary)["network_results"]
    assert "synthetic" in table.lower()
    assert "53" in table

def test_claim_validator_rejects_citywide_observed_claim(summary):
    errors = validate_claims("53 observed intersections", summary)
    assert errors
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/report/test_haichau_network.py -v`

- [ ] **Step 3: Generate result tables and plots from summary only**

Create controller/scenario table, paired difference plot, completion plot, per-node queue map, training curves, demand robustness and ablation. Every figure sidecar records summary hash and generation command.

- [ ] **Step 4: Update thesis**

Chapter 3 describes 53-agent architecture, phase features, split and gates. Chapter 4 reports the actual result including failures. Limitations distinguish one-junction observed evidence from network synthetic evidence. Add PressLight, CoLight, AttendLight, Efficient Pressure and task-underspecification references.

- [ ] **Step 5: Build and visually inspect PDF**

Run:

```bash
PYTHONPATH=src pytest tests/report/test_haichau_network.py -v
PYTHONPATH=src python3 scripts/build_haichau_thesis_artifacts.py
cd paper && latexmk -pdf -interaction=nonstopmode thesis_danang.tex
```

Render the changed result pages to PNG and inspect clipping, table overflow, legends and citation rendering.

- [ ] **Step 6: Commit**

```bash
git add src/traffic_rl/report/haichau_network.py scripts/build_haichau_thesis_artifacts.py tests/report/test_haichau_network.py paper
git commit -m "docs: report verified Hai Chau network study"
```

### Task 6: Offline 53-node synchronized replay demo

**Files:**
- Create: `frontend/haichau_network_demo.html`
- Create: `frontend/haichau_network_demo.js`
- Create: `frontend/haichau_network_demo_core.js`
- Create: `frontend/haichau_network_demo.css`
- Create: `scripts/export_haichau_replays.py`
- Test: `tests/replay_ab/haichau_network_demo_core.test.cjs`
- Test: `tests/report/test_haichau_replay_export.py`

**Interfaces:**
- Exporter writes bounded-size network, replay and aggregate JSON with hashes.
- Viewer supports scenario/controller selection, synchronized time, overview heat map, node selection and local neighbor panel.

- [ ] **Step 1: Write failing replay/export tests**

```javascript
test("node color increases monotonically with queue", () => {
  assert.ok(core.queueColor(50) !== core.queueColor(0));
});

test("frame lookup is synchronized at requested time", () => {
  assert.equal(core.frameIndexAt([{t:5},{t:10}], 9), 0);
});
```

Python export test asserts representative replay metrics reproduce the frozen run exactly and every path/hash exists.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/replay_ab/haichau_network_demo_core.test.cjs && PYTHONPATH=src pytest tests/report/test_haichau_replay_export.py -v`

- [ ] **Step 3: Implement bounded replay export and viewer**

Sample frames every five simulation seconds; store signal state, per-node queue and visible vehicle positions. Keep aggregate values in a separate signed summary. Add labels stating lower queue is better and demand is synthetic network-scale evidence.

- [ ] **Step 4: Add fallbacks and verify offline behavior**

Build MP4 walkthrough, result PDF and overview PNG. Serve locally, disable network, exercise play/pause/seek/scenario switch/node zoom in Chrome and confirm console has no warning/error.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
npm run test:replay
PYTHONPATH=src pytest tests/report/test_haichau_replay_export.py -v
```

```bash
git add frontend/haichau_network_demo.* scripts/export_haichau_replays.py tests/replay_ab/haichau_network_demo_core.test.cjs tests/report/test_haichau_replay_export.py results/haichau_network_v2/demo
git commit -m "demo: add offline 53-node Hai Chau comparison"
```

### Task 7: Project-level end-to-end thesis verifier

**Files:**
- Create: `scripts/verify_haichau_thesis.py`
- Create: `tests/scripts/test_verify_haichau_thesis.py`
- Create: generated `results/haichau_network_v2/verification/final-report.json`
- Modify: `README.md`
- Modify: `docs/defense/demo-runbook.md`

**Interfaces:**
- CLI exits zero only when foundation, model, campaign, paper and demo gates all pass.

- [ ] **Step 1: Write a failing completion-audit test**

```python
def test_final_verifier_lists_missing_requirements(tmp_path):
    report = verify_project(tmp_path)
    assert report["complete"] is False
    assert "five_learning_seeds" in report["failed_gates"]
    assert "offline_demo" in report["failed_gates"]
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_thesis.py -v`

- [ ] **Step 3: Implement requirement-by-requirement audit**

Check exact network and case counts, hashes, five learning seeds, fresh baseline provenance, scenario coverage, horizon completeness, statistical-unit metadata, acceptance results, thesis summary hash, PDF existence, replay hashes, fallback files and no remote frontend dependencies. Emit evidence path and status for every gate.

- [ ] **Step 4: Run complete verification**

Run:

```bash
make test
make cf-test
npm run test:replay
PYTHONPATH=src python3 scripts/verify_haichau_thesis.py
```

Expected: final report has `"complete": true` and no failed gates.

- [ ] **Step 5: Repeat the release path from a clean checkout**

Clone current HEAD to a temporary directory, obtain only documented tracked/release inputs, run the project verifier, start the offline demo and open the generated PDF. Record commit, commands, tool versions, hashes and wall time in `final-report.json`.

- [ ] **Step 6: Update operator documentation and commit**

Document exact reproduce, verify and demo commands plus fallback order.

```bash
git add scripts/verify_haichau_thesis.py tests/scripts/test_verify_haichau_thesis.py results/haichau_network_v2/verification/final-report.json README.md docs/defense/demo-runbook.md
git commit -m "verify: add end-to-end Hai Chau thesis release gate"
```

## Thesis Completion Gate

The work is complete only when the final verifier proves:

- 53-node tracked network and 30-case split are hash-valid;
- five final learning seeds and all matched controller runs are complete;
- normal non-inferiority and peak results are reported exactly as observed;
- all tables/figures/PDF derive from the frozen summary;
- offline network demo and fallbacks work;
- the same release path succeeds from a clean checkout.
