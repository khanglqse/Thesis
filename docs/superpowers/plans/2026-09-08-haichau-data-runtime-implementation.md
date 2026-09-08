# Hai Chau Data and Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a versioned, checksum-verified 53-signal Hai Chau CityFlow network, multi-regime demand family, split manifest, and pinned runtime that reproduce from a clean checkout.

**Architecture:** Copy the canonical OSM-derived arterial roadnet into a tracked dataset package, validate its graph and phase contract, then generate seeded normal/AM/PM CityFlow flows from boundary-to-boundary routes that cross controlled signals. A resolved experiment manifest binds network, flow, split, simulator and preprocessing hashes; a fail-closed verifier checks the complete foundation.

**Tech Stack:** Python 3.13 host tooling, CityFlow Python 3.6 runtime in a digest-pinned Docker image, NumPy, PyYAML, pytest, SHA-256 manifests.

**Spec:** `docs/superpowers/specs/2026-09-08-haichau-network-marl-design.md`

## Global Constraints

- Canonical scope is the Hai Chau arterial network with exactly 53 controllable signals.
- Network-scale demand is labeled `synthetic_osm_haichau_constrained_by_danang_profiles`.
- Train, validation and test demand seeds are disjoint.
- Every generated artifact is bound to network, generator-config and source hashes.
- Existing `results/haichau*` remains immutable legacy evidence.
- No command may depend on ignored `data/` files after the tracked dataset is created.
- CityFlow image digest is `sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32` until a new image is deliberately built and recorded.

---

## File Structure

- `datasets/haichau_network_v2/roadnet.json`: tracked canonical CityFlow network.
- `datasets/haichau_network_v2/provenance.json`: source, conversion and license metadata.
- `configs/haichau_network_v2.yaml`: generator, split, simulator and preprocessing inputs.
- `src/traffic_rl/research/artifacts.py`: hashing and canonical manifest helpers.
- `src/traffic_rl/network/haichau_dataset.py`: network audit and demand-route generation.
- `scripts/prepare_haichau_network_v2.py`: deterministic dataset/case builder.
- `scripts/verify_haichau_foundation.py`: fail-closed clean-foundation verification.
- `docker/cityflow-research/Dockerfile`: pinned runtime recipe.
- `results/haichau_network_v2/experiment-manifest.json`: generated case registry.

### Task 1: Artifact hashing and manifest contract

**Files:**
- Create: `src/traffic_rl/research/__init__.py`
- Create: `src/traffic_rl/research/artifacts.py`
- Test: `tests/research/test_artifacts.py`

**Interfaces:**
- Produces: `sha256_file(path) -> str`, `canonical_sha256(value) -> str`, `verify_artifact(root, record) -> Path`, and `validate_disjoint_splits(cases) -> dict`.
- `record` is `{"path": relative_path, "sha256": 64_hex_chars}`.

- [ ] **Step 1: Write failing contract tests**

```python
def test_verify_artifact_rejects_hash_drift(tmp_path):
    from traffic_rl.research.artifacts import sha256_file, verify_artifact
    (tmp_path / "a.json").write_text('{"x":1}\n')
    record = {"path": "a.json", "sha256": sha256_file(tmp_path / "a.json")}
    assert verify_artifact(tmp_path, record) == tmp_path / "a.json"
    (tmp_path / "a.json").write_text('{"x":2}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_artifact(tmp_path, record)

def test_split_validator_rejects_reused_demand_seed():
    from traffic_rl.research.artifacts import validate_disjoint_splits
    cases = [{"split": "train", "demand_seed": 11},
             {"split": "test", "demand_seed": 11}]
    with pytest.raises(ValueError, match="multiple splits"):
        validate_disjoint_splits(cases)
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/research/test_artifacts.py -v`

Expected: FAIL because `traffic_rl.research.artifacts` does not exist.

- [ ] **Step 3: Implement the minimal helpers**

```python
def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()

def verify_artifact(root, record):
    path = Path(root) / record["path"]
    if not path.exists() or sha256_file(path) != record["sha256"]:
        raise ValueError("hash mismatch: %s" % record["path"])
    return path
```

