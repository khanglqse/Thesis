# Da Nang CityFlow Foundation (P0–P2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation for the thesis: a working CityFlow simulation of central Da Nang generated from OSM, exposed as a multi-agent traffic-signal environment, validated end-to-end with a Fixed-Time controller and a CityFlow replay.

**Architecture:** Network pipeline OSM → SUMO (`netconvert`, local) → CityFlow `roadnet.json` (converter, in Docker). Synthetic motorbike-heavy `flow.json` generated in pure Python. The CityFlow C++ engine runs only inside Docker (`cityflowproject/cityflow:latest`); it is hidden behind a thin `CityFlowEngine` wrapper. All non-engine logic (flow generation, roadnet parsing, per-intersection observation/reward) is pure Python and unit-tested locally. The multi-agent env composes these via a duck-typed engine interface so it is testable with a fake engine.

**Tech Stack:** Python 3.13, CityFlow (Docker), SUMO `netconvert`/`osmGet.py` (local, Homebrew), pytest, PyYAML, NumPy. Docker image `cityflowproject/cityflow:latest`.

---

## Environment facts (verified 2026-06-01)

- `cityflow` is **not** pip-installable; it works only inside `cityflowproject/cityflow:latest`. The image is `linux/amd64` (runs emulated on this arm64 Mac — correct but slow; fine for dev, train heavy runs on a server later).
- CityFlow SUMO→CityFlow converter lives at `/home/cityflow/tools/converter/converter.py` inside the image.
- `netconvert` (SUMO 1.24) is at `/opt/homebrew/bin/netconvert`; SUMO tools at `/opt/homebrew/share/sumo/tools/` (e.g. `osmGet.py`). `SUMO_HOME` is unset — set it to `/opt/homebrew/share/sumo`.
- OSM already imported via `scripts/download_osm_danang.py` (osmnx graphml, for inspection only). `netconvert` needs raw `.osm` XML, downloaded separately with `osmGet.py` (Task 3).
- Central Da Nang bbox: `(west, south, east, north) = (108.12, 16.00, 108.28, 16.08)`, ~37 OSM `traffic_signals`.

## File structure (created by this plan)

```
traffic-rl/
├── Makefile                       # docker + test helpers (single source of dev commands)
├── pyproject.toml                 # package + pytest config
├── configs/
│   └── network.yaml               # bboxes (subarea + full), netconvert/flow params
├── src/traffic_rl/
│   ├── __init__.py
│   ├── network/
│   │   ├── __init__.py
│   │   ├── osm_to_sumo.py         # build netconvert command + run it
│   │   ├── sumo_to_cityflow.py    # run converter.py inside Docker
│   │   ├── roadnet.py             # parse roadnet.json: intersections, roads, adjacency
│   │   └── flow_gen.py            # generate flow.json (pure python, motorbike-heavy)
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── engine.py              # CityFlowEngine thin wrapper (imports cityflow)
│   │   ├── intersection.py        # per-intersection observation + pressure reward (pure)
│   │   └── multi_agent_env.py     # MultiAgentTrafficEnv over a duck-typed engine
│   └── agents/
│       ├── __init__.py
│       └── fixed_time.py          # FixedTimeController
├── scripts/
│   ├── download_osm.py            # osmGet.py wrapper -> data/osm/danang.osm.xml
│   └── run_fixed_time.py          # end-to-end: build sim, run fixed-time, save replay+metrics
├── data/
│   ├── osm/                       # raw .osm (gitignored, large)
│   ├── sumo/                      # .net.xml (gitignored)
│   └── danang/                    # roadnet.json, flow.json (subarea + full)
└── tests/
    ├── conftest.py
    ├── test_smoke.py
    ├── network/{test_osm_to_sumo.py,test_roadnet.py,test_flow_gen.py}
    └── sim/{test_intersection.py,test_multi_agent_env.py}
```

> Engine-dependent integration tests are marked `@pytest.mark.docker` and run via `make cf-test`; pure-python tests run via `make test` locally.

---

## Task 1: Project scaffolding + pytest

**Files:**
- Create: `pyproject.toml`, `src/traffic_rl/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing smoke test**

`tests/test_smoke.py`:
```python
from traffic_rl import __version__


def test_package_importable():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'traffic_rl'`.

- [ ] **Step 3: Create the package and config**

`src/traffic_rl/__init__.py`:
```python
__version__ = "0.1.0"
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "traffic-rl"
version = "0.1.0"
description = "Da Nang traffic signal control with MARL on CityFlow"
requires-python = ">=3.10"
dependencies = ["numpy", "pyyaml"]

