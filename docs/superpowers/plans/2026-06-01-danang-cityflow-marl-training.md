# MARL Training & Full Comparison Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Da Nang network, add a correct green-phase signal-control model (min-green + yellow), implement Max-Pressure / Random baselines and a parameter-shared NumPy DQN, then produce a full quantitative comparison (metrics + plots) of all four controllers.

**Architecture:** Everything that touches CityFlow runs inside the `cityflowproject/cityflow:latest` Docker image (Python 3.6.5). PyTorch is incompatible with 3.6, so the DQN is a small from-scratch NumPy MLP that runs in the *same* process as CityFlow — no IPC, no torch. Pure-Python logic (roadnet parsing, observation encoding, pressure, DQN math, controllers) is unit-tested locally on Python 3.13; only the end-to-end runs need Docker. Controllers share one interface `act(context) -> {agent_id: green_choice}` so a single runner drives all of them.

**Tech Stack:** CityFlow (Docker), NumPy (DQN + math), SUMO `netconvert` + CityFlow `converter.py` + `osmium-tool` (network build), matplotlib (plots), pytest (TDD).

---

## Background the implementer needs

This continues Plan 1 (Foundation). The pipeline OSM → SUMO → CityFlow → multi-agent env already works on a Da Nang **sub-area** (10 signalized intersections). Key facts:

- **CityFlow only runs in Docker** (`make cf-run CMD="..."`, `make cf-test`). The image is **Python 3.6.5**: no `from __future__ import annotations`, `dataclasses` is pip-installed there. All modules imported in-container must stay 3.6-safe.
- **Tests:** `make test` runs locally (`pytest -m 'not docker'`, py3.13). `make cf-test` runs `@pytest.mark.docker` tests inside the image. Local suite is currently **18 passing**.
- **Roadnet lightphases** alternate green / transition. Inspected example (`roadnet_subarea.json`, intersection `1334170383`, 12 roadLinks):
  - phase 0: `availableRoadLinks = [3,4,5,6,7,8]`, time 39 → **green**
  - phase 1: `availableRoadLinks = []`, time 6 → **yellow/all-red**
  - phase 2: `availableRoadLinks = [0,1,2,9,10,11]`, time 39 → **green**
  - phase 3: `availableRoadLinks = []`, time 6 → **yellow/all-red**
  - Distribution across the 10 agents: 7 intersections have 4 phases, 3 have 6 phases. So **green phases = those with non-empty `availableRoadLinks`** (do NOT assume index parity; derive it).
- **Lane id format:** `"{roadId}_{laneIndex}"`. A `roadLink` has `startRoad`, `endRoad`, and `laneLinks: [{startLaneIndex, endLaneIndex}, ...]`.
- **Existing files** (Plan 1): `src/traffic_rl/network/roadnet.py`, `.../network/osm_to_sumo.py`, `.../network/sumo_to_cityflow.py`, `.../network/flow_gen.py`, `.../sim/intersection.py`, `.../sim/engine.py`, `.../sim/multi_agent_env.py`, `.../agents/fixed_time.py`, `scripts/run_fixed_time.py`. `configs/network.yaml` has `bbox.full = [108.12, 16.00, 108.28, 16.08]`.

### Design decisions locked for this plan
1. **DQN = NumPy** 2-hidden-layer MLP with Adam, target network, replay buffer, epsilon-greedy + action masking. Runs in-container.
2. **Scope = full Da Nang first.** Build `roadnet_full.json` / `flow_full.json` via a Geofabrik PBF clipped with `osmium-tool` (Overpass is blocked from this machine; the OSM export API 50k-node limit fails on the full bbox). Code stays area-parameterized so sub-area remains a smoke target.
3. **Action space = green phases only.** Action `a ∈ {0..G_i-1}` selects the i-th green lightphase. The env maps it to the real lightphase index, enforces **min-green**, and inserts a **yellow/all-red** phase for `yellow_time` engine-steps on a switch.
4. **Reward = signed intersection pressure:** `-(sum incoming-lane queue − sum outgoing-lane queue)` (drop the `abs()` from Plan 1; this is the standard max-pressure learning signal).
5. **Observation = normalized + zero-padded** to global dims so one shared network fits every intersection: `[queue per incoming lane / NORM (padded to max_in)] + [one-hot current green-phase (padded to max_green)]`. Each agent also gets a boolean **action mask** of length `max_green`.
6. **Controller interface:** `act(context) -> {agent_id: green_choice}` where `context = {"observations": {...}, "waiting_counts": {lane: int}, "action_masks": {agent_id: np.bool_ array}}`. A single `run_episode` builds the context and drives Fixed-Time, Max-Pressure, Random, and the trained DQN identically.

## File structure (created / modified)

```
src/traffic_rl/
  network/roadnet.py        (MODIFY) green_phases(), phase_movements(), all_red_phase()
  sim/encoder.py            (CREATE) ObservationEncoder: global dims, normalize, pad, masks
  sim/intersection.py       (MODIFY) signed pressure reward
  sim/multi_agent_env.py    (MODIFY) green-phase actions, min-green + yellow, encoder, masks, queue in info
  agents/base.py            (CREATE) Controller protocol + shared helpers
  agents/fixed_time.py      (MODIFY) cycle green phases via act(context)
  agents/max_pressure.py    (CREATE) MaxPressureController
  agents/random_agent.py    (CREATE) RandomController
  agents/dqn.py             (CREATE) SharedDQN (NumPy MLP+Adam) + ReplayBuffer + epsilon schedule
  train/__init__.py         (CREATE)
  train/trainer.py          (CREATE) training loop, checkpoint (.npz), JSON log
  eval/__init__.py          (CREATE)
  eval/runner.py            (CREATE) run_episode + metric collection
  eval/compare.py           (CREATE) run all controllers, aggregate, plot
scripts/
  build_full_network.py     (CREATE) Geofabrik PBF -> clip -> netconvert -> CityFlow -> flow (full)
  run_baseline.py           (CREATE) run one baseline controller, save metrics
  train_dqn.py              (CREATE) Docker entry: train shared DQN
  run_comparison.py         (CREATE) Docker entry: run all 4 + write comparison.json + plots
configs/training.yaml       (CREATE) hyperparameters
tests/
  network/test_roadnet_phases.py     (CREATE)
  sim/test_encoder.py                (CREATE)
  sim/test_intersection.py           (MODIFY) signed reward
  sim/test_multi_agent_env.py        (MODIFY) green actions + yellow/min-green via fake engine
  agents/test_fixed_time.py          (MODIFY) new interface
  agents/test_max_pressure.py        (CREATE)
  agents/test_random_agent.py        (CREATE)
  agents/test_dqn.py                 (CREATE)
  train/test_trainer.py              (CREATE) uses a fake engine, no Docker
  eval/test_runner.py                (CREATE) uses a fake engine, no Docker
```

A shared **fake engine** is needed by several tests. Put it in `tests/conftest.py` as a fixture/class so env, trainer, and runner tests reuse it.

---

## Phase A — Full Da Nang network (unblock Task #13)

### Task 1: Add a shared FakeEngine test fixture

**Files:**
- Modify: `tests/conftest.py`

This unblocks every later non-Docker test (env, trainer, runner). A `FakeEngine` duck-types the methods `MultiAgentTrafficEnv` calls and records the call sequence so we can assert yellow/min-green behaviour.

- [ ] **Step 1: Append the FakeEngine to conftest**

```python
# --- appended to tests/conftest.py ---
class FakeEngine:
    """Duck-typed stand-in for CityFlowEngine.

    Records set_tl_phase + step calls so tests can assert phase scheduling.
    lane counts are programmable via .vehicle_counts / .waiting_counts dicts.
    """
    def __init__(self, vehicle_counts=None, waiting_counts=None):
        self.vehicle_counts = dict(vehicle_counts or {})
        self.waiting_counts = dict(waiting_counts or {})
        self.calls = []          # ("set", inter_id, phase) / ("step",) / ("reset",)
        self.phase = {}          # inter_id -> last phase set
        self._tt = 0.0
        self._t = 0

    def reset(self):
        self.calls.append(("reset",))
        self._t = 0

    def step(self):
        self.calls.append(("step",))
        self._t += 1
        self._tt += 1.0

    def set_tl_phase(self, inter_id, phase):
        self.calls.append(("set", inter_id, phase))
        self.phase[inter_id] = phase

    def lane_vehicle_counts(self):
        return dict(self.vehicle_counts)

    def lane_waiting_counts(self):
        return dict(self.waiting_counts)

    def vehicle_count(self):
        return sum(self.vehicle_counts.values())

    def average_travel_time(self):
        return self._tt

    def steps_of(self, kind):
        return [c for c in self.calls if c[0] == kind]
```