Implement `validate_disjoint_splits` so each split is non-empty and no demand seed or flow hash occurs in two splits.

- [ ] **Step 4: Verify GREEN and regression suite**

Run: `PYTHONPATH=src pytest tests/research/test_artifacts.py tests/eval/test_runner.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/research tests/research/test_artifacts.py
git commit -m "feat: add research artifact manifest contract"
```

### Task 2: Version and audit the canonical 53-signal network

**Files:**
- Create: `datasets/haichau_network_v2/roadnet.json`
- Create: `datasets/haichau_network_v2/provenance.json`
- Create: `src/traffic_rl/network/haichau_dataset.py`
- Test: `tests/network/test_haichau_dataset.py`

**Interfaces:**
- Consumes: `RoadNet.load(path)` and artifact helpers from Task 1.
- Produces: `audit_network(path) -> dict` with `roads`, `intersections`, `controlled_signals`, `agent_ids`, `directed_signal_edges`, `weak_components`, `phase_errors`.

- [ ] **Step 1: Write failing audit tests using a hand-built roadnet fixture**

```python
def test_audit_network_counts_only_multi_phase_signals(tmp_path, mini_roadnet):
    from traffic_rl.network.haichau_dataset import audit_network
    report = audit_network(mini_roadnet)
    assert report["controlled_signals"] == 1
    assert report["phase_errors"] == []

def test_audit_network_rejects_missing_lane_reference(tmp_path, broken_roadnet):
    from traffic_rl.network.haichau_dataset import audit_network
    report = audit_network(broken_roadnet)
    assert any("missing road" in error for error in report["phase_errors"])
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py -v`

Expected: FAIL because `audit_network` is missing.

- [ ] **Step 3: Implement graph and phase audit**

Walk every `roadLink` and `laneLink`; verify referenced roads and lane indices. Build directed signal adjacency when a road connects two controlled signals. Count weakly connected components over controlled signals and sort all IDs before returning the report.

- [ ] **Step 4: Copy and describe the canonical network**

Run:

```bash
mkdir -p datasets/haichau_network_v2
cp data/danang/roadnet_haichau_rush.json datasets/haichau_network_v2/roadnet.json
```

Write `provenance.json` with:

```json
{
  "dataset_id": "haichau_network_v2",
  "data_source_label": "osm_topology_synthetic_demand",
  "osm_source": "Geofabrik Vietnam extract clipped to Hai Chau bbox",
  "bbox_wgs84": [108.1888, 16.0213, 108.2360, 16.1037],
  "roadnet_expected_sha256": "cddce1090b214fd8250303a28b51e4a460f4af04dde87cafad9dabd58f2ac040",
  "expected_controlled_signals": 53,
  "license": "OpenStreetMap ODbL; derived topology"
}
```

- [ ] **Step 5: Verify the real dataset gate**

Run:

```bash
PYTHONPATH=src python3 -c "from traffic_rl.network.haichau_dataset import audit_network; import json; r=audit_network('datasets/haichau_network_v2/roadnet.json'); print(json.dumps(r,indent=2)); assert r['controlled_signals']==53; assert not r['phase_errors']"
```

Expected: 53 controlled signals and zero phase errors.

- [ ] **Step 6: Run tests and commit**

Run: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py tests/network/test_roadnet_phases.py -v`

```bash
git add datasets/haichau_network_v2 src/traffic_rl/network/haichau_dataset.py tests/network/test_haichau_dataset.py
git commit -m "data: version canonical Hai Chau 53-signal network"
```

### Task 3: Deterministic multi-regime OD demand generator

**Files:**
- Modify: `src/traffic_rl/network/haichau_dataset.py`
- Create: `configs/haichau_network_v2.yaml`
- Test: `tests/network/test_haichau_demand.py`

**Interfaces:**
- Produces: `generate_routes(roadnet, seed, route_count, min_signals) -> list[list[str]]` and `build_flow_cases(roadnet, config) -> list[dict]`.
- Each case includes `case_id`, `split`, `scenario`, `demand_seed`, `sim_seed`, `scale`, `flow`, `route_signal_histogram`, and `data_source_label`.

- [ ] **Step 1: Write failing determinism and coverage tests**

```python
def test_routes_are_seeded_and_cross_multiple_signals(signal_chain_roadnet):
    a = generate_routes(signal_chain_roadnet, seed=11, route_count=4, min_signals=2)
    b = generate_routes(signal_chain_roadnet, seed=11, route_count=4, min_signals=2)
    assert a == b
    assert all(count_controlled_signals(signal_chain_roadnet, r) >= 2 for r in a)

