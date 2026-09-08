# Hai Chau Neighbor-Aware DDQN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and train a phase-centric, neighbor-aware shared DDQN across all 53 Hai Chau signals using balanced normal/AM/PM cases and validation-constrained checkpoint selection.

**Architecture:** Encode every candidate phase with movement-aligned local and neighbor features, then score valid phases with one shared NumPy Q network. The environment enforces signal constraints and measures switch costs. A balanced multi-case trainer samples the versioned train split and selects checkpoints by worst-case validation regret against freshly evaluated tuned Fixed-Time.

**Tech Stack:** Python 3.6-compatible NumPy model/runtime, CityFlow, pytest fake engines, JSON/NPZ checkpoint bundles.

**Spec:** `docs/superpowers/specs/2026-09-08-haichau-network-marl-design.md`

## Global Constraints

- Foundation plan `2026-09-08-haichau-data-runtime-implementation.md` must pass first.
- The policy controls all 53 signals in every episode.
- Normal, AM peak and PM peak appear in both training and validation.
- Checkpoint evaluation uses resolved config from its own bundle.
- Existing `SharedDQN` remains as an ablation; new behavior uses `PhaseScoringDDQN`.
- All runtime code imported in CityFlow stays Python 3.6 compatible.
- No test case or test metric influences hyperparameter or checkpoint selection.

---

## File Structure

- `src/traffic_rl/sim/phase_encoder.py`: phase-aligned local/neighbor features and action masks.
- `src/traffic_rl/sim/multi_agent_env.py`: constraint state and richer metrics.
- `src/traffic_rl/agents/phase_ddqn.py`: scalar phase scorer, target net and replay buffer.
- `src/traffic_rl/train/case_sampler.py`: balanced manifest case sampling.
- `src/traffic_rl/train/network_trainer.py`: multi-case learning and checkpoint bundles.
- `src/traffic_rl/eval/checkpoint_selection.py`: validation regret and acceptance gates.
- `scripts/train_haichau_network.py`: smoke/pilot/final training entry point.

### Task 1: Phase-centric neighbor encoder

**Files:**
- Create: `src/traffic_rl/sim/phase_encoder.py`
- Modify: `src/traffic_rl/network/roadnet.py`
- Test: `tests/sim/test_phase_encoder.py`

**Interfaces:**
- Produces: `RoadNet.downstream_neighbors(inter_id) -> list[str]`.
- Produces: `PhaseFeatureEncoder(roadnet, count_norm, capacity_norm)` with `encode_all(inter_id, vehicle_counts, waiting_counts, green_index, elapsed_green, time_since_service) -> (features, mask)`.
- `features` has shape `(max_green, 12)` and `mask` has shape `(max_green,)`.

- [ ] **Step 1: Write failing semantic-alignment tests**

```python
def test_phase_features_follow_served_movements_not_lane_position(two_geometry_roadnets):
    ea, eb = [PhaseFeatureEncoder(r, 20.0, 40.0) for r in two_geometry_roadnets]
    fa, ma = ea.encode_all("A", counts_a, waits_a, 0, 20, service_a)
    fb, mb = eb.encode_all("B", counts_b, waits_b, 0, 20, service_b)
    assert np.allclose(fa[0, :6], fb[0, :6])
    assert ma.tolist() == mb.tolist()

def test_neighbor_features_include_upstream_and_downstream(signal_chain_roadnet):
    enc = PhaseFeatureEncoder(signal_chain_roadnet, 20.0, 40.0)
    features, _ = enc.encode_all("middle", counts, waits, 0, 30, service)
    assert features[0, 8] > 0
    assert features[0, 9] > 0
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/sim/test_phase_encoder.py -v`

Expected: FAIL because `PhaseFeatureEncoder` is missing.

- [ ] **Step 3: Implement the 12-feature schema**

For each green phase compute, in fixed order:

```python
FEATURES = (
    "incoming_queue_mean", "incoming_queue_max", "incoming_running_mean",
    "outgoing_queue_mean", "outgoing_remaining_capacity_mean", "pressure",
    "is_current_phase", "elapsed_green", "upstream_queue_mean",
    "downstream_queue_mean", "time_since_service", "movement_count",
)
```

