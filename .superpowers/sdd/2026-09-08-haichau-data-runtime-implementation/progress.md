# Hai Chau data/runtime implementation ledger

- Branch: `feat/haichau-data-runtime`
- Worktree: `/Users/khanglq1/workplace/Thesis/traffic-rl/.worktrees/haichau-data`
- Plan: `docs/superpowers/plans/2026-09-08-haichau-data-runtime-implementation.md`
- Canonical source SHA-256: `cddce1090b214fd8250303a28b51e4a460f4af04dde87cafad9dabd58f2ac040`

## Baseline

- `PYTHONPATH=src pytest tests/eval/test_runner.py -v`: PASS (1 test).
- Source roadnet inspection: 1,107 roads, 592 intersections, 53 multi-phase controlled signals.

## Tasks

- [x] Task 1: artifact hashing and manifest contract
- [x] Task 2: version and audit canonical network
- [x] Task 3: deterministic multi-regime OD demand generator
- [x] Task 4: build versioned experiment manifest and flows
- [ ] Task 5: pin and smoke CityFlow runtime

## TDD evidence

Entries below record the command and observed reason for RED before production code, followed by GREEN evidence.

- Task 1 RED: `PYTHONPATH=src pytest tests/research/test_artifacts.py -v` — 5 failed because `traffic_rl.research.artifacts` did not exist.
- Task 1 GREEN: `PYTHONPATH=src pytest tests/research/test_artifacts.py tests/eval/test_runner.py -v` — 6 passed.
- Task 2 RED: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py -v` — 4 failed because `traffic_rl.network.haichau_dataset` did not exist.
- Task 2 dataset gate: copied source hash and tracked roadnet hash both `cddce109...f2ac040`; audit reported 1,107 roads, 592 intersections, 53 controlled signals, 53 directed signal edges, 28 weak components and zero phase errors.
- Task 2 GREEN: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py tests/network/test_roadnet_phases.py -v` — 7 passed.
- Task 3 RED: `PYTHONPATH=src pytest tests/network/test_haichau_demand.py -v` — 5 failed because route and case generation functions were absent.
- Task 3 GREEN: `PYTHONPATH=src pytest tests/network/test_haichau_demand.py tests/research/test_artifacts.py -v` — 10 passed.
- Task 4 RED: `PYTHONPATH=src pytest tests/scripts/test_prepare_haichau_network.py -v` — 3 failed because `scripts.prepare_haichau_network_v2` did not exist.
- Task 4 real generation: builder emitted 30 cases (9 train, 6 validation, 15 test), 30 unique flow hashes, all three regimes in every seed family, minimum route coverage 2 controlled signals; output size 8.0 MB.
- Task 4 GREEN: `PYTHONPATH=src pytest tests/scripts/test_prepare_haichau_network.py -v` — 3 passed.