def test_normal_am_pm_cases_use_disjoint_split_seeds(config_fixture):
    cases = build_flow_cases(config_fixture.roadnet, config_fixture.value)
    validate_disjoint_splits(cases)
    assert {c["scenario"] for c in cases if c["split"] == "train"} == {
        "normal", "am_peak", "pm_peak"}
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/network/test_haichau_demand.py -v`

Expected: FAIL because route generation functions are missing.

- [ ] **Step 3: Implement seeded graph routing**

Build boundary candidates from `RoadNet.entry_roads()` and exit roads ending at virtual intersections. Use deterministic breadth-first search with seed-shuffled neighbors, reject loops and routes crossing fewer than `min_signals`, and raise `ValueError("insufficient multi-signal routes")` instead of silently reducing the count.

Construct CityFlow flow rows with explicit vehicle template, `startTime`, `endTime`, `interval` and road ID route. Apply regime multipliers to interval while keeping route family fixed inside a case.

- [ ] **Step 4: Add the resolved input configuration**

```yaml
schema_version: 2
dataset_id: haichau_network_v2
roadnet: datasets/haichau_network_v2/roadnet.json
demand_label: synthetic_osm_haichau_constrained_by_danang_profiles
route_count: 500
min_controlled_signals_per_route: 2
horizon_seconds: 3600
motorcycle_ratio: 0.90
regimes:
  normal: {interval_seconds: 72.0}
  am_peak: {interval_seconds: 45.0}
  pm_peak: {interval_seconds: 36.0}
splits:
  train: {demand_seeds: [11, 12, 13], sim_seeds: [111, 112, 113]}
  validation: {demand_seeds: [31, 32], sim_seeds: [131, 132]}
  test: {demand_seeds: [101, 102, 103, 104, 105], sim_seeds: [201, 202, 203, 204, 205]}
simulation:
  action_interval: 10
  yellow_time: 3
  min_green: 20
  maximum_red: 180
preprocessing:
  count_norm: 20.0
  capacity_norm: 40.0