Normalize count/capacity/time features by the contract constants and set padded phase rows to zero with mask `False`.

- [ ] **Step 4: Verify GREEN and existing encoder regression**

Run: `PYTHONPATH=src pytest tests/sim/test_phase_encoder.py tests/sim/test_encoder.py tests/network/test_roadnet_phases.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/phase_encoder.py src/traffic_rl/network/roadnet.py tests/sim/test_phase_encoder.py
git commit -m "feat: encode movement-aligned neighbor phase features"
```

### Task 2: Signal constraints, switching cost and service timers

**Files:**
- Modify: `src/traffic_rl/sim/multi_agent_env.py`
- Modify: `src/traffic_rl/sim/intersection.py`
- Test: `tests/sim/test_multi_agent_constraints.py`

**Interfaces:**
- `MultiAgentTrafficEnv(..., maximum_red=180, switch_penalty=0.05, encoder=None)`.
- `info` adds `phase_switches`, `intergreen_vehicle_seconds`, `max_red_seconds`, and `per_agent_queue`.
- `action_masks()` blocks switching before minimum green and forces an overdue phase when maximum red is reached.

- [ ] **Step 1: Write failing behavior tests**

```python
def test_hold_action_has_no_clearance_or_switch_penalty(constrained_env):
    constrained_env.reset()
    _, rewards, _, info = constrained_env.step({"A": 0})
    assert info["phase_switches"] == 0
    assert info["intergreen_vehicle_seconds"] == 0

def test_maximum_red_mask_forces_overdue_phase(constrained_env):
    constrained_env._time_since_service["A"] = [0, 181]
    mask = constrained_env.action_masks()["A"]
    assert mask.tolist() == [False, True]
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/sim/test_multi_agent_constraints.py -v`

- [ ] **Step 3: Implement timers and reward accounting**

Increment elapsed green and time-since-service during every engine step. Reset service timers for movements served by the active phase. Apply the switch penalty once per accepted switch; do not alter evaluation queue metrics. Count actual intergreen seconds, not requested actions.

- [ ] **Step 4: Verify environment suites**

Run: `PYTHONPATH=src pytest tests/sim/test_multi_agent_constraints.py tests/sim/test_multi_agent_env.py tests/sim/test_intersection.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/multi_agent_env.py src/traffic_rl/sim/intersection.py tests/sim/test_multi_agent_constraints.py
git commit -m "feat: enforce network signal timing constraints"
```

### Task 3: Phase-scoring Double DQN and checkpoint contract

**Files:**
- Create: `src/traffic_rl/agents/phase_ddqn.py`
- Test: `tests/agents/test_phase_ddqn.py`

**Interfaces:**
- `PhaseScoringDDQN(feature_dim, hidden, lr, seed, grad_clip, huber_delta)`.
- `q_values(features, mask) -> ndarray[batch, max_green]`.
- `greedy_action(features, mask) -> int`.
- `train_step(features, actions, rewards, next_features, dones, next_masks, gamma) -> float`.
- `save_bundle(directory, contract)` and `load_bundle(directory, expected_contract)`.

- [ ] **Step 1: Write failing action, DDQN and contract tests**

```python
def test_greedy_action_never_selects_padding():
    net = PhaseScoringDDQN(12, hidden=16, lr=1e-3, seed=1)
    features = np.zeros((4, 12), np.float32)
    assert net.greedy_action(features, np.array([1, 1, 0, 0], bool)) in (0, 1)

def test_loader_rejects_count_norm_drift(tmp_path):
    net.save_bundle(tmp_path, {"obs_schema_version": 2, "count_norm": 5.0})
    with pytest.raises(ValueError, match="count_norm"):
        PhaseScoringDDQN.load_bundle(
            tmp_path, {"obs_schema_version": 2, "count_norm": 40.0})
```