- [ ] **Step 2: Verify the suite still collects**

Run: `make test`
Expected: still 18 passed (no behavior change yet; new class is unused).

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared FakeEngine fixture for env/trainer/runner tests"
```

### Task 2: Build the full Da Nang network (PBF → clip → SUMO → CityFlow)

**Files:**
- Create: `scripts/build_full_network.py`

Not TDD (data/IO orchestration). Reuses `osm_to_sumo.run_netconvert` and `sumo_to_cityflow.run_converter` from Plan 1. Produces `data/danang/roadnet_full.json`.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Build the full-central-Da-Nang CityFlow roadnet from a Geofabrik PBF.

Overpass is blocked from this machine and the OSM export API caps at ~50k nodes,
so we download the Vietnam extract once and clip the Da Nang bbox locally with
osmium-tool (`brew install osmium-tool`).

Run locally (needs SUMO netconvert + osmium on PATH; the converter step uses Docker):
  python3 scripts/build_full_network.py
"""
import subprocess
import sys
from pathlib import Path

import yaml

from traffic_rl.network.osm_to_sumo import run_netconvert
from traffic_rl.network.sumo_to_cityflow import run_converter

ROOT = Path(__file__).resolve().parent.parent
OSM_DIR = ROOT / "data" / "osm"
OUT_DIR = ROOT / "data" / "danang"
PBF_URL = "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"


def sh(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bbox = yaml.safe_load((ROOT / "configs" / "network.yaml").read_text())["bbox"]["full"]
    left, bottom, right, top = bbox  # [minlon, minlat, maxlon, maxlat]

    pbf = OSM_DIR / "vietnam-latest.osm.pbf"
    if not pbf.exists():
        sh(["curl", "-L", "--fail", "-o", str(pbf), PBF_URL])

    clipped_pbf = OSM_DIR / "danang_full.osm.pbf"
    sh(["osmium", "extract", "--overwrite",
        "-b", "{},{},{},{}".format(left, bottom, right, top),
        str(pbf), "-o", str(clipped_pbf)])

    osm_xml = OSM_DIR / "danang_full.osm"
    sh(["osmium", "cat", "--overwrite", str(clipped_pbf), "-o", str(osm_xml)])

    sumo_net = OSM_DIR / "danang_full.net.xml"
    run_netconvert(str(osm_xml), str(sumo_net))

    roadnet = OUT_DIR / "roadnet_full.json"
    run_converter(str(sumo_net), str(roadnet))
    print("Wrote", roadnet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Install osmium and run**

Run:
```bash
brew install osmium-tool
PYTHONPATH=src python3 scripts/build_full_network.py
```
Expected: downloads `vietnam-latest.osm.pbf` (~300MB, one-time), writes `data/danang/roadnet_full.json` (non-empty). The converter prints progress; the `run_converter` patch from Plan 1 applies.

- [ ] **Step 3: Verify signalized agent count**

Run:
```bash
PYTHONPATH=src python3 -c "from traffic_rl.network.roadnet import RoadNet; rn=RoadNet.load('data/danang/roadnet_full.json'); ids=rn.signalized_ids(); print('signalized agents:', len(ids))"
```
Expected: prints a count **> 10** (the sub-area had 10; the full central-Da-Nang bbox should yield more, on the order of the ~37 tagged signals plus netconvert-guessed ones). If it errors or prints 0, STOP and report — likely a converter/network issue to debug before proceeding.

- [ ] **Step 4: Commit (script only; data is gitignored)**

```bash
git add scripts/build_full_network.py
git commit -m "feat: build full Da Nang CityFlow network via Geofabrik PBF clip"
```

### Task 3: Generate full-network synthetic flow

**Files:**
- Create/extend: reuse `src/traffic_rl/network/flow_gen.py` (no code change expected) via a one-liner; verify it scales.

- [ ] **Step 1: Generate flow for the full roadnet**

Run:
```bash
PYTHONPATH=src python3 -c "
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.network.flow_gen import generate_flow, write_flow
import yaml
p = yaml.safe_load(open('configs/network.yaml'))['flow']
rn = RoadNet.load('data/danang/roadnet_full.json')
flows = generate_flow(rn, num_flows=p['num_flows'], route_length=p['route_length'],
                      seed=p['seed'], motorbike_ratio=p['motorbike_ratio'], end_time=p['end_time'])
write_flow(flows, 'data/danang/flow_full.json')
print('flows:', len(flows))
"
```
Expected: writes `data/danang/flow_full.json`, prints `flows: 300` (or the configured count). If `generate_flow` raises on the larger net (e.g., an intersection with no outgoing road during the random walk), STOP and add a guard task — do not silently reduce flow count.

- [ ] **Step 2: Smoke the full network end-to-end with Fixed-Time**

Run:
```bash
make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_fixed_time.py full"
```
Expected: completes without crashing and prints metrics JSON with `"area": "full"` and `agents` matching Task 2. (This validates the full net loads in the real engine before we build training on it.)

- [ ] **Step 3: Commit any guard fixes** (only if Step 1 required them; otherwise skip — no code changed).

---

## Phase B — Green-phase signal model

### Task 4: Roadnet green-phase + movement helpers

**Files:**
- Modify: `src/traffic_rl/network/roadnet.py`
- Test: `tests/network/test_roadnet_phases.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from traffic_rl.network.roadnet import RoadNet

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False,
            "roads": ["rin", "rout"],
            "roadLinks": [
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]},
            ],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},   # green 0
                {"time": 6,  "availableRoadLinks": []},     # all-red
                {"time": 39, "availableRoadLinks": [1]},   # green 1
            ]},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "X", "endIntersection": "A",
             "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "Y",
             "lanes": [{}]},
        ],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data))
    return RoadNet.load(str(p))

def test_green_phases_excludes_all_red(tmp_path):
    rn = _net(tmp_path)
    assert rn.green_phases("A") == [0, 2]

def test_all_red_phase_is_first_empty(tmp_path):
    rn = _net(tmp_path)
    assert rn.all_red_phase("A") == 1

def test_phase_movements_maps_lane_ids(tmp_path):
    rn = _net(tmp_path)
    inc, out = rn.phase_movements("A", 0)   # roadLink 0: rin_0 -> rout_0
    assert inc == ["rin_0"] and out == ["rout_0"]
    inc2, out2 = rn.phase_movements("A", 2)  # roadLink 1: rin_1 -> rout_0
    assert inc2 == ["rin_1"] and out2 == ["rout_0"]
```

- [ ] **Step 2: Run to confirm failure**

Run: `make test -- tests/network/test_roadnet_phases.py` (or `SUMO_HOME=/opt/homebrew/share/sumo python3 -m pytest tests/network/test_roadnet_phases.py -v`)
Expected: FAIL — `AttributeError: 'RoadNet' object has no attribute 'green_phases'`.

- [ ] **Step 3: Implement the helpers**

Add to `RoadNet` in `src/traffic_rl/network/roadnet.py`:

```python
    def _lightphases(self, inter_id):
        return self._by_id[inter_id]["trafficLight"]["lightphases"]

    def green_phases(self, inter_id):
        """Lightphase indices that actually let traffic move (non-empty availableRoadLinks)."""
        return [idx for idx, ph in enumerate(self._lightphases(inter_id))
                if ph.get("availableRoadLinks")]

    def all_red_phase(self, inter_id):
        """First all-red / yellow lightphase index (empty availableRoadLinks), or None."""
        for idx, ph in enumerate(self._lightphases(inter_id)):
            if not ph.get("availableRoadLinks"):
                return idx
        return None

    def phase_movements(self, inter_id, phase_idx):
        """Deduped (incoming_lanes, outgoing_lanes) served by a lightphase."""
        inter = self._by_id[inter_id]
        road_links = inter["roadLinks"]
        ph = self._lightphases(inter_id)[phase_idx]
        inc, out = [], []
        for rl_idx in ph.get("availableRoadLinks", []):
            rl = road_links[rl_idx]
            for ll in rl["laneLinks"]:
                il = "{}_{}".format(rl["startRoad"], ll["startLaneIndex"])
                ol = "{}_{}".format(rl["endRoad"], ll["endLaneIndex"])
                if il not in inc:
                    inc.append(il)
                if ol not in out:
                    out.append(ol)
        return inc, out
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/network/test_roadnet_phases.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/network/roadnet.py tests/network/test_roadnet_phases.py
git commit -m "feat: roadnet green-phase + per-phase movement helpers"
```

### Task 5: Signed pressure reward

**Files:**
- Modify: `src/traffic_rl/sim/intersection.py`
- Modify: `tests/sim/test_intersection.py`

- [ ] **Step 1: Update/add the failing test**

Add to `tests/sim/test_intersection.py`:

```python
from traffic_rl.sim.intersection import IntersectionState, pressure_reward