[project.optional-dependencies]
dev = ["pytest"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
markers = [
    "docker: integration tests that require the CityFlow Docker image",
]
addopts = "-m 'not docker'"
```

`tests/conftest.py`:
```python
# Shared fixtures live here; intentionally minimal for now.
```

- [ ] **Step 4: Append data dirs to `.gitignore`**

Append to `.gitignore`:
```
# Generated simulation data — all regenerable from scripts (OSM, nets, roadnet, flow, replay)
data/
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `python3 -m pytest tests/test_smoke.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/traffic_rl/__init__.py tests/conftest.py tests/test_smoke.py .gitignore
git commit -m "chore: scaffold traffic_rl package + pytest"
```

---

## Task 2: Makefile with Docker + test helpers

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile**

`Makefile`:
```makefile
SHELL := /bin/bash
CF_IMAGE := cityflowproject/cityflow:latest
SUMO_HOME ?= /opt/homebrew/share/sumo
PWD := $(shell pwd)

# Run an arbitrary command inside the CityFlow container with the repo mounted.
# Usage: make cf-run CMD="python3 scripts/foo.py"
cf-run:
	docker run --rm -v "$(PWD)":/work -w /work $(CF_IMAGE) sh -lc '$(CMD)'

# Run pure-python unit tests locally (cityflow NOT required).
test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest -m 'not docker' -v

# Run engine integration tests inside the CityFlow container.
cf-test:
	docker run --rm -v "$(PWD)":/work -w /work $(CF_IMAGE) \
		sh -lc 'pip install pytest pyyaml numpy >/dev/null 2>&1; python3 -m pytest -m docker -v -o addopts="" -o pythonpath=src'

# Smoke-check that cityflow imports inside the container.
cf-smoke:
	docker run --rm $(CF_IMAGE) python3 -c 'import cityflow; print("cityflow OK")'

.PHONY: cf-run test cf-test cf-smoke
```

- [ ] **Step 2: Verify the cityflow smoke target works**

Run: `make cf-smoke`
Expected: prints `cityflow OK` (after a platform warning line, which is fine).

- [ ] **Step 3: Verify local tests still pass through the Makefile**

Run: `make test`
Expected: the Task 1 smoke test passes (1 passed, deselected docker tests).

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile docker + test helpers"
```

---

## Task 3: Download raw OSM XML for Da Nang

**Files:**
- Create: `scripts/download_osm.py`, `configs/network.yaml`

- [ ] **Step 1: Create the network config**

`configs/network.yaml`:
```yaml
# Bounding boxes: [west, south, east, north]
bbox:
  # Small validation sub-area (a few signalized intersections near the center).
  subarea: [108.215, 16.045, 108.235, 16.065]
  # Full central Da Nang.
  full: [108.12, 16.00, 108.28, 16.08]

netconvert:
  # Options applied when converting OSM -> SUMO net (see osm_to_sumo.py).
  tls_default_type: actuated

flow:
  start_time: 0
  end_time: 3600        # 1 hour of generated demand
  num_flows: 300        # number of distinct route-flows
  route_length: 4       # roads per generated route (random walk depth)
  seed: 42
  # Vehicle mix: motorbike-heavy, typical of Vietnam.
  motorbike_ratio: 0.75
```

- [ ] **Step 2: Create the OSM download script**

`scripts/download_osm.py`:
```python
#!/usr/bin/env python3
"""Download raw OSM XML for a Da Nang bbox using SUMO's osmGet.py.

netconvert needs raw .osm XML (osmnx graphml is only for inspection).
Usage: python3 scripts/download_osm.py [subarea|full]
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUMO_HOME = os.environ.get("SUMO_HOME", "/opt/homebrew/share/sumo")


def main() -> int:
    area = sys.argv[1] if len(sys.argv) > 1 else "subarea"
    cfg = yaml.safe_load((ROOT / "configs" / "network.yaml").read_text())
    w, s, e, n = cfg["bbox"][area]

    out_dir = ROOT / "data" / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"danang_{area}"

    osm_get = Path(SUMO_HOME) / "tools" / "osmGet.py"
    cmd = [
        sys.executable, str(osm_get),
        "--bbox", f"{w},{s},{e},{n}",
        "--output-dir", str(out_dir),
        "--prefix", prefix,
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, env={**os.environ, "SUMO_HOME": SUMO_HOME})

    produced = out_dir / f"{prefix}_bbox.osm.xml"
    if not produced.exists():
        print(f"ERROR: expected {produced} not found", file=sys.stderr)
        return 1
    print(f"Saved: {produced} ({produced.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Download the sub-area OSM**

Run: `SUMO_HOME=/opt/homebrew/share/sumo python3 scripts/download_osm.py subarea`
Expected: prints `Saved: .../data/osm/danang_subarea_bbox.osm.xml (<N> bytes)` with N > 0.

- [ ] **Step 4: Commit (config + script only; .osm is gitignored)**

```bash
git add scripts/download_osm.py configs/network.yaml
git commit -m "feat(network): add raw OSM download via osmGet.py"
```

---

## Task 4: OSM → SUMO network (`netconvert`)

**Files:**
- Create: `src/traffic_rl/network/__init__.py`, `src/traffic_rl/network/osm_to_sumo.py`, `tests/network/test_osm_to_sumo.py`

- [ ] **Step 1: Write the failing test for the command builder**

`tests/network/test_osm_to_sumo.py`:
```python
from traffic_rl.network.osm_to_sumo import build_netconvert_command


def test_command_includes_osm_input_and_output():
    cmd = build_netconvert_command("in.osm.xml", "out.net.xml", tls_default_type="actuated")
    assert cmd[0] == "netconvert"
    assert "--osm-files" in cmd
    assert cmd[cmd.index("--osm-files") + 1] == "in.osm.xml"
    assert "--output-file" in cmd
    assert cmd[cmd.index("--output-file") + 1] == "out.net.xml"


def test_command_imports_and_joins_traffic_lights():
    cmd = build_netconvert_command("in.osm.xml", "out.net.xml", tls_default_type="actuated")
    # Import OSM signals, merge clustered junctions, keep only car-drivable edges.
    assert "--tls.guess-signals" in cmd
    assert "--junctions.join" in cmd
    assert "--tls.default-type" in cmd
    assert cmd[cmd.index("--tls.default-type") + 1] == "actuated"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/network/test_osm_to_sumo.py -v`
Expected: FAIL — module `traffic_rl.network.osm_to_sumo` does not exist.

- [ ] **Step 3: Implement the command builder + runner**

`src/traffic_rl/network/__init__.py`:
```python
```

`src/traffic_rl/network/osm_to_sumo.py`:
```python
"""Convert raw OSM XML to a SUMO .net.xml using netconvert."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List


def build_netconvert_command(
    osm_file: str, output_file: str, tls_default_type: str = "actuated"
) -> List[str]:
    """Build the netconvert argv for a clean, signal-aware urban network."""
    return [
        "netconvert",
        "--osm-files", osm_file,
        "--output-file", output_file,
        # Keep only car-drivable roads; drop isolated/duplicate geometry.
        "--keep-edges.by-vclass", "passenger",
        "--remove-edges.isolated", "true",
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        # Merge OSM's clustered nodes into single real junctions.
        "--junctions.join", "true",
        # Import + consolidate traffic signals from OSM.
        "--tls.guess-signals", "true",
        "--tls.join", "true",
        "--tls.discard-simple", "true",
        "--tls.default-type", tls_default_type,
        "--no-turnarounds", "true",
    ]


def run_netconvert(osm_file: str, output_file: str, tls_default_type: str = "actuated") -> Path:
    """Run netconvert; return the output path. Raises on failure."""
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_netconvert_command(osm_file, output_file, tls_default_type)
    sumo_home = os.environ.get("SUMO_HOME", "/opt/homebrew/share/sumo")
    subprocess.run(cmd, check=True, env={**os.environ, "SUMO_HOME": sumo_home})
    if not out.exists():
        raise RuntimeError(f"netconvert did not produce {out}")
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/network/test_osm_to_sumo.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Actually convert the sub-area and inspect signal count**

Run:
```bash
SUMO_HOME=/opt/homebrew/share/sumo python3 -c "
from traffic_rl.network.osm_to_sumo import run_netconvert
run_netconvert('data/osm/danang_subarea_bbox.osm.xml', 'data/sumo/danang_subarea.net.xml')
"
grep -c "type=\"traffic_light\"" data/sumo/danang_subarea.net.xml
```
Expected: `data/sumo/danang_subarea.net.xml` created; the grep prints the number of signalized junctions (≥ 1). Record this number — it is the agent count for the sub-area.

- [ ] **Step 6: Commit (code only; .net.xml is gitignored)**

```bash
git add src/traffic_rl/network/__init__.py src/traffic_rl/network/osm_to_sumo.py tests/network/test_osm_to_sumo.py
git commit -m "feat(network): OSM -> SUMO net conversion via netconvert"
```

---

## Task 5: SUMO → CityFlow `roadnet.json` (converter in Docker)

**Files:**
- Create: `src/traffic_rl/network/sumo_to_cityflow.py`, `tests/network/test_sumo_to_cityflow.py`

- [ ] **Step 1: Write the failing test for the Docker command builder**

`tests/network/test_sumo_to_cityflow.py`:
```python
from traffic_rl.network.sumo_to_cityflow import build_converter_docker_command


def test_converter_command_mounts_repo_and_calls_converter():
    cmd = build_converter_docker_command(
        "data/sumo/danang_subarea.net.xml",
        "data/danang/roadnet_subarea.json",
        image="cityflowproject/cityflow:latest",
        workdir="/work",
    )
    joined = " ".join(cmd)
    assert cmd[0] == "docker"
    assert "run" in cmd and "--rm" in cmd
    assert "/work" in joined                       # repo mounted at /work
    # converter.py needs deps not in the image; they are pip-installed first.
    assert "pip install" in joined
    assert "sympy" in joined and "traci" in joined and "sumolib" in joined
    assert "/home/cityflow/tools/converter/converter.py" in joined
    assert "--sumonet data/sumo/danang_subarea.net.xml" in joined
    assert "--cityflownet data/danang/roadnet_subarea.json" in joined
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/network/test_sumo_to_cityflow.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the converter wrapper**

`src/traffic_rl/network/sumo_to_cityflow.py`:
```python
"""Run CityFlow's SUMO->CityFlow converter inside the CityFlow Docker image."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List

CONVERTER = "/home/cityflow/tools/converter/converter.py"
# converter.py imports sympy + traci/sumolib, which are not in the image.
DEPS = "sympy traci sumolib"


def build_converter_docker_command(
    sumo_net: str,
    cityflow_net: str,
    image: str = "cityflowproject/cityflow:latest",
    workdir: str = "/work",
    host_root: str | None = None,
) -> List[str]:
    """Build the `docker run` argv that converts a SUMO net to CityFlow roadnet."""
    host_root = host_root or os.getcwd()
    inner = (
        f"pip install {DEPS} >/dev/null 2>&1; "
        f"python3 {CONVERTER} --sumonet {sumo_net} --cityflownet {cityflow_net}"
    )
    return [
        "docker", "run", "--rm",
        "-v", f"{host_root}:{workdir}",
        "-w", workdir,
        image,
        "sh", "-lc", inner,
    ]


def run_converter(sumo_net: str, cityflow_net: str, image: str = "cityflowproject/cityflow:latest") -> Path:
    """Run the converter in Docker; return the roadnet path. Raises on failure."""
    out = Path(cityflow_net)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_converter_docker_command(sumo_net, cityflow_net, image=image)
    subprocess.run(cmd, check=True)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"converter did not produce non-empty {out}")
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/network/test_sumo_to_cityflow.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Actually convert the sub-area net to roadnet.json**

Run:
```bash
python3 -c "
from traffic_rl.network.sumo_to_cityflow import run_converter
run_converter('data/sumo/danang_subarea.net.xml', 'data/danang/roadnet_subarea.json')
"
python3 -c "
import json; d=json.load(open('data/danang/roadnet_subarea.json'))
inter=d['intersections']; sig=[i for i in inter if not i.get('virtual') and i.get('trafficLight')]
print('intersections:', len(inter), '| signalized:', len(sig), '| roads:', len(d['roads']))
"
```
Expected: `roadnet_subarea.json` created; prints intersection/road counts with `signalized ≥ 1`. If the converter errors on the platform, prepend `--platform linux/amd64` is already implicit via the image; if it fails, capture the error for debugging before proceeding.

- [ ] **Step 6: Commit**

```bash
git add src/traffic_rl/network/sumo_to_cityflow.py tests/network/test_sumo_to_cityflow.py
git commit -m "feat(network): SUMO -> CityFlow roadnet via dockerized converter"
```

---

## Task 6: Roadnet parsing + road adjacency

**Files:**
- Create: `src/traffic_rl/network/roadnet.py`, `tests/network/test_roadnet.py`

- [ ] **Step 1: Write the failing test**

`tests/network/test_roadnet.py`:
```python
import json

from traffic_rl.network.roadnet import RoadNet

SAMPLE = {
    "intersections": [
        {
            "id": "int_A", "virtual": False,
            "roads": ["road_in", "road_out"],
            "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": [1]}]},
            "roadLinks": [
                {"startRoad": "road_in", "endRoad": "road_out"},
            ],
        },
        {"id": "int_V", "virtual": True, "roads": ["road_out"]},
    ],
    "roads": [
        {"id": "road_in", "startIntersection": "int_V", "endIntersection": "int_A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "road_out", "startIntersection": "int_A", "endIntersection": "int_V",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


def test_signalized_intersections(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    assert rn.signalized_ids() == ["int_A"]
    assert rn.num_phases("int_A") == 2


def test_single_phase_junctions_are_not_agents(tmp_path):
    # The CityFlow converter emits a trivial 1-phase trafficLight for every
    # non-signalized junction. Those must NOT be treated as agents.
    sample = json.loads(json.dumps(SAMPLE))
    sample["intersections"].append({
        "id": "int_trivial", "virtual": False,
        "roads": ["road_in"],
        "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}]},
        "roadLinks": [],
    })
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(sample))
    rn = RoadNet.load(str(p))
    assert rn.signalized_ids() == ["int_A"]   # int_trivial (1 phase) excluded


def test_incoming_lane_ids(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    # CityFlow lane id convention: "<roadId>_<laneIndex>"
    assert rn.incoming_lanes("int_A") == ["road_in_0"]
    assert rn.outgoing_lanes("int_A") == ["road_out_0"]


def test_road_adjacency_for_routing(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    # road_in -> road_out is a valid turn (roadLink at int_A)
    assert rn.next_roads("road_in") == ["road_out"]
    assert rn.next_roads("road_out") == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/network/test_roadnet.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the roadnet parser**

`src/traffic_rl/network/roadnet.py`:
```python
"""Parse a CityFlow roadnet.json into convenient lookups for env + flow generation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RoadNet:
    intersections: List[dict]
    roads: List[dict]
    _by_id: Dict[str, dict]
    _road_by_id: Dict[str, dict]
    _next: Dict[str, List[str]]

    @classmethod
    def load(cls, path: str) -> "RoadNet":
        data = json.loads(open(path).read())
        by_id = {i["id"]: i for i in data["intersections"]}
        road_by_id = {r["id"]: r for r in data["roads"]}
        # Build road->road adjacency from every intersection's roadLinks.
        nxt: Dict[str, List[str]] = {r["id"]: [] for r in data["roads"]}
        for inter in data["intersections"]:
            for link in inter.get("roadLinks", []):
                start, end = link["startRoad"], link["endRoad"]
                if end not in nxt[start]:
                    nxt[start].append(end)
        return cls(data["intersections"], data["roads"], by_id, road_by_id, nxt)

    def signalized_ids(self) -> List[str]:
        # A real controllable signal has >1 phase. The CityFlow converter emits a
        # trivial single-phase trafficLight for every non-signalized junction;
        # those are excluded so they don't become bogus agents.
        return [
            i["id"] for i in self.intersections
            if not i.get("virtual") and i.get("trafficLight")
            and len(i["trafficLight"].get("lightphases", [])) > 1
        ]

    def num_phases(self, inter_id: str) -> int:
        return len(self._by_id[inter_id]["trafficLight"]["lightphases"])

    def _lane_ids(self, road_id: str) -> List[str]:
        road = self._road_by_id[road_id]
        return [f"{road_id}_{idx}" for idx in range(len(road["lanes"]))]

    def incoming_lanes(self, inter_id: str) -> List[str]:
        lanes: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            if self._road_by_id[road_id]["endIntersection"] == inter_id:
                lanes.extend(self._lane_ids(road_id))
        return lanes

    def outgoing_lanes(self, inter_id: str) -> List[str]:
        lanes: List[str] = []
        for road_id in self._by_id[inter_id]["roads"]:
            if self._road_by_id[road_id]["startIntersection"] == inter_id:
                lanes.extend(self._lane_ids(road_id))
        return lanes

    def next_roads(self, road_id: str) -> List[str]:
        return self._next.get(road_id, [])

    def entry_roads(self) -> List[str]:
        """Roads starting at a virtual (boundary) intersection — flow spawn points."""
        virtual = {i["id"] for i in self.intersections if i.get("virtual")}
        return [r["id"] for r in self.roads if r["startIntersection"] in virtual]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/network/test_roadnet.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Sanity-check against the real sub-area roadnet**

Run:
```bash
python3 -c "
from traffic_rl.network.roadnet import RoadNet
rn = RoadNet.load('data/danang/roadnet_subarea.json')
print('signalized agents:', len(rn.signalized_ids()))
print('entry roads:', len(rn.entry_roads()))
"
```
Expected: prints non-zero agent count and entry-road count. If `signalized agents` is 0, revisit Task 4 netconvert options (`--tls.guess-signals`) before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/traffic_rl/network/roadnet.py tests/network/test_roadnet.py
git commit -m "feat(network): roadnet parser with lanes, phases, adjacency"
```

---

## Task 7: Synthetic flow generation (motorbike-heavy)

**Files:**
- Create: `src/traffic_rl/network/flow_gen.py`, `tests/network/test_flow_gen.py`

- [ ] **Step 1: Write the failing test**

`tests/network/test_flow_gen.py`:
```python
import json

from traffic_rl.network.flow_gen import VEHICLE_TEMPLATES, generate_flow
from traffic_rl.network.roadnet import RoadNet

SAMPLE = {
    "intersections": [
        {"id": "A", "virtual": False, "roads": ["r1", "r2"],
         "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}]},
         "roadLinks": [{"startRoad": "r1", "endRoad": "r2"}]},
        {"id": "V1", "virtual": True, "roads": ["r1"]},
        {"id": "V2", "virtual": True, "roads": ["r2"]},
    ],
    "roads": [
        {"id": "r1", "startIntersection": "V1", "endIntersection": "A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "r2", "startIntersection": "A", "endIntersection": "V2",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


def _roadnet(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    return RoadNet.load(str(p))


def test_generate_flow_is_deterministic(tmp_path):
    rn = _roadnet(tmp_path)
    a = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=0.75)
    b = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=0.75)
    assert a == b


def test_flow_entries_are_valid_cityflow(tmp_path):
    rn = _roadnet(tmp_path)
    flows = generate_flow(rn, num_flows=10, route_length=2, seed=1, motorbike_ratio=1.0)
    assert len(flows) == 10
    f = flows[0]
    assert set(f) >= {"vehicle", "route", "interval", "startTime", "endTime"}
    assert f["route"][0] == "r1"            # routes start at an entry road
    assert f["vehicle"] == VEHICLE_TEMPLATES["motorbike"]
    assert all(isinstance(r, str) for r in f["route"])


def test_motorbike_ratio_controls_mix(tmp_path):
    rn = _roadnet(tmp_path)
    flows = generate_flow(rn, num_flows=100, route_length=2, seed=3, motorbike_ratio=0.0)
    assert all(f["vehicle"] == VEHICLE_TEMPLATES["car"] for f in flows)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/network/test_flow_gen.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement flow generation**

`src/traffic_rl/network/flow_gen.py`:
```python
"""Generate a CityFlow flow.json: motorbike-heavy synthetic demand via random walks."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from traffic_rl.network.roadnet import RoadNet

# CityFlow vehicle templates. Motorbike: shorter/narrower, common in Vietnam.
VEHICLE_TEMPLATES = {
    "motorbike": {
        "length": 2.0, "width": 1.0, "maxPosAcc": 3.0, "maxNegAcc": 5.0,
        "usualPosAcc": 2.5, "usualNegAcc": 4.5, "minGap": 1.0,
        "maxSpeed": 13.89, "headwayTime": 1.0,
    },
    "car": {
        "length": 5.0, "width": 2.0, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 2.5,
        "maxSpeed": 11.11, "headwayTime": 1.5,
    },
}


def _random_route(rn: RoadNet, entry_roads: List[str], length: int, rng: random.Random) -> List[str]:
    """Random walk over road adjacency starting from an entry road."""
    route = [rng.choice(entry_roads)]
    while len(route) < length:
        nxts = rn.next_roads(route[-1])
        if not nxts:
            break
        route.append(rng.choice(nxts))
    return route


def generate_flow(
    rn: RoadNet,
    num_flows: int,
    route_length: int,
    seed: int,
    motorbike_ratio: float,
    start_time: int = 0,
    end_time: int = 3600,
    interval: float = 2.0,
) -> List[dict]:
    """Return a list of CityFlow flow entries (deterministic given seed)."""
    rng = random.Random(seed)
    entry_roads = rn.entry_roads()
    if not entry_roads:
        raise ValueError("roadnet has no entry roads (no virtual boundary intersections)")

    flows: List[dict] = []
    for _ in range(num_flows):
        route = _random_route(rn, entry_roads, route_length, rng)
        kind = "motorbike" if rng.random() < motorbike_ratio else "car"
        flows.append({
            "vehicle": VEHICLE_TEMPLATES[kind],
            "route": route,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time,
        })
    return flows


def write_flow(rn: RoadNet, out_path: str, **kwargs) -> Path:
    flows = generate_flow(rn, **kwargs)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(flows, indent=2))
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/network/test_flow_gen.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Generate the real sub-area flow.json**

Run:
```bash
python3 -c "
import yaml
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.network.flow_gen import write_flow
cfg = yaml.safe_load(open('configs/network.yaml'))['flow']
rn = RoadNet.load('data/danang/roadnet_subarea.json')
p = write_flow(rn, 'data/danang/flow_subarea.json',
               num_flows=cfg['num_flows'], route_length=cfg['route_length'],
               seed=cfg['seed'], motorbike_ratio=cfg['motorbike_ratio'],
               start_time=cfg['start_time'], end_time=cfg['end_time'])
import json; print('flows:', len(json.load(open(p))))
"
```
Expected: prints `flows: 300`; `data/danang/flow_subarea.json` exists.

- [ ] **Step 6: Commit**

```bash
git add src/traffic_rl/network/flow_gen.py tests/network/test_flow_gen.py
git commit -m "feat(network): synthetic motorbike-heavy flow generation"
```

---

## Task 8: Per-intersection observation + pressure reward (pure Python)

**Files:**
- Create: `src/traffic_rl/sim/__init__.py`, `src/traffic_rl/sim/intersection.py`, `tests/sim/test_intersection.py`

- [ ] **Step 1: Write the failing test**

`tests/sim/test_intersection.py`:
```python
from traffic_rl.sim.intersection import IntersectionState, pressure_reward


def test_observation_concatenates_incoming_counts_and_phase():
    state = IntersectionState(
        inter_id="A",
        incoming_lanes=["r1_0", "r1_1"],
        outgoing_lanes=["r2_0"],
        num_phases=2,
    )
    lane_counts = {"r1_0": 3, "r1_1": 5, "r2_0": 1}
    obs = state.observation(lane_counts, current_phase=1)
    # [count(r1_0), count(r1_1), one-hot phase(2)]
    assert list(obs) == [3.0, 5.0, 0.0, 1.0]


def test_pressure_reward_is_negative_incoming_minus_outgoing():
    state = IntersectionState(
        inter_id="A",
        incoming_lanes=["r1_0"],
        outgoing_lanes=["r2_0"],
        num_phases=2,
    )
    # pressure = |sum_in - sum_out| ; reward = -pressure
    waiting = {"r1_0": 7, "r2_0": 2}
    assert pressure_reward(state, waiting) == -5.0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/sim/test_intersection.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement intersection state + reward**

`src/traffic_rl/sim/__init__.py`:
```python
```

`src/traffic_rl/sim/intersection.py`:
```python
"""Pure-Python per-intersection observation and pressure reward.

Operates on plain dicts (lane_id -> count) so it is testable without CityFlow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class IntersectionState:
    inter_id: str
    incoming_lanes: List[str]
    outgoing_lanes: List[str]
    num_phases: int

    def observation(self, lane_counts: Dict[str, int], current_phase: int) -> np.ndarray:
        """Vehicle count per incoming lane, then a one-hot of the current phase."""
        counts = [float(lane_counts.get(l, 0)) for l in self.incoming_lanes]
        phase = [0.0] * self.num_phases
        if 0 <= current_phase < self.num_phases:
            phase[current_phase] = 1.0
        return np.array(counts + phase, dtype=np.float32)

    def obs_dim(self) -> int:
        return len(self.incoming_lanes) + self.num_phases


def pressure_reward(state: IntersectionState, waiting_counts: Dict[str, int]) -> float:
    """Reward = -|incoming pressure - outgoing pressure| (max-pressure style)."""
    inflow = sum(waiting_counts.get(l, 0) for l in state.incoming_lanes)
    outflow = sum(waiting_counts.get(l, 0) for l in state.outgoing_lanes)
    return -float(abs(inflow - outflow))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/sim/test_intersection.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/__init__.py src/traffic_rl/sim/intersection.py tests/sim/test_intersection.py
git commit -m "feat(sim): per-intersection observation + pressure reward"
```

---

## Task 9: CityFlow engine wrapper (Docker integration)

**Files:**
- Create: `src/traffic_rl/sim/engine.py`, `tests/sim/test_engine_docker.py`

- [ ] **Step 1: Write the failing integration test (docker-marked)**

`tests/sim/test_engine_docker.py`:
```python
import json

import pytest

from traffic_rl.sim.engine import CityFlowEngine


@pytest.mark.docker
def test_engine_runs_subarea_and_reports_lane_counts(tmp_path):
    cfg = {
        "interval": 1.0, "seed": 0, "dir": "data/danang/",
        "roadnetFile": "roadnet_subarea.json", "flowFile": "flow_subarea.json",
        "rlTrafficLight": True, "laneChange": False, "saveReplay": False,
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))

    eng = CityFlowEngine(str(cfg_path))
    eng.reset()
    for _ in range(50):
        eng.step()
    counts = eng.lane_vehicle_counts()
    assert isinstance(counts, dict)
    assert eng.vehicle_count() >= 0
```

- [ ] **Step 2: Run it to verify it fails (in Docker)**

Run: `make cf-test`
Expected: FAIL — module `traffic_rl.sim.engine` does not exist.

- [ ] **Step 3: Implement the thin engine wrapper**

`src/traffic_rl/sim/engine.py`:
```python
"""Thin wrapper around the CityFlow C++ Engine (only importable inside Docker).

Keep this layer minimal: it just forwards to cityflow and returns plain dicts,
so all higher-level logic stays pure-Python and testable without cityflow.
"""
from __future__ import annotations

from typing import Dict


class CityFlowEngine:
    def __init__(self, config_path: str, thread_num: int = 1):
        import cityflow  # imported lazily; only available in the Docker image
        self._config_path = config_path
        self._thread_num = thread_num
        self._eng = cityflow.Engine(config_path, thread_num=thread_num)

    def reset(self) -> None:
        self._eng.reset()

    def step(self) -> None:
        self._eng.next_step()

    def set_tl_phase(self, inter_id: str, phase: int) -> None:
        self._eng.set_tl_phase(inter_id, phase)

    def lane_vehicle_counts(self) -> Dict[str, int]:
        return dict(self._eng.get_lane_vehicle_count())

    def lane_waiting_counts(self) -> Dict[str, int]:
        return dict(self._eng.get_lane_waiting_vehicle_count())

    def vehicle_count(self) -> int:
        return int(self._eng.get_vehicle_count())

    def average_travel_time(self) -> float:
        return float(self._eng.get_average_travel_time())
```

- [ ] **Step 4: Run the integration test to verify it passes (in Docker)**

Run: `make cf-test`
Expected: PASS — `test_engine_runs_subarea_and_reports_lane_counts` passes. (First run pulls/loads the image; allow a minute.)

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/engine.py tests/sim/test_engine_docker.py
git commit -m "feat(sim): thin CityFlow engine wrapper + docker integration test"
```

---

## Task 10: Multi-agent environment (engine-agnostic)

**Files:**
- Create: `src/traffic_rl/sim/multi_agent_env.py`, `tests/sim/test_multi_agent_env.py`

- [ ] **Step 1: Write the failing test with a fake engine**

`tests/sim/test_multi_agent_env.py`:
```python
import json

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

SAMPLE = {
    "intersections": [
        {"id": "A", "virtual": False, "roads": ["r1", "r2"],
         "trafficLight": {"lightphases": [{"availableRoadLinks": [0]}, {"availableRoadLinks": [1]}]},
         "roadLinks": [{"startRoad": "r1", "endRoad": "r2"}]},
        {"id": "V1", "virtual": True, "roads": ["r1"]},
        {"id": "V2", "virtual": True, "roads": ["r2"]},
    ],
    "roads": [
        {"id": "r1", "startIntersection": "V1", "endIntersection": "A",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
        {"id": "r2", "startIntersection": "A", "endIntersection": "V2",
         "lanes": [{"width": 3.0, "maxSpeed": 11.11}]},
    ],
}


class FakeEngine:
    def __init__(self):
        self.steps = 0
        self.phases = {}
    def reset(self): self.steps = 0
    def step(self): self.steps += 1
    def set_tl_phase(self, i, p): self.phases[i] = p
    def lane_vehicle_counts(self): return {"r1_0": 4, "r2_0": 1}
    def lane_waiting_counts(self): return {"r1_0": 4, "r2_0": 1}
    def vehicle_count(self): return 5
    def average_travel_time(self): return 12.0


def _env(tmp_path):
    p = tmp_path / "roadnet.json"
    p.write_text(json.dumps(SAMPLE))
    rn = RoadNet.load(str(p))
    return MultiAgentTrafficEnv(rn, FakeEngine(), action_interval=5)


def test_reset_returns_obs_per_agent(tmp_path):
    env = _env(tmp_path)
    obs = env.reset()
    assert list(obs.keys()) == ["A"]
    assert obs["A"].shape == (1 + 2,)   # 1 incoming lane + 2 phases


def test_step_applies_phase_and_returns_rewards(tmp_path):
    env = _env(tmp_path)
    env.reset()
    obs, rewards, done, info = env.step({"A": 1})
    assert env.engine.phases["A"] == 1
    assert env.engine.steps == 5         # action_interval sub-steps
    assert rewards["A"] == -3.0          # -|4 - 1|
    assert "A" in obs and not done


def test_agent_ids_are_signalized_only(tmp_path):
    env = _env(tmp_path)
    assert env.agent_ids == ["A"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/sim/test_multi_agent_env.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the multi-agent env**

`src/traffic_rl/sim/multi_agent_env.py`:
```python
"""Multi-agent traffic-signal environment over a duck-typed engine.

`engine` must provide: reset(), step(), set_tl_phase(id, phase),
lane_vehicle_counts(), lane_waiting_counts(), vehicle_count(),
average_travel_time(). The real one is CityFlowEngine; tests use a fake.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.intersection import IntersectionState, pressure_reward


class MultiAgentTrafficEnv:
    def __init__(self, roadnet: RoadNet, engine, action_interval: int = 10, max_steps: int = 3600):
        self.roadnet = roadnet
        self.engine = engine
        self.action_interval = action_interval
        self.max_steps = max_steps
        self.agent_ids: List[str] = roadnet.signalized_ids()
        self.states: Dict[str, IntersectionState] = {
            aid: IntersectionState(
                inter_id=aid,
                incoming_lanes=roadnet.incoming_lanes(aid),
                outgoing_lanes=roadnet.outgoing_lanes(aid),
                num_phases=roadnet.num_phases(aid),
            )
            for aid in self.agent_ids
        }
        self._phase: Dict[str, int] = {aid: 0 for aid in self.agent_ids}
        self._t = 0

    def obs_dims(self) -> Dict[str, int]:
        return {aid: s.obs_dim() for aid, s in self.states.items()}

    def reset(self) -> Dict[str, np.ndarray]:
        self.engine.reset()
        self._phase = {aid: 0 for aid in self.agent_ids}
        self._t = 0
        return self._observations()

    def _observations(self) -> Dict[str, np.ndarray]:
        counts = self.engine.lane_vehicle_counts()
        return {
            aid: self.states[aid].observation(counts, self._phase[aid])
            for aid in self.agent_ids
        }

    def step(self, actions: Dict[str, int]) -> Tuple[Dict[str, np.ndarray], Dict[str, float], bool, dict]:
        for aid, phase in actions.items():
            self._phase[aid] = phase
            self.engine.set_tl_phase(aid, phase)
        for _ in range(self.action_interval):
            self.engine.step()
            self._t += 1
        waiting = self.engine.lane_waiting_counts()
        rewards = {aid: pressure_reward(self.states[aid], waiting) for aid in self.agent_ids}
        done = self._t >= self.max_steps
        info = {
            "average_travel_time": self.engine.average_travel_time(),
            "vehicle_count": self.engine.vehicle_count(),
            "step": self._t,
        }
        return self._observations(), rewards, done, info
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/sim/test_multi_agent_env.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/sim/multi_agent_env.py tests/sim/test_multi_agent_env.py
git commit -m "feat(sim): engine-agnostic multi-agent traffic env"
```

---

## Task 11: Fixed-Time controller

**Files:**
- Create: `src/traffic_rl/agents/__init__.py`, `src/traffic_rl/agents/fixed_time.py`, `tests/agents/test_fixed_time.py`

- [ ] **Step 1: Write the failing test**

`tests/agents/test_fixed_time.py`:
```python
from traffic_rl.agents.fixed_time import FixedTimeController


def test_cycles_phases_each_decision():
    ctrl = FixedTimeController(num_phases={"A": 2, "B": 3})
    assert ctrl.act() == {"A": 0, "B": 0}
    assert ctrl.act() == {"A": 1, "B": 1}
    assert ctrl.act() == {"A": 0, "B": 2}   # A wraps at 2, B continues
    assert ctrl.act() == {"A": 1, "B": 0}   # B wraps at 3


def test_reset_restarts_cycle():
    ctrl = FixedTimeController(num_phases={"A": 2})
    ctrl.act(); ctrl.act()
    ctrl.reset()
    assert ctrl.act() == {"A": 0}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/agents/test_fixed_time.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the controller**

`src/traffic_rl/agents/__init__.py`:
```python
```

`src/traffic_rl/agents/fixed_time.py`:
```python
"""Fixed-time baseline: each intersection cycles its phases round-robin."""
from __future__ import annotations

from typing import Dict


class FixedTimeController:
    def __init__(self, num_phases: Dict[str, int]):
        self.num_phases = num_phases
        self._counter: Dict[str, int] = {aid: 0 for aid in num_phases}

    def act(self, observations: Dict | None = None) -> Dict[str, int]:
        actions = {aid: self._counter[aid] % n for aid, n in self.num_phases.items()}
        for aid in self.num_phases:
            self._counter[aid] += 1
        return actions

    def reset(self) -> None:
        self._counter = {aid: 0 for aid in self.num_phases}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/agents/test_fixed_time.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/traffic_rl/agents/__init__.py src/traffic_rl/agents/fixed_time.py tests/agents/test_fixed_time.py
git commit -m "feat(agents): fixed-time baseline controller"
```

---

## Task 12: End-to-end sub-area run with replay (P2 gate)

**Files:**
- Create: `scripts/run_fixed_time.py`

- [ ] **Step 1: Write the end-to-end runner**

`scripts/run_fixed_time.py`:
```python
#!/usr/bin/env python3
"""Run the Fixed-Time controller on a CityFlow scenario; save replay + metrics.

Must run inside the CityFlow Docker image (needs cityflow). Example:
  make cf-run CMD="python3 scripts/run_fixed_time.py subarea"
"""
import json
import sys
from pathlib import Path

from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    area = sys.argv[1] if len(sys.argv) > 1 else "subarea"
    data_dir = ROOT / "data" / "danang"
    roadnet_file = f"roadnet_{area}.json"
    flow_file = f"flow_{area}.json"

    results_dir = ROOT / "results" / area
    results_dir.mkdir(parents=True, exist_ok=True)

    # CityFlow resolves roadnetFile/flowFile/log files all relative to `dir`,
    # so the replay must be written alongside the roadnet (in data/danang/).
    cfg = {
        "interval": 1.0, "seed": 0, "dir": "data/danang/",
        "roadnetFile": roadnet_file, "flowFile": flow_file,
        "rlTrafficLight": True, "laneChange": False, "saveReplay": True,
        "roadnetLogFile": f"replay_roadnet_{area}.json",
        "replayLogFile": f"replay_{area}.txt",
    }
    cfg_path = results_dir / "config_runtime.json"
    cfg_path.write_text(json.dumps(cfg, indent=2))

    rn = RoadNet.load(str(data_dir / roadnet_file))
    engine = CityFlowEngine(str(cfg_path))
    env = MultiAgentTrafficEnv(rn, engine, action_interval=10, max_steps=1000)
    controller = FixedTimeController(num_phases={aid: rn.num_phases(aid) for aid in env.agent_ids})

    env.reset()
    controller.reset()
    done = False
    info = {}
    while not done:
        actions = controller.act()
        _, _, done, info = env.step(actions)

    metrics = {
        "controller": "FixedTime",
        "area": area,
        "agents": len(env.agent_ids),
        "final_average_travel_time": info.get("average_travel_time"),
        "final_vehicle_count": info.get("vehicle_count"),
        "steps": info.get("step"),
    }
    (results_dir / "metrics_fixed_time.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print("Replay:", data_dir / f"replay_roadnet_{area}.json", data_dir / f"replay_{area}.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the end-to-end scenario in Docker**

Run: `make cf-run CMD="pip install pyyaml numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_fixed_time.py subarea"`
Expected: prints a metrics JSON with `agents >= 1` and a numeric `final_average_travel_time`; creates `results/subarea/replay_roadnet.json` and `results/subarea/replay.txt`.

- [ ] **Step 3: Verify replay + metrics files are non-empty**

Run: `ls -la data/danang/replay_*subarea* results/subarea/ && test -s data/danang/replay_subarea.txt && echo "REPLAY OK"`
Expected: `data/danang/replay_roadnet_subarea.json`, `data/danang/replay_subarea.txt`, and `results/subarea/metrics_fixed_time.json` all present; prints `REPLAY OK`.

- [ ] **Step 4: Commit (script + metrics; replay is gitignored)**

```bash
git add scripts/run_fixed_time.py results/subarea/metrics_fixed_time.json
git commit -m "feat: end-to-end fixed-time run on Da Nang sub-area with replay"
```

- [ ] **Step 5: Scale to the full network (gate check)**

Run, in order:
```bash
SUMO_HOME=/opt/homebrew/share/sumo python3 scripts/download_osm.py full
SUMO_HOME=/opt/homebrew/share/sumo python3 -c "from traffic_rl.network.osm_to_sumo import run_netconvert; run_netconvert('data/osm/danang_full_bbox.osm.xml','data/sumo/danang_full.net.xml')"
python3 -c "from traffic_rl.network.sumo_to_cityflow import run_converter; run_converter('data/sumo/danang_full.net.xml','data/danang/roadnet_full.json')"
python3 -c "
import yaml; from traffic_rl.network.roadnet import RoadNet; from traffic_rl.network.flow_gen import write_flow
cfg=yaml.safe_load(open('configs/network.yaml'))['flow']; rn=RoadNet.load('data/danang/roadnet_full.json')
write_flow(rn,'data/danang/flow_full.json',num_flows=cfg['num_flows'],route_length=cfg['route_length'],seed=cfg['seed'],motorbike_ratio=cfg['motorbike_ratio'],start_time=cfg['start_time'],end_time=cfg['end_time'])
print('full agents:', len(rn.signalized_ids()))
"
make cf-run CMD="pip install pyyaml numpy >/dev/null 2>&1; PYTHONPATH=src python3 scripts/run_fixed_time.py full"
```
Expected: full network converts and runs end-to-end; prints the full Da Nang agent count and a metrics JSON. This is the **P2 completion gate**: a working CityFlow simulation of Da Nang, driven through the multi-agent env, with replay. If conversion fails at full scale, debug `netconvert` options (Task 4) on the full bbox before declaring the gate met.

- [ ] **Step 6: Commit the full-network metrics**

```bash
git add results/full/metrics_fixed_time.json
git commit -m "feat: full Da Nang network runs end-to-end under fixed-time"
```

---

## What this plan delivers

A reproducible pipeline that turns OSM Da Nang into a CityFlow simulation, a multi-agent environment exposing per-intersection observations + pressure rewards, a Fixed-Time baseline, and CityFlow replays for both a sub-area and the full city. This is the foundation the next plans build on.

## Follow-up plans (not in this document)

- **Plan 2 — Baselines + MARL:** Max-Pressure & Random controllers; parameter-shared DQN agent + training loop over `MultiAgentTrafficEnv`; checkpointing and training logs.
- **Plan 3 — Evaluation + UI:** metric aggregation across methods, Streamlit comparison dashboard (training curves + tables), CityFlow web-replay launcher, and Chapter 4 result export.

These are deferred because their exact shapes (observation sizing, phase semantics, replay wiring) depend on the real `roadnet.json` produced here.
```