```

- [ ] **Step 5: Verify tests and commit**

Run: `PYTHONPATH=src pytest tests/network/test_haichau_demand.py tests/research/test_artifacts.py -v`

```bash
git add configs/haichau_network_v2.yaml src/traffic_rl/network/haichau_dataset.py tests/network/test_haichau_demand.py
git commit -m "feat: generate seeded Hai Chau multi-regime demand"
```

### Task 4: Build the versioned experiment manifest and flows

**Files:**
- Create: `scripts/prepare_haichau_network_v2.py`
- Create: generated `results/haichau_network_v2/experiment-manifest.json`
- Create: generated `results/haichau_network_v2/demands/*.json`
- Test: `tests/scripts/test_prepare_haichau_network.py`

**Interfaces:**
- Consumes: config from Task 3 and `build_flow_cases`.
- Produces: protocol version 2 manifest with `network`, `generator_config_sha256`, `cases`, `runtime`, `preprocessing`, and `simulation`.

- [ ] **Step 1: Write a failing CLI test**

```python
def test_prepare_writes_hash_bound_cases(tmp_path, mini_config):
    manifest = prepare(mini_config, tmp_path)
    assert manifest["protocol_version"] == 2
    assert all(len(c["flow_sha256"]) == 64 for c in manifest["cases"])
    assert manifest["network"]["controlled_signals"] == 1
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/scripts/test_prepare_haichau_network.py -v`

Expected: FAIL because `prepare` does not exist.

- [ ] **Step 3: Implement builder and canonical output**

Use `json.dumps(..., indent=2, sort_keys=True) + "\n"` for every generated file. Store paths relative to repository root. Refuse to overwrite an existing manifest whose network or generator hash differs unless `--new-version` is supplied.

- [ ] **Step 4: Generate the real case family**

Run: `PYTHONPATH=src python3 scripts/prepare_haichau_network_v2.py`

Expected: 30 primary cases: 9 train, 6 validation and 15 test, covering normal/AM/PM in each split.

- [ ] **Step 5: Verify and commit**

Run: `PYTHONPATH=src pytest tests/scripts/test_prepare_haichau_network.py -v`

```bash
git add scripts/prepare_haichau_network_v2.py tests/scripts/test_prepare_haichau_network.py results/haichau_network_v2
git commit -m "data: prepare Hai Chau v2 experiment cases"
```

### Task 5: Pin and smoke the CityFlow research runtime

**Files:**
- Create: `docker/cityflow-research/Dockerfile`
- Modify: `Makefile`
- Create: `scripts/verify_haichau_foundation.py`
- Test: `tests/scripts/test_verify_haichau_foundation.py`

**Interfaces:**
- Produces: `make haichau-image`, `make haichau-smoke`, and `verify_foundation(root, manifest) -> dict`.

- [ ] **Step 1: Write failing verifier tests**

```python
def test_foundation_verifier_rejects_wrong_agent_count(tmp_path, manifest_fixture):
    manifest_fixture["network"]["controlled_signals"] = 52
    with pytest.raises(ValueError, match="controlled signal count"):
        verify_foundation(tmp_path, manifest_fixture)
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_foundation.py -v`

Expected: FAIL because verifier is missing.

- [ ] **Step 3: Add the pinned runtime recipe**

```dockerfile
FROM cityflowproject/cityflow@sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32
RUN pip install --no-cache-dir dataclasses==0.8 numpy==1.19.5 PyYAML==5.4.1
WORKDIR /work
ENV PYTHONPATH=/work/src
```

Add Make targets that build `traffic-rl-cityflow-research:v2` and run a 60-second Fixed-Time episode with `--platform linux/amd64` explicitly set.

- [ ] **Step 4: Implement fail-closed foundation verification**

Verify all artifact hashes, exact 53-agent audit, split disjointness, all scenario coverage, route-signal histogram minimum, runtime digest and expected 30 cases. Print one JSON record with counts and hashes on success.

- [ ] **Step 5: Run host tests, build and engine smoke**

Run:

```bash
PYTHONPATH=src pytest tests/research tests/network/test_haichau_dataset.py tests/network/test_haichau_demand.py tests/scripts/test_prepare_haichau_network.py tests/scripts/test_verify_haichau_foundation.py -v
make haichau-image
make haichau-smoke
PYTHONPATH=src python3 scripts/verify_haichau_foundation.py
```

Expected: all tests pass; smoke reports 53 agents and 60 simulator steps; verifier reports 30 cases.

- [ ] **Step 6: Clean-checkout gate**

Create a temporary clone from current HEAD, run `scripts/verify_haichau_foundation.py` there, build the image, and run `make haichau-smoke`. Record command, commit SHA, wall time and output under `results/haichau_network_v2/verification/foundation.json`.

- [ ] **Step 7: Commit**

```bash
git add docker/cityflow-research Makefile scripts/verify_haichau_foundation.py tests/scripts/test_verify_haichau_foundation.py results/haichau_network_v2/verification/foundation.json
git commit -m "build: verify reproducible Hai Chau research foundation"
```

## Foundation Completion Gate

Do not start model work until all are true:

- tracked roadnet hash matches provenance;
- network audit reports exactly 53 controlled signals and no phase errors;
- 30 demand cases cover normal/AM/PM with disjoint splits;
- routes satisfy the declared multi-signal coverage;
- pinned Docker smoke completes 60 steps;
- the same checks pass in a clean checkout.