def test_pressure_reward_is_signed_negative_inflow():
    st = IntersectionState("A", ["i0", "i1"], ["o0"], num_phases=2)
    # incoming queue 5, outgoing queue 2 -> pressure 3 -> reward -3
    assert pressure_reward(st, {"i0": 3, "i1": 2, "o0": 2}) == -3.0

def test_pressure_reward_positive_when_outflow_dominates():
    st = IntersectionState("A", ["i0"], ["o0", "o1"], num_phases=2)
    # incoming 1, outgoing 4 -> pressure -3 -> reward +3 (signed, not abs)
    assert pressure_reward(st, {"i0": 1, "o0": 1, "o1": 3}) == 3.0
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/sim/test_intersection.py -v`
Expected: `test_pressure_reward_positive_when_outflow_dominates` FAILS (current code uses `abs`, returns -3.0 not +3.0).

- [ ] **Step 3: Make the reward signed**

In `src/traffic_rl/sim/intersection.py` replace the body of `pressure_reward`:

```python
def pressure_reward(state, waiting_counts):
    """Signed max-pressure reward = -(incoming queue - outgoing queue).

    Negative pressure (queues draining downstream) yields positive reward.
    """
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    outflow = sum(waiting_counts.get(l, 0) for l in state.outgoing_lanes)
    return -float(inflow - outflow)
```

(Drop the type hints if they used `Dict` only via annotations — keep imports as-is; 3.6-safe.)

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/sim/test_intersection.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/intersection.py tests/sim/test_intersection.py
git commit -m "feat: signed max-pressure reward (drop abs)"
```

### Task 6: ObservationEncoder (normalize + pad + masks)

**Files:**
- Create: `src/traffic_rl/sim/encoder.py`
- Test: `tests/sim/test_encoder.py`

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from traffic_rl.sim.encoder import ObservationEncoder

class StubNet:
    # two agents with different #incoming lanes and #green phases
    def signalized_ids(self): return ["A", "B"]
    def incoming_lanes(self, i): return {"A": ["a0", "a1"], "B": ["b0"]}[i]
    def green_phases(self, i): return {"A": [0, 2], "B": [0, 2, 4]}[i]

def test_dims_are_global_max():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    assert enc.max_in == 2 and enc.max_green == 3
    assert enc.obs_dim == 2 + 3  # padded lanes + padded one-hot

def test_encode_normalizes_pads_and_one_hots():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    # agent B has 1 lane (queue 5) and is at its 2nd green phase (green index 1)
    v = enc.encode("B", lane_counts={"b0": 5}, green_index=1)
    assert v.shape == (5,)
    # lane part: [0.5, 0(pad)] ; phase one-hot over 3: [0,1,0]
    assert np.allclose(v, [0.5, 0.0, 0.0, 1.0, 0.0])

def test_action_mask_marks_valid_greens():
    enc = ObservationEncoder(StubNet(), count_norm=10.0)
    np.testing.assert_array_equal(enc.action_mask("A"), [True, True, False])
    np.testing.assert_array_equal(enc.action_mask("B"), [True, True, True])
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/sim/test_encoder.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the encoder**

```python
"""Fixed-size, normalized observations + action masks for a shared policy.

Different intersections have different #lanes / #phases. We pad to the global
maxima so one network input/output shape fits every agent. 3.6-safe.
"""
import numpy as np


class ObservationEncoder:
    def __init__(self, roadnet, count_norm=10.0):
        self.count_norm = float(count_norm)
        ids = roadnet.signalized_ids()
        self._incoming = {i: roadnet.incoming_lanes(i) for i in ids}
        self._greens = {i: roadnet.green_phases(i) for i in ids}
        self.max_in = max(len(self._incoming[i]) for i in ids)
        self.max_green = max(len(self._greens[i]) for i in ids)
        self.obs_dim = self.max_in + self.max_green

    def num_greens(self, inter_id):
        return len(self._greens[inter_id])

    def encode(self, inter_id, lane_counts, green_index):
        v = np.zeros(self.obs_dim, dtype=np.float32)
        for k, lane in enumerate(self._incoming[inter_id]):
            v[k] = lane_counts.get(lane, 0) / self.count_norm
        if 0 <= green_index < self.num_greens(inter_id):
            v[self.max_in + green_index] = 1.0
        return v

    def action_mask(self, inter_id):
        m = np.zeros(self.max_green, dtype=np.bool_)
        m[: self.num_greens(inter_id)] = True
        return m
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/sim/test_encoder.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/encoder.py tests/sim/test_encoder.py
git commit -m "feat: ObservationEncoder with normalization, padding, action masks"
```

### Task 7: Env green-phase actions + min-green + yellow

**Files:**
- Modify: `src/traffic_rl/sim/multi_agent_env.py`
- Modify: `tests/sim/test_multi_agent_env.py`

The env now takes `green_choice` actions, maps them to lightphases, enforces `min_green` (engine-steps a green must hold before switching), and inserts the all-red phase for `yellow_time` engine-steps on a switch. It exposes `num_actions`, `action_masks()`, `current_waiting_counts()`, and includes `total_queue` in `info`.

- [ ] **Step 1: Write the failing tests** (replace the body of `tests/sim/test_multi_agent_env.py`)

```python
import json
import numpy as np
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from tests.conftest import FakeEngine

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": [
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                {"startRoad": "rin", "endRoad": "rout",
                 "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]},
            ],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},   # green idx 0 -> phase 0
                {"time": 6,  "availableRoadLinks": []},     # all-red -> phase 1
                {"time": 39, "availableRoadLinks": [1]},   # green idx 1 -> phase 2
            ]},
        }],
        "roads": [
            {"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
            {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]},
        ],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data))
    return RoadNet.load(str(p))

def test_num_actions_and_masks(tmp_path):
    env = MultiAgentTrafficEnv(_net(tmp_path), FakeEngine(),
                               action_interval=10, yellow_time=3, min_green=5)
    assert env.num_actions == {"A": 2}
    np.testing.assert_array_equal(env.action_masks()["A"], [True, True])

def test_keeping_phase_does_not_insert_yellow(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=0)
    env.reset()
    env.step({"A": 0})            # already at green 0 -> no switch
    assert eng.steps_of("step").__len__() == 10
    assert ("set", "A", 1) not in eng.calls   # all-red phase never set

def test_switching_inserts_yellow_then_new_green(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=0)
    env.reset()
    env.step({"A": 1})            # switch green 0 -> green 1 (lightphase 2)
    # expect: set all-red (1), 3 steps, set green lightphase 2, 7 steps
    assert ("set", "A", 1) in eng.calls
    assert ("set", "A", 2) in eng.calls
    assert len(eng.steps_of("step")) == 10

def test_min_green_blocks_early_switch(tmp_path):
    eng = FakeEngine()
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=10, yellow_time=3, min_green=100)
    env.reset()
    env.step({"A": 1})            # min_green not satisfied -> stay on green 0
    assert ("set", "A", 1) not in eng.calls
    assert env._green["A"] == 0

def test_info_has_total_queue(tmp_path):
    eng = FakeEngine(waiting_counts={"rin_0": 2, "rin_1": 1, "rout_0": 0})
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=2, yellow_time=1, min_green=0)
    env.reset()
    _, rewards, _, info = env.step({"A": 0})
    assert info["total_queue"] == 3      # sum of all waiting lanes
    assert rewards["A"] == -3.0          # signed pressure: -(3 - 0)
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/sim/test_multi_agent_env.py -v`
Expected: FAIL (constructor lacks `yellow_time`/`min_green`; no `num_actions`).

- [ ] **Step 3: Rewrite the env**

Replace `src/traffic_rl/sim/multi_agent_env.py` with:

```python
"""Multi-agent traffic-signal env over a duck-typed engine.

Actions are GREEN-phase choices (0..G_i-1). The env maps each to the real
lightphase index, enforces min-green, and inserts the all-red phase for
yellow_time engine-steps on a switch. Reward is signed max-pressure.

3.6-safe: no `from __future__ import annotations`.
"""
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.intersection import IntersectionState, pressure_reward


class MultiAgentTrafficEnv:
    def __init__(self, roadnet, engine, action_interval=10, max_steps=3600,
                 yellow_time=3, min_green=10, count_norm=10.0):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.yellow_time = yellow_time
        self.min_green = min_green
        self.agent_ids = roadnet.signalized_ids()
        self.encoder = ObservationEncoder(roadnet, count_norm=count_norm)
        self._green_phases = {a: roadnet.green_phases(a) for a in self.agent_ids}
        self._all_red = {a: roadnet.all_red_phase(a) for a in self.agent_ids}
        self.states = {
            a: IntersectionState(a, roadnet.incoming_lanes(a),
                                 roadnet.outgoing_lanes(a),
                                 num_phases=len(self._green_phases[a]))
            for a in self.agent_ids
        }
        self.num_actions = {a: len(self._green_phases[a]) for a in self.agent_ids}
        self.obs_dim = self.encoder.obs_dim
        self._green = {a: 0 for a in self.agent_ids}       # current green INDEX
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._t = 0

    # --- introspection used by controllers/runner ---
    def action_masks(self):
        return {a: self.encoder.action_mask(a) for a in self.agent_ids}

    def current_waiting_counts(self):
        return self.engine.lane_waiting_counts()

    # --- lifecycle ---
    def reset(self):
        self.engine.reset()
        self._green = {a: 0 for a in self.agent_ids}
        self._since_switch = {a: 0 for a in self.agent_ids}
        self._t = 0
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][0])
        return self._observations()

    def _observations(self):
        counts = self.engine.lane_vehicle_counts()
        return {a: self.encoder.encode(a, counts, self._green[a]) for a in self.agent_ids}

    def _engine_steps(self, n):
        for _ in range(n):
            self.engine.step()
            self._t += 1
        for a in self.agent_ids:
            self._since_switch[a] += n

    def step(self, actions):
        # decide switches (respecting min-green + validity)
        switching = {}
        for a, choice in actions.items():
            choice = int(choice)
            if 0 <= choice < self.num_actions[a] and choice != self._green[a] \
                    and self._since_switch[a] >= self.min_green:
                switching[a] = choice

        # yellow / all-red transition for switching agents
        if switching and self.yellow_time > 0:
            for a in switching:
                ar = self._all_red[a]
                if ar is not None:
                    self.engine.set_tl_phase(a, ar)
            self._engine_steps(self.yellow_time)
            green_steps = self.action_interval - self.yellow_time
        else:
            green_steps = self.action_interval

        # commit new greens
        for a, choice in switching.items():
            self._green[a] = choice
            self._since_switch[a] = 0
        for a in self.agent_ids:
            self.engine.set_tl_phase(a, self._green_phases[a][self._green[a]])

        if green_steps > 0:
            self._engine_steps(green_steps)

        waiting = self.engine.lane_waiting_counts()
        rewards = {a: pressure_reward(self.states[a], waiting) for a in self.agent_ids}
        done = self._t >= self.max_steps
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": self.engine.vehicle_count(),
            "total_queue": float(sum(waiting.values())),
            "step": self._t,
        }
        return self._observations(), rewards, done, info
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/sim/test_multi_agent_env.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/multi_agent_env.py tests/sim/test_multi_agent_env.py
git commit -m "feat: green-phase action space with min-green + yellow transitions"
```

### Task 8: Controller base + Fixed-Time on new interface

**Files:**
- Create: `src/traffic_rl/agents/base.py`
- Modify: `src/traffic_rl/agents/fixed_time.py`
- Modify: `tests/agents/test_fixed_time.py`
- Modify: `scripts/run_fixed_time.py`

- [ ] **Step 1: Write `agents/base.py`**

```python
"""Shared controller helpers. A controller implements:
    act(context) -> {agent_id: green_choice}
where context = {"observations": {...}, "waiting_counts": {lane: int},
                 "action_masks": {agent_id: np.bool_ array}}.
3.6-safe.
"""


class Controller(object):
    name = "base"

    def act(self, context):
        raise NotImplementedError

    def reset(self):
        pass
```

- [ ] **Step 2: Update the Fixed-Time test**

Replace `tests/agents/test_fixed_time.py`:

```python
from traffic_rl.agents.fixed_time import FixedTimeController

def test_round_robin_over_green_choices():
    c = FixedTimeController(num_actions={"A": 2, "B": 3})
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    assert c.act(ctx) == {"A": 0, "B": 0}
    assert c.act(ctx) == {"A": 1, "B": 1}
    assert c.act(ctx) == {"A": 0, "B": 2}   # A wraps at 2, B continues
    assert c.act(ctx) == {"A": 1, "B": 0}   # B wraps at 3

def test_reset_restarts_cycle():
    c = FixedTimeController(num_actions={"A": 2})
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    c.act(ctx); c.reset()
    assert c.act(ctx) == {"A": 0}
```

- [ ] **Step 3: Run to confirm failure**

Run: `python3 -m pytest tests/agents/test_fixed_time.py -v`
Expected: FAIL — `act` takes `context`, ctor arg renamed to `num_actions`.

- [ ] **Step 4: Rewrite Fixed-Time**

Replace `src/traffic_rl/agents/fixed_time.py`:

```python
"""Fixed-time baseline: each intersection cycles its green phases round-robin.
3.6-safe."""
from traffic_rl.agents.base import Controller


class FixedTimeController(Controller):
    name = "FixedTime"

    def __init__(self, num_actions):
        self.num_actions = num_actions          # {agent_id: #green phases}
        self._counter = {a: 0 for a in num_actions}

    def act(self, context):
        actions = {a: self._counter[a] % n for a, n in self.num_actions.items()}
        for a in self.num_actions:
            self._counter[a] += 1
        return actions

    def reset(self):
        self._counter = {a: 0 for a in self.num_actions}
```

- [ ] **Step 5: Update `scripts/run_fixed_time.py`** to the new API

Change the controller construction and call site:

```python
# was: FixedTimeController(num_phases={aid: rn.num_phases(aid) ...}) and controller.act()
controller = FixedTimeController(num_actions=env.num_actions)
...
ctx = {"observations": obs, "waiting_counts": env.current_waiting_counts(),
       "action_masks": env.action_masks()}
actions = controller.act(ctx)
obs, _, done, info = env.step(actions)
```
(Initialize `obs = env.reset()` before the loop; rebuild `ctx` each iteration.)

- [ ] **Step 6: Run to confirm pass**

Run: `python3 -m pytest tests/agents/test_fixed_time.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add src/traffic_rl/agents/base.py src/traffic_rl/agents/fixed_time.py \
        tests/agents/test_fixed_time.py scripts/run_fixed_time.py
git commit -m "feat: controller base interface; Fixed-Time on green-choice act(context)"
```

---

## Phase C — Baselines + runner

### Task 9: Max-Pressure controller

**Files:**
- Create: `src/traffic_rl/agents/max_pressure.py`
- Test: `tests/agents/test_max_pressure.py`

- [ ] **Step 1: Write the failing test**

```python
from traffic_rl.agents.max_pressure import MaxPressureController

class StubNet:
    def signalized_ids(self): return ["A"]
    def green_phases(self, i): return [0, 2]
    def phase_movements(self, i, p):
        # green 0 serves rin_0->rout_0 ; green 2 serves rin_1->rout_0
        return {0: (["rin_0"], ["rout_0"]),
                2: (["rin_1"], ["rout_0"])}[p]

def test_picks_phase_with_max_pressure():
    c = MaxPressureController(StubNet())
    ctx = {"waiting_counts": {"rin_0": 1, "rin_1": 9, "rout_0": 0},
           "observations": {}, "action_masks": {}}
    # pressure(green0)=1-0=1 ; pressure(green1)=9-0=9 -> choose index 1
    assert c.act(ctx) == {"A": 1}

def test_ties_pick_lowest_index():
    c = MaxPressureController(StubNet())
    ctx = {"waiting_counts": {"rin_0": 5, "rin_1": 5, "rout_0": 0},
           "observations": {}, "action_masks": {}}
    assert c.act(ctx) == {"A": 0}
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/agents/test_max_pressure.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
"""Max-Pressure baseline (Varaiya): pick the green phase maximizing pressure
= sum(incoming queue) - sum(outgoing queue) over the movements it serves.
Greedy, no learning. 3.6-safe."""
from traffic_rl.agents.base import Controller


class MaxPressureController(Controller):
    name = "MaxPressure"

    def __init__(self, roadnet):
        self.ids = roadnet.signalized_ids()
        # precompute per-agent list of (incoming_lanes, outgoing_lanes) per green
        self._mov = {}
        for a in self.ids:
            greens = roadnet.green_phases(a)
            self._mov[a] = [roadnet.phase_movements(a, p) for p in greens]

    def act(self, context):
        w = context["waiting_counts"]
        actions = {}
        for a in self.ids:
            best_idx, best_p = 0, None
            for idx, (inc, out) in enumerate(self._mov[a]):
                p = sum(w.get(l, 0) for l in inc) - sum(w.get(l, 0) for l in out)
                if best_p is None or p > best_p:
                    best_p, best_idx = p, idx
            actions[a] = best_idx
        return actions
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/agents/test_max_pressure.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/max_pressure.py tests/agents/test_max_pressure.py
git commit -m "feat: Max-Pressure baseline controller"
```