Add a numeric test proving online argmax plus target evaluation implements Double DQN.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/agents/test_phase_ddqn.py -v`

- [ ] **Step 3: Implement shared scalar scoring network**

Flatten `(batch, phases, features)` to phase rows, score each with a two-hidden-layer MLP, reshape to `(batch, phases)`, apply masks, and update only the selected action. Store weights, target weights and exact `contract.json`; fail on any contract-field mismatch.

- [ ] **Step 4: Verify GREEN and gradient stability**

Run: `PYTHONPATH=src pytest tests/agents/test_phase_ddqn.py tests/agents/test_dqn.py -v`

Expected: finite loss after 100 synthetic updates; masks and checkpoint drift tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/phase_ddqn.py tests/agents/test_phase_ddqn.py
git commit -m "feat: add contract-bound phase-scoring DDQN"
```

### Task 4: Balanced multi-case sampler and replay

**Files:**
- Create: `src/traffic_rl/train/case_sampler.py`
- Create: `src/traffic_rl/train/network_replay.py`
- Test: `tests/train/test_case_sampler.py`
- Test: `tests/train/test_network_replay.py`

**Interfaces:**
- `BalancedCaseSampler(cases, seed).next_case() -> dict`.
- `NetworkReplayBuffer(capacity, max_green, feature_dim, seed)` stores `case_regime` with each transition.
- `coverage() -> dict[str, int]` returns stored transition counts by regime.

- [ ] **Step 1: Write failing balance and replay tests**

```python
def test_sampler_balances_regimes_before_repeating(cases):
    sampler = BalancedCaseSampler(cases, seed=7)
    seen = [sampler.next_case()["scenario"] for _ in range(3)]
    assert set(seen) == {"normal", "am_peak", "pm_peak"}

def test_replay_reports_regime_coverage():
    replay.add(features, 0, -1, next_features, False, mask, "normal")
    replay.add(features, 1, -2, next_features, False, mask, "pm_peak")
    assert replay.coverage() == {"normal": 1, "pm_peak": 1}
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/train/test_case_sampler.py tests/train/test_network_replay.py -v`

- [ ] **Step 3: Implement deterministic stratified cycling and array storage**

Shuffle cases independently inside each regime, cycle regimes in seeded shuffled blocks of three, and reshuffle a regime only after exhausting its cases. Store numeric regime IDs in the buffer and map them back in `coverage()`.

- [ ] **Step 4: Verify and commit**

Run: `PYTHONPATH=src pytest tests/train/test_case_sampler.py tests/train/test_network_replay.py -v`

```bash
git add src/traffic_rl/train/case_sampler.py src/traffic_rl/train/network_replay.py tests/train/test_case_sampler.py tests/train/test_network_replay.py
git commit -m "feat: balance multi-regime network training cases"
```

### Task 5: Validation regret and non-inferiority selection

**Files:**
- Create: `src/traffic_rl/eval/checkpoint_selection.py`
- Test: `tests/eval/test_checkpoint_selection.py`

**Interfaces:**
- `relative_regret(candidate, baseline) -> float`.
- `score_validation(rows) -> dict` with `worst_regret`, `mean_regret`, `normal_regret`, `eligible`.
- `choose_checkpoint(evaluations) -> str`.

- [ ] **Step 1: Write failing gate tests**

```python
def test_checkpoint_that_loses_normal_is_ineligible():
    rows = matched_rows(normal=(105, 100), am=(80, 100), pm=(70, 100))
    assert score_validation(rows)["eligible"] is False

def test_selection_minimizes_worst_regret_then_mean():
    evaluations = {"a": score(-0.01, -0.10), "b": score(-0.01, -0.20)}
    assert choose_checkpoint(evaluations) == "b"
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/eval/test_checkpoint_selection.py -v`

- [ ] **Step 3: Implement normalized matched-case scoring**

Regret is `(candidate_queue - baseline_queue) / baseline_queue`. Aggregate each scenario across validation demand seeds. Eligibility requires `normal_regret <= 0` and completion degradation no worse than 0.02. Rank eligible checkpoints by worst scenario regret, then mean regret, then earlier training step.

- [ ] **Step 4: Verify and commit**