### Task 10: Random controller

**Files:**
- Create: `src/traffic_rl/agents/random_agent.py`
- Test: `tests/agents/test_random_agent.py`

- [ ] **Step 1: Write the failing test**

```python
from traffic_rl.agents.random_agent import RandomController

def test_actions_are_valid_green_indices_and_seeded():
    c1 = RandomController(num_actions={"A": 2, "B": 3}, seed=42)
    c2 = RandomController(num_actions={"A": 2, "B": 3}, seed=42)
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    seq1 = [c1.act(ctx) for _ in range(5)]
    seq2 = [c2.act(ctx) for _ in range(5)]
    assert seq1 == seq2                         # deterministic given seed
    for step in seq1:
        assert 0 <= step["A"] < 2 and 0 <= step["B"] < 3
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/agents/test_random_agent.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
"""Random baseline: pick a uniformly-random valid green phase each decision.
Lower-bound reference. 3.6-safe."""
import random
from traffic_rl.agents.base import Controller


class RandomController(Controller):
    name = "Random"

    def __init__(self, num_actions, seed=0):
        self.num_actions = num_actions
        self._rng = random.Random(seed)

    def act(self, context):
        return {a: self._rng.randrange(n) for a, n in self.num_actions.items()}

    def reset(self):
        pass
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/agents/test_random_agent.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/random_agent.py tests/agents/test_random_agent.py
git commit -m "feat: Random baseline controller"
```

### Task 11: Episode runner + metrics

**Files:**
- Create: `src/traffic_rl/eval/__init__.py` (empty)
- Create: `src/traffic_rl/eval/runner.py`
- Test: `tests/eval/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import numpy as np
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode
from tests.conftest import FakeEngine

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": [{"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                          {"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]}],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},
                {"time": 6, "availableRoadLinks": []},
                {"time": 39, "availableRoadLinks": [1]}]},
        }],
        "roads": [{"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
                  {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]}],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data)); return RoadNet.load(str(p))

def test_run_episode_returns_metrics(tmp_path):
    eng = FakeEngine(waiting_counts={"rin_0": 2, "rin_1": 1, "rout_0": 0})
    env = MultiAgentTrafficEnv(_net(tmp_path), eng, action_interval=2,
                               yellow_time=1, min_green=0, max_steps=6)
    ctrl = FixedTimeController(num_actions=env.num_actions)
    m = run_episode(env, ctrl)
    assert m["controller"] == "FixedTime"
    assert m["steps"] == 6
    assert m["agents"] == 1
    assert "final_average_travel_time" in m
    assert m["mean_total_queue"] == 3.0      # constant 3 each decision
    assert "mean_reward" in m
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/eval/test_runner.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
"""Drive any controller through one episode and collect comparison metrics.
3.6-safe (used in-container with CityFlow)."""


def run_episode(env, controller, max_decisions=None):
    obs = env.reset()
    controller.reset()
    masks = env.action_masks()
    queues, rewards, info = [], [], {}
    done = False
    decisions = 0
    while not done:
        ctx = {"observations": obs,
               "waiting_counts": env.current_waiting_counts(),
               "action_masks": masks}
        actions = controller.act(ctx)
        obs, r, done, info = env.step(actions)
        queues.append(info["total_queue"])
        if r:
            rewards.append(sum(r.values()) / len(r))
        decisions += 1
        if max_decisions is not None and decisions >= max_decisions:
            break
    n = max(len(queues), 1)
    return {
        "controller": getattr(controller, "name", controller.__class__.__name__),
        "agents": len(env.agent_ids),
        "steps": info.get("step"),
        "final_average_travel_time": info.get("average_travel_time"),
        "final_vehicle_count": info.get("vehicle_count"),
        "mean_total_queue": sum(queues) / n,
        "mean_reward": (sum(rewards) / len(rewards)) if rewards else 0.0,
    }
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/eval/test_runner.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/eval/__init__.py src/traffic_rl/eval/runner.py tests/eval/test_runner.py
git commit -m "feat: episode runner with comparison metrics"
```

### Task 12: Baseline entry script

**Files:**
- Create: `scripts/run_baseline.py`

Not TDD (Docker entry; logic is tested via `run_episode`).

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Run one baseline controller on a CityFlow scenario; save metrics + replay.

Inside Docker:
  make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/run_baseline.py max_pressure full"
controller in {fixed_time, max_pressure, random}; area in {subarea, full}.
"""
import json, sys
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import MaxPressureController
from traffic_rl.agents.random_agent import RandomController
from traffic_rl.eval.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "max_pressure"
    area = sys.argv[2] if len(sys.argv) > 2 else "full"
    data_dir = ROOT / "data" / "danang"
    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
           "roadnetLogFile": "replay_roadnet_{}.json".format(area),
           "replayLogFile": "replay_{}_{}.txt".format(which, area)}
    cfg_path = results_dir / "config_{}.json".format(which)
    cfg_path.write_text(json.dumps(cfg, indent=2))

    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))
    env = MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                               action_interval=10, max_steps=3600,
                               yellow_time=3, min_green=10)
    ctrl = {"fixed_time": lambda: FixedTimeController(env.num_actions),
            "max_pressure": lambda: MaxPressureController(rn),
            "random": lambda: RandomController(env.num_actions, seed=0)}[which]()

    metrics = run_episode(env, ctrl)
    metrics["area"] = area
    (results_dir / "metrics_{}.json".format(which)).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke each baseline in Docker** (after Phase A produced the full net)

Run:
```bash
make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_baseline.py max_pressure full"
make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_baseline.py random full"
make cf-run CMD="pip install dataclasses numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_baseline.py fixed_time full"
```
Expected: each prints metrics JSON and writes `results/full/metrics_<which>.json`. Max-Pressure's `final_average_travel_time` should be **lower** than Random's (sanity check).

- [ ] **Step 3: Commit**

```bash
git add scripts/run_baseline.py
git commit -m "feat: baseline runner entry script (fixed/max-pressure/random)"
```

---

## Phase D — Parameter-shared NumPy DQN

### Task 13: DQN network + replay buffer

**Files:**
- Create: `src/traffic_rl/agents/dqn.py`
- Test: `tests/agents/test_dqn.py`

The shared Q-net is a 2-hidden-layer ReLU MLP (`obs_dim → hidden → hidden → max_green`) with Adam and a target copy. All agents share it; their transitions pool into one buffer (parameter sharing). Action masking sets invalid Q-values to a large negative before argmax/target-max.

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
from traffic_rl.agents.dqn import SharedDQN, ReplayBuffer

def test_qvalues_shape():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    q = net.q_values(np.zeros((4, 5), dtype=np.float32))
    assert q.shape == (4, 3)

def test_greedy_respects_mask():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    obs = np.ones(5, dtype=np.float32)
    mask = np.array([False, False, True])     # only action 2 valid
    assert net.greedy_action(obs, mask) == 2

def test_train_step_reduces_loss_on_fixed_batch():
    net = SharedDQN(obs_dim=4, n_actions=2, hidden=16, seed=1, lr=1e-2)
    rng = np.random.RandomState(0)
    obs = rng.randn(32, 4).astype(np.float32)
    next_obs = rng.randn(32, 4).astype(np.float32)
    acts = rng.randint(0, 2, size=32)
    rew = rng.randn(32).astype(np.float32)
    done = np.zeros(32, dtype=np.float32)
    nmask = np.ones((32, 2), dtype=np.bool_)
    net.sync_target()
    first = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    for _ in range(200):
        last = net.train_step(obs, acts, rew, next_obs, done, nmask, gamma=0.9)
    assert last < first * 0.5                  # loss meaningfully decreased

def test_replay_buffer_sample_shapes():
    buf = ReplayBuffer(capacity=100, obs_dim=4, n_actions=2, seed=0)
    for i in range(50):
        buf.add(np.zeros(4, np.float32), 1, 0.5, np.ones(4, np.float32), 0.0,
                np.array([True, True]))
    batch = buf.sample(16)
    assert batch["obs"].shape == (16, 4)
    assert batch["actions"].shape == (16,)
    assert batch["next_mask"].shape == (16, 2)
    assert len(buf) == 50
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/agents/test_dqn.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the DQN**

```python
"""Parameter-shared DQN as a small from-scratch NumPy MLP (Adam + target net).

NumPy because the CityFlow Docker image is Python 3.6 (no modern PyTorch). The
simulator is the bottleneck, so a NumPy net costs little. 3.6-safe.
"""
import numpy as np

NEG = -1e9


def _relu(x):
    return np.maximum(x, 0.0)


class SharedDQN(object):
    def __init__(self, obs_dim, n_actions, hidden=64, lr=1e-3, seed=0):
        rng = np.random.RandomState(seed)

        def he(fan_in, fan_out):
            return (rng.randn(fan_in, fan_out) * np.sqrt(2.0 / fan_in)).astype(np.float32)

        self.W1, self.b1 = he(obs_dim, hidden), np.zeros(hidden, np.float32)
        self.W2, self.b2 = he(hidden, hidden), np.zeros(hidden, np.float32)
        self.W3, self.b3 = he(hidden, n_actions), np.zeros(n_actions, np.float32)
        self.params = ["W1", "b1", "W2", "b2", "W3", "b3"]
        self.lr = lr
        self._adam = {p: [np.zeros_like(getattr(self, p)),
                          np.zeros_like(getattr(self, p))] for p in self.params}
        self._t = 0
        self.sync_target()

    # ---- forward ----
    def _forward(self, X, W1, b1, W2, b2, W3, b3):
        z1 = X.dot(W1) + b1; a1 = _relu(z1)
        z2 = a1.dot(W2) + b2; a2 = _relu(z2)
        q = a2.dot(W3) + b3
        return q, (X, z1, a1, z2, a2)

    def q_values(self, X):
        X = np.atleast_2d(X).astype(np.float32)
        q, _ = self._forward(X, self.W1, self.b1, self.W2, self.b2, self.W3, self.b3)
        return q

    def _target_q(self, X):
        return self._forward(X, self.tW1, self.tb1, self.tW2, self.tb2,
                             self.tW3, self.tb3)[0]

    def greedy_action(self, obs, mask):
        q = self.q_values(obs)[0].copy()
        q[~np.asarray(mask, dtype=bool)] = NEG
        return int(np.argmax(q))

    def sync_target(self):
        self.tW1, self.tb1 = self.W1.copy(), self.b1.copy()
        self.tW2, self.tb2 = self.W2.copy(), self.b2.copy()
        self.tW3, self.tb3 = self.W3.copy(), self.b3.copy()

    # ---- training ----
    def train_step(self, obs, actions, rewards, next_obs, dones, next_mask, gamma=0.99):
        obs = obs.astype(np.float32); next_obs = next_obs.astype(np.float32)
        B = obs.shape[0]
        q, cache = self._forward(obs, self.W1, self.b1, self.W2, self.b2, self.W3, self.b3)
        X, z1, a1, z2, a2 = cache

        nq = self._target_q(next_obs).copy()
        nq[~np.asarray(next_mask, dtype=bool)] = NEG
        target = rewards + (1.0 - dones) * gamma * np.max(nq, axis=1)

        chosen = q[np.arange(B), actions]
        diff = (chosen - target).astype(np.float32)        # dL/dchosen (MSE/B form below)
        loss = float(np.mean(diff ** 2))

        # backprop only through chosen action
        dq = np.zeros_like(q)
        dq[np.arange(B), actions] = (2.0 / B) * diff
        dW3 = a2.T.dot(dq); db3 = dq.sum(axis=0)
        da2 = dq.dot(self.W3.T); dz2 = da2 * (z2 > 0)
        dW2 = a1.T.dot(dz2); db2 = dz2.sum(axis=0)
        da1 = dz2.dot(self.W2.T); dz1 = da1 * (z1 > 0)
        dW1 = X.T.dot(dz1); db1 = dz1.sum(axis=0)

        self._adam_step({"W1": dW1, "b1": db1, "W2": dW2, "b2": db2,
                         "W3": dW3, "b3": db3})
        return loss

    def _adam_step(self, grads, beta1=0.9, beta2=0.999, eps=1e-8):
        self._t += 1
        for p in self.params:
            g = grads[p]
            m, v = self._adam[p]
            m[:] = beta1 * m + (1 - beta1) * g
            v[:] = beta2 * v + (1 - beta2) * (g * g)
            mhat = m / (1 - beta1 ** self._t)
            vhat = v / (1 - beta2 ** self._t)
            setattr(self, p, getattr(self, p) - self.lr * mhat / (np.sqrt(vhat) + eps))

    # ---- checkpoint ----
    def save(self, path):
        np.savez(path, **{p: getattr(self, p) for p in self.params})

    def load(self, path):
        d = np.load(path)
        for p in self.params:
            setattr(self, p, d[p].astype(np.float32))
        self.sync_target()


class ReplayBuffer(object):
    def __init__(self, capacity, obs_dim, n_actions, seed=0):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), np.float32)
        self.actions = np.zeros(capacity, np.int64)
        self.rewards = np.zeros(capacity, np.float32)
        self.dones = np.zeros(capacity, np.float32)
        self.next_mask = np.zeros((capacity, n_actions), np.bool_)
        self._rng = np.random.RandomState(seed)
        self._n = 0; self._i = 0

    def add(self, obs, action, reward, next_obs, done, next_mask):
        i = self._i
        self.obs[i] = obs; self.next_obs[i] = next_obs
        self.actions[i] = action; self.rewards[i] = reward; self.dones[i] = done
        self.next_mask[i] = next_mask
        self._i = (i + 1) % self.capacity
        self._n = min(self._n + 1, self.capacity)

    def sample(self, batch_size):
        idx = self._rng.randint(0, self._n, size=batch_size)
        return {"obs": self.obs[idx], "actions": self.actions[idx],
                "rewards": self.rewards[idx], "next_obs": self.next_obs[idx],
                "dones": self.dones[idx], "next_mask": self.next_mask[idx]}

    def __len__(self):
        return self._n
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/agents/test_dqn.py -v`
Expected: 4 passed. (If `test_train_step_reduces_loss` is flaky, the gradient is wrong — debug before moving on; do not loosen the assertion.)

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/dqn.py tests/agents/test_dqn.py
git commit -m "feat: parameter-shared NumPy DQN (Adam, target net) + replay buffer"
```

### Task 14: DQN controller (greedy policy wrapper)

**Files:**
- Create append to: `src/traffic_rl/agents/dqn.py` (add `DQNController`)
- Test: extend `tests/agents/test_dqn.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from traffic_rl.agents.dqn import DQNController, SharedDQN

def test_dqn_controller_greedy_actions_are_masked():
    net = SharedDQN(obs_dim=5, n_actions=3, hidden=8, seed=0)
    ctrl = DQNController(net, agent_ids=["A"])
    import numpy as np
    ctx = {"observations": {"A": np.ones(5, np.float32)},
           "waiting_counts": {}, "action_masks": {"A": np.array([True, False, False])}}
    assert ctrl.act(ctx) == {"A": 0}          # only valid action
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/agents/test_dqn.py::test_dqn_controller_greedy_actions_are_masked -v`
Expected: FAIL — `DQNController` undefined.

- [ ] **Step 3: Implement** (append to `dqn.py`)

```python
from traffic_rl.agents.base import Controller


class DQNController(Controller):
    """Greedy (eval-time) wrapper around a trained SharedDQN."""
    name = "DQN"

    def __init__(self, net, agent_ids):
        self.net = net
        self.agent_ids = list(agent_ids)

    def act(self, context):
        obs = context["observations"]; masks = context["action_masks"]
        return {a: self.net.greedy_action(obs[a], masks[a]) for a in self.agent_ids}
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/agents/test_dqn.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/dqn.py tests/agents/test_dqn.py
git commit -m "feat: greedy DQNController for evaluation"
```

### Task 15: Training config

**Files:**
- Create: `configs/training.yaml`

- [ ] **Step 1: Write the config**

```yaml
# DQN parameter-sharing training hyperparameters
episodes: 100
max_steps: 3600          # CityFlow seconds per episode
action_interval: 10      # decision every 10 sim-seconds
yellow_time: 3
min_green: 10
hidden: 64
lr: 0.001
gamma: 0.99
batch_size: 64
buffer_capacity: 100000
train_start: 1000        # min transitions before learning
target_sync: 500         # train-steps between target syncs
epsilon_start: 1.0
epsilon_end: 0.05
epsilon_decay_steps: 50000   # linear decay over this many decisions
seed: 42
```

- [ ] **Step 2: Commit**

```bash
git add configs/training.yaml
git commit -m "chore: DQN training hyperparameter config"
```

### Task 16: Training loop

**Files:**
- Create: `src/traffic_rl/train/__init__.py` (empty)
- Create: `src/traffic_rl/train/trainer.py`
- Test: `tests/train/test_trainer.py`

The trainer pools all agents' transitions into one buffer (parameter sharing), uses epsilon-greedy with per-agent masks, syncs the target periodically, logs per-episode stats, and checkpoints. It is engine-agnostic (tested with `FakeEngine`, run for real with `CityFlowEngine`).

- [ ] **Step 1: Write the failing test**

```python
import json
import numpy as np
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.train.trainer import train
from tests.conftest import FakeEngine

def _net(tmp_path):
    data = {
        "intersections": [{
            "id": "A", "virtual": False, "roads": ["rin", "rout"],
            "roadLinks": [{"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 0, "endLaneIndex": 0}]},
                          {"startRoad": "rin", "endRoad": "rout",
                           "laneLinks": [{"startLaneIndex": 1, "endLaneIndex": 0}]}],
            "trafficLight": {"lightphases": [
                {"time": 39, "availableRoadLinks": [0]},
                {"time": 6, "availableRoadLinks": []},
                {"time": 39, "availableRoadLinks": [1]}]},
        }],
        "roads": [{"id": "rin", "startIntersection": "X", "endIntersection": "A", "lanes": [{}, {}]},
                  {"id": "rout", "startIntersection": "A", "endIntersection": "Y", "lanes": [{}]}],
    }
    p = tmp_path / "rn.json"; p.write_text(json.dumps(data)); return RoadNet.load(str(p))

def _env_factory(tmp_path):
    rn = _net(tmp_path)
    def make():
        return MultiAgentTrafficEnv(rn, FakeEngine(waiting_counts={"rin_0": 1, "rin_1": 1}),
                                    action_interval=2, yellow_time=1, min_green=0, max_steps=6)
    return make

def test_train_runs_and_checkpoints(tmp_path):
    cfg = {"episodes": 2, "max_steps": 6, "hidden": 8, "lr": 1e-3, "gamma": 0.9,
           "batch_size": 8, "buffer_capacity": 1000, "train_start": 4,
           "target_sync": 5, "epsilon_start": 1.0, "epsilon_end": 0.1,
           "epsilon_decay_steps": 20, "seed": 0}
    ckpt = tmp_path / "dqn.npz"; log = tmp_path / "log.json"
    net = train(_env_factory(tmp_path), cfg, ckpt_path=str(ckpt), log_path=str(log))
    assert ckpt.exists()
    rec = json.loads(log.read_text())
    assert len(rec["episodes"]) == 2
    assert "mean_reward" in rec["episodes"][0]
    # net is usable
    q = net.q_values(np.zeros((1, net.W1.shape[0]), np.float32))
    assert q.shape[1] == net.W3.shape[1]
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/train/test_trainer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the trainer**

```python
"""Parameter-shared DQN training loop over MultiAgentTrafficEnv. 3.6-safe.