Run: `PYTHONPATH=src pytest tests/eval/test_checkpoint_selection.py -v`

```bash
git add src/traffic_rl/eval/checkpoint_selection.py tests/eval/test_checkpoint_selection.py
git commit -m "feat: select checkpoints by multi-regime regret"
```

### Task 6: Multi-case trainer and 53-node training smoke

**Files:**
- Create: `src/traffic_rl/train/network_trainer.py`
- Create: `scripts/train_haichau_network.py`
- Create: `configs/haichau_training_v2.yaml`
- Test: `tests/train/test_network_trainer.py`

**Interfaces:**
- `train_network(env_factory, manifest, config, output_dir) -> dict`.
- CLI modes: `--mode smoke`, `--mode pilot`, `--mode final`, and required `--learning-seed`.

- [ ] **Step 1: Write a failing fake multi-case training test**

```python
def test_training_visits_all_regimes_and_saves_resolved_contract(fake_factory, manifest):
    summary = train_network(fake_factory, manifest, smoke_config, output)
    assert set(summary["episode_regimes"]) == {"normal", "am_peak", "pm_peak"}
    contract = json.loads((output / "checkpoint" / "contract.json").read_text())
    assert contract["count_norm"] == 20.0
    assert contract["network_sha256"] == manifest["network"]["sha256"]
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/train/test_network_trainer.py -v`

- [ ] **Step 3: Implement trainer with fresh validation baselines**

At every evaluation interval, run the candidate and tuned Fixed-Time on every validation case from fresh environments. Persist `resolved-config.json`, `train-log.json`, `validation.json`, replay coverage and checkpoint contract. Never read controller rows from legacy results.

- [ ] **Step 4: Add explicit tier configuration**

```yaml
schema_version: 2
model: {feature_dim: 12, hidden: 128, lr: 0.0003, gamma: 0.99, n_step: 3}
optimizer: {batch_size: 128, buffer_capacity: 200000, train_start: 2000, target_sync: 500, grad_clip: 10.0, huber_delta: 1.0}
exploration: {epsilon_start: 1.0, epsilon_end: 0.05, epsilon_decay_decisions: 10000}
reward: {queue_weight: 1.0, downstream_block_weight: 0.2, switch_penalty: 0.05}
tiers:
  smoke: {episodes: 3, horizon_seconds: 120, eval_every: 3}
  pilot: {episodes: 12, horizon_seconds: 3600, eval_every: 4}
  final: {episodes: 80, horizon_seconds: 3600, eval_every: 5}
```

- [ ] **Step 5: Run unit tests and real 53-node smoke**

Run:

```bash
PYTHONPATH=src pytest tests/train/test_network_trainer.py tests/train/test_case_sampler.py tests/train/test_network_replay.py tests/agents/test_phase_ddqn.py -v
make haichau-train-smoke LEARNING_SEED=11
```

Expected: 3 episodes cover all regimes; every episode reports 53 agents; checkpoint bundle reloads and completes a 120-second greedy episode.

- [ ] **Step 6: Run one full-horizon pilot and record budget**

Run: `make haichau-train-pilot LEARNING_SEED=11`

Record simulated seconds/second, updates/second, peak RSS, validation wall time and projected five-seed campaign duration in `results/haichau_network_v2/profiling/pilot-seed11.json`.

- [ ] **Step 7: Commit**

```bash
git add src/traffic_rl/train/network_trainer.py scripts/train_haichau_network.py configs/haichau_training_v2.yaml tests/train/test_network_trainer.py results/haichau_network_v2/profiling/pilot-seed11.json
git commit -m "feat: train neighbor DDQN across Hai Chau cases"
```

## Model Completion Gate

Do not launch final test evaluation until:

- all phase/model/constraint/trainer tests pass;
- smoke trains across 53 nodes and all three regimes;
- pilot completes full horizon with reloadable checkpoint;
- validation baselines are freshly executed;
- at least one frozen candidate satisfies normal validation non-inferiority;
- the final configuration and checkpoint-selection rule are committed before test hashes are opened.