Pools every agent's transition into one replay buffer and trains one shared
network (parameter sharing). Engine-agnostic via the env's factory.
"""
import json

import numpy as np

from traffic_rl.agents.dqn import SharedDQN, ReplayBuffer


def _epsilon(step, cfg):
    frac = min(1.0, float(step) / max(1, cfg["epsilon_decay_steps"]))
    return cfg["epsilon_start"] + frac * (cfg["epsilon_end"] - cfg["epsilon_start"])


def train(env_factory, cfg, ckpt_path, log_path):
    env = env_factory()
    obs_dim = env.obs_dim
    n_actions = env.encoder.max_green
    rng = np.random.RandomState(cfg["seed"])

    net = SharedDQN(obs_dim, n_actions, hidden=cfg["hidden"], lr=cfg["lr"], seed=cfg["seed"])
    buf = ReplayBuffer(cfg["buffer_capacity"], obs_dim, n_actions, seed=cfg["seed"])
    masks = env.action_masks()

    decisions = 0
    train_steps = 0
    log = {"episodes": []}

    for ep in range(cfg["episodes"]):
        obs = env.reset()
        done = False
        ep_rewards, ep_queues, ep_losses = [], [], []
        while not done:
            eps = _epsilon(decisions, cfg)
            actions = {}
            for a in env.agent_ids:
                if rng.rand() < eps:
                    valid = np.where(masks[a])[0]
                    actions[a] = int(rng.choice(valid))
                else:
                    actions[a] = net.greedy_action(obs[a], masks[a])
            next_obs, rewards, done, info = env.step(actions)
            for a in env.agent_ids:
                buf.add(obs[a], actions[a], rewards[a], next_obs[a],
                        1.0 if done else 0.0, masks[a])
            obs = next_obs
            decisions += 1
            ep_rewards.append(sum(rewards.values()) / len(rewards))
            ep_queues.append(info["total_queue"])

            if len(buf) >= cfg["train_start"]:
                b = buf.sample(cfg["batch_size"])
                loss = net.train_step(b["obs"], b["actions"], b["rewards"],
                                      b["next_obs"], b["dones"], b["next_mask"],
                                      gamma=cfg["gamma"])
                ep_losses.append(loss)
                train_steps += 1
                if train_steps % cfg["target_sync"] == 0:
                    net.sync_target()

        log["episodes"].append({
            "episode": ep,
            "mean_reward": float(np.mean(ep_rewards)) if ep_rewards else 0.0,
            "mean_total_queue": float(np.mean(ep_queues)) if ep_queues else 0.0,
            "mean_loss": float(np.mean(ep_losses)) if ep_losses else 0.0,
            "final_average_travel_time": info.get("average_travel_time"),
            "epsilon": _epsilon(decisions, cfg),
        })
        net.save(ckpt_path)
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2)

    return net
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/train/test_trainer.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/train/__init__.py src/traffic_rl/train/trainer.py tests/train/test_trainer.py
git commit -m "feat: parameter-shared DQN training loop with checkpoint + log"
```

### Task 17: Training entry script + real run

**Files:**
- Create: `scripts/train_dqn.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Train the shared DQN on a CityFlow scenario (run inside Docker).

  make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/train_dqn.py full"
"""
import json, sys
from pathlib import Path

import yaml

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.train.trainer import train

ROOT = Path(__file__).resolve().parent.parent


def main():
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    cfg = yaml.safe_load((ROOT / "configs" / "training.yaml").read_text())
    data_dir = ROOT / "data" / "danang"
    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    def env_factory():
        run_cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
                   "roadnetFile": "roadnet_{}.json".format(area),
                   "flowFile": "flow_{}.json".format(area),
                   "rlTrafficLight": True, "laneChange": False, "saveReplay": False}
        cfg_path = results_dir / "config_train.json"
        cfg_path.write_text(json.dumps(run_cfg))
        return MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                                    action_interval=cfg["action_interval"],
                                    max_steps=cfg["max_steps"],
                                    yellow_time=cfg["yellow_time"],
                                    min_green=cfg["min_green"])

    train(env_factory, cfg,
          ckpt_path=str(results_dir / "dqn_{}.npz".format(area)),
          log_path=str(results_dir / "train_log_{}.json".format(area)))
    print("Saved checkpoint + log to", results_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: the env factory recreates a `CityFlowEngine` each episode (cheap reset is fine; `train` calls `env.reset()` per episode but only builds the env once — the factory is called once in `train`). Keep `saveReplay: False` during training for speed.

- [ ] **Step 2: Short smoke run in Docker** (override episodes for a quick check)

Run:
```bash
make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; PYTHONPATH=src python3 -c \"
import yaml, json
from pathlib import Path
cfg=yaml.safe_load(open('configs/training.yaml')); cfg['episodes']=2
open('configs/training.yaml','w').write(yaml.safe_dump(cfg))
\"; PYTHONPATH=src python3 scripts/train_dqn.py full"
```
Expected: completes 2 episodes, writes `results/full/dqn_full.npz` + `train_log_full.json`. (Restore `episodes: 100` afterward via git checkout or edit.)

- [ ] **Step 3: Full training run** (long; emulated CityFlow is slow — expect this to take a while)

Run:
```bash
make cf-run CMD="pip install dataclasses numpy pyyaml >/dev/null 2>&1; PYTHONPATH=src python3 scripts/train_dqn.py full"
```
Expected: `train_log_full.json` shows `mean_total_queue` trending down and `mean_reward` trending up across episodes. If it diverges (loss explodes / queue grows), STOP and tune `lr` / `epsilon_decay_steps` in `configs/training.yaml` before continuing — record what was changed.

- [ ] **Step 4: Commit script (checkpoints/logs are gitignored data)**

```bash
git add scripts/train_dqn.py
git commit -m "feat: DQN training entry script"
```

---

## Phase E — Full comparison & results

### Task 18: Comparison aggregator + plots

**Files:**
- Create: `src/traffic_rl/eval/compare.py`
- Test: `tests/eval/test_compare.py`

`compare.py` has two parts: a pure `aggregate(metrics_list)` (testable, no Docker/plot) and a `plot_*` step (matplotlib, exercised only by the entry script). Test the pure part.

- [ ] **Step 1: Write the failing test**

```python
from traffic_rl.eval.compare import aggregate

def test_aggregate_builds_table_and_best():
    rows = [
        {"controller": "Random", "final_average_travel_time": 400.0, "mean_total_queue": 50},
        {"controller": "FixedTime", "final_average_travel_time": 360.0, "mean_total_queue": 40},
        {"controller": "MaxPressure", "final_average_travel_time": 300.0, "mean_total_queue": 30},
        {"controller": "DQN", "final_average_travel_time": 290.0, "mean_total_queue": 28},
    ]
    out = aggregate(rows)
    assert out["best_controller"] == "DQN"      # lowest travel time
    assert out["table"][0]["controller"] in {"Random", "FixedTime", "MaxPressure", "DQN"}
    # improvement of DQN vs FixedTime in %
    assert round(out["improvement_vs_fixed_pct"], 2) == round((360.0 - 290.0) / 360.0 * 100, 2)
```

- [ ] **Step 2: Run to confirm failure**

Run: `python3 -m pytest tests/eval/test_compare.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** (pure part + plotting helpers)

```python
"""Aggregate per-controller metrics into a comparison table + plots. 3.6-safe core."""
import json


def aggregate(rows):
    table = sorted(rows, key=lambda r: r["final_average_travel_time"])
    best = table[0]["controller"]
    by = {r["controller"]: r["final_average_travel_time"] for r in rows}
    improvement = None
    if "FixedTime" in by and "DQN" in by and by["FixedTime"]:
        improvement = (by["FixedTime"] - by["DQN"]) / by["FixedTime"] * 100.0
    return {"table": table, "best_controller": best,
            "improvement_vs_fixed_pct": improvement}


def write_report(rows, out_json):
    report = aggregate(rows)
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2)
    return report


def plot_metrics(rows, out_png):
    """Bar chart of avg travel time + mean queue per controller."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = [r["controller"] for r in rows]
    tt = [r["final_average_travel_time"] for r in rows]
    q = [r.get("mean_total_queue", 0) for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].bar(names, tt); ax[0].set_title("Avg travel time (s) — lower is better")
    ax[1].bar(names, q); ax[1].set_title("Mean total queue — lower is better")
    for a in ax:
        a.tick_params(axis="x", rotation=20)
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)


def plot_training_curve(train_log, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    eps = train_log["episodes"]
    x = [e["episode"] for e in eps]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(x, [e["mean_reward"] for e in eps]); ax[0].set_title("Mean reward / episode")
    ax[1].plot(x, [e["mean_total_queue"] for e in eps]); ax[1].set_title("Mean queue / episode")
    for a in ax:
        a.set_xlabel("episode")
    fig.tight_layout(); fig.savefig(out_png, dpi=120); plt.close(fig)
```

- [ ] **Step 4: Run to confirm pass**

Run: `python3 -m pytest tests/eval/test_compare.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/eval/compare.py tests/eval/test_compare.py
git commit -m "feat: comparison aggregator + metric/training plots"
```

### Task 19: Comparison entry script + final results

**Files:**
- Create: `scripts/run_comparison.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Run all four controllers on the same scenario and produce the comparison.

  make cf-run CMD="pip install dataclasses numpy pyyaml matplotlib >/dev/null 2>&1; \
    PYTHONPATH=src python3 scripts/run_comparison.py full"
Loads the trained DQN checkpoint from results/<area>/dqn_<area>.npz.
"""
import json, sys
from pathlib import Path

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.agents.max_pressure import MaxPressureController
from traffic_rl.agents.random_agent import RandomController
from traffic_rl.agents.dqn import SharedDQN, DQNController
from traffic_rl.eval.runner import run_episode
from traffic_rl.eval import compare

ROOT = Path(__file__).resolve().parent.parent


def _env(rn, area, tag, results_dir):
    cfg = {"interval": 1.0, "seed": 0, "dir": "data/danang/",
           "roadnetFile": "roadnet_{}.json".format(area),
           "flowFile": "flow_{}.json".format(area),
           "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
           "roadnetLogFile": "replay_roadnet_{}.json".format(area),
           "replayLogFile": "replay_{}_{}.txt".format(tag, area)}
    cfg_path = results_dir / "config_cmp_{}.json".format(tag)
    cfg_path.write_text(json.dumps(cfg))
    return MultiAgentTrafficEnv(rn, CityFlowEngine(str(cfg_path)),
                                action_interval=10, max_steps=3600,
                                yellow_time=3, min_green=10)


def main():
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    data_dir = ROOT / "data" / "danang"
    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)
    rn = RoadNet.load(str(data_dir / "roadnet_{}.json".format(area)))

    rows = []
    # baselines
    for tag, make in [
        ("fixed_time", lambda e: FixedTimeController(e.num_actions)),
        ("max_pressure", lambda e: MaxPressureController(rn)),
        ("random", lambda e: RandomController(e.num_actions, seed=0))]:
        env = _env(rn, area, tag, results_dir)
        rows.append(run_episode(env, make(env)))

    # trained DQN
    env = _env(rn, area, "dqn", results_dir)
    net = SharedDQN(env.obs_dim, env.encoder.max_green)
    net.load(str(results_dir / "dqn_{}.npz".format(area)))
    rows.append(run_episode(env, DQNController(net, env.agent_ids)))

    report = compare.write_report(rows, str(results_dir / "comparison.json"))
    compare.plot_metrics(rows, str(results_dir / "comparison_metrics.png"))
    train_log = results_dir / "train_log_{}.json".format(area)
    if train_log.exists():
        compare.plot_training_curve(json.loads(train_log.read_text()),
                                    str(results_dir / "training_curve.png"))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the full comparison in Docker**

Run:
```bash
make cf-run CMD="pip install dataclasses numpy pyyaml matplotlib >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_comparison.py full"
```
Expected: writes `results/full/comparison.json`, `comparison_metrics.png`, `training_curve.png`, and per-controller replay files. The printed report should show **DQN and Max-Pressure beating Fixed-Time and Random** on `final_average_travel_time`. If DQN is worse than Fixed-Time, that's a real result to report — but first sanity-check the checkpoint loaded and training converged (Task 17 Step 3).

- [ ] **Step 3: Commit**

```bash
git add scripts/run_comparison.py
git commit -m "feat: full four-controller comparison entry script + plots"
```

### Task 20: Run full local + docker test suites (gate)

- [ ] **Step 1: Local suite**

Run: `make test`
Expected: all green (Plan-1 18 + new tests; ~35+ passed, docker deselected).

- [ ] **Step 2: Docker engine tests**

Run: `make cf-test`
Expected: docker-marked tests pass (engine smoke). If `tests/sim/test_engine_docker.py` needs the new env API, update it minimally.

- [ ] **Step 3: Confirm 3.6 import of all in-container modules**

Run:
```bash
make cf-run CMD="PYTHONPATH=src python3 -c 'import traffic_rl.sim.multi_agent_env, traffic_rl.agents.dqn, traffic_rl.train.trainer, traffic_rl.eval.runner, traffic_rl.eval.compare; print(\"3.6 imports OK\")'"
```
Expected: prints `3.6 imports OK` (no `from __future__ import annotations`, no f-string-only-3.6 issues, dataclasses available).

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "test: green full + docker suites for Plan 2"
```

---

## Self-review checklist (run before handing off)

- **Spec coverage:** P3 baselines (Max-Pressure ✓ Task 9, Random ✓ Task 10, Fixed-Time ✓ Task 8); P4 MARL DQN param-sharing (✓ Tasks 13–17); metrics avg-travel-time/throughput-proxy/queue (✓ runner Task 11 + compare Task 18); full-network scope (✓ Phase A). Min-green + yellow + signed pressure + normalized/padded obs + action masks (✓ Tasks 5–7). UI dashboard/replay is **out of scope here → Plan 3**.
- **Type consistency:** controller interface `act(context)` is uniform (Tasks 8–10, 14); env exposes `num_actions`, `obs_dim`, `encoder.max_green`, `action_masks()`, `current_waiting_counts()` (Task 7) and they are used consistently by runner/trainer/comparison.
- **Throughput note:** CityFlow's older API exposes `average_travel_time` (over finished vehicles) and running `vehicle_count`, but not a clean finished-count; this plan reports avg travel time (primary), mean queue, and final running count rather than a possibly-misleading throughput number. Documented as a metric choice for the thesis.

## Out of scope (→ Plan 3)
- Streamlit comparison dashboard and embedded CityFlow web replay launcher.
- Chapter 4 write-up from the generated `comparison.json` + plots.
- Coordination/communication between agents (future work, per spec §10).
