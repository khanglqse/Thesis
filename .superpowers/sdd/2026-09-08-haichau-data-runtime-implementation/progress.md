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
- [x] Task 5: pin and smoke CityFlow runtime

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
- Task 5 RED: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_foundation.py -v` — 5 failed because `scripts.verify_haichau_foundation` did not exist.
- Task 5 Python 3.6 compatibility RED: direct import in the pinned base image failed at the new module's dependency on legacy `flow_gen.py` (`future feature annotations is not defined`). Root cause: the new runtime path imported a host-only Python 3.7 future feature.
- Task 5 Python 3.6 compatibility GREEN: built research image imported `haichau_dataset` and `verify_haichau_foundation` successfully under Python 3.6.5.
- Task 5 GREEN: specified host suite passed 22 tests; host verifier returned 53 signals, 30 cases and split counts 9/6/15.
- Runtime build: `make haichau-image` completed with linux/amd64 image ID `sha256:6e9eccf4cceb4251a8f7c0614699fe25c7e45e25ff1a41c654f645995bb17069` from the required base digest.
- Runtime smoke: `make haichau-smoke` completed a real 60-step Fixed-Time CityFlow episode on `train_normal_demand11`: 53 controlled signals, 496 active vehicles, 1,938 vehicle-seconds queue integral, average travel time 60.0 seconds.
- Full-suite RED: `make test` reached 132 passed and 1 failed because `tests/network/test_roadnet_neighbors.py` still referenced ignored `data/danang/roadnet_haichau.json`; the original-checkout file has the same SHA-256 as the new tracked roadnet. Updated the test to consume the tracked clean-checkout dataset.
- Full-suite GREEN: `make test` — 133 passed, 1 Docker-marked test deselected, zero failures.

## Review remediation

- C1 route-family partition RED: `PYTHONPATH=src pytest tests/network/test_haichau_demand.py -v` — 7 failures because no canonical catalog or disjoint family partition existed and all splits sampled the same route pool.
- C1 route-family partition GREEN: the canonical network yields 1,418 stable route families; deterministic weighted partitioning assigns every family to exactly one of train/validation/test before any case sampling. Real-dataset and artifact-contract tests reject cross-split family reuse.
- C2 semantic verification RED: 12 mutation cases passed unexpectedly after changing preprocessing, simulation, labels, scale, histogram, seeds/case IDs, runtime identity, regime flow content, route-family split, vehicle mix, and provenance.
- C2 semantic verification GREEN: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_foundation.py -v` — 20 passed. The verifier reconstructs the catalog and every expected flow from the tracked inputs, parses every route and vehicle row, checks family/histogram/split membership, and binds YAML, manifest, provenance, temporal source, Dockerfile, and runtime identity.
- I1 network audit RED: the canonical dataset gate exposed agent `5896811072` with only one movement-serving green phase.
- I1 network audit GREEN: deterministically split its two simultaneous movements into two 40-second green phases separated by the existing 5-second clearance phases, preserving the 90-second cycle. The repaired network SHA-256 is `a65a6edea00a44ea9e51da75db47aa88c08025a725e1dd07cf2f908093607ca1`; all 53 agents now have at least two movement-serving green phases.
- I2 provenance GREEN: provenance records the available source artifact hashes, extraction/conversion commands and flags, demand aggregation, license, bounding box, source definition commit, and deterministic network repair. Tool versions and original retrieval date were not recorded at creation time and are explicitly `unknown_not_recorded`; verifier-required auditable fields fail closed.
- I3 temporal-profile RED: generated streams used synchronized, constant-hour starts.
- I3 temporal-profile GREEN: tracked source counts define three bins for normal, AM peak, and PM peak; deterministic staggering schedules the exact integer count for every bin. Mutation tests reject source-count, interval, and scheduled-count drift.
- I4 runtime identity RED: smoke accepted only the mutable derived tag.
- I4 runtime identity GREEN: `make haichau-smoke` rebuilds the linux/amd64 image, validates base-digest and Dockerfile-hash labels, passes the immutable derived image ID into the verifier, and completed a real 60-step CityFlow episode with image ID `sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517`.
- Deterministic regeneration: two consecutive builder runs produced the same tracked/untracked artifact digest `4a95d973bf54e4627179141cb567451c03e5ab964ec9f1f35f706052b3ada104`.
- Review full-suite GREEN: `make test` — 153 passed, 1 Docker-marked test deselected, zero failures.
- Review host verifier GREEN: 53 controlled signals, 30 cases, 1,418 route families, split counts 9/6/15, and verified network/config/runtime hashes.
- Review runtime smoke GREEN: `make haichau-smoke` — real 60-step Fixed-Time episode on `train_normal_demand11`, 485 vehicles, 627 vehicle-seconds queue integral, 30.896-second average travel time, linux/amd64 derived image identity attested.
- I5 evidence RED: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_foundation.py::test_committed_clean_checkout_foundation_evidence -q` — failed because `results/haichau_network_v2/verification/foundation.json` did not exist.
- I5 clean-checkout GREEN: detached clean worktree at candidate commit `e110437364f19072fcaba7d8b7065ffd0e87626e`, with ignored source absent, passed `make test` (153 passed, 1 deselected), host foundation verification, and a rebuilt real CityFlow smoke. `results/haichau_network_v2/verification/foundation.json` records exact commands, timestamps, wall times, outputs, commit and immutable image identity; its contract test passes.
- Clean-checkout mount note: an initial clone under `/tmp` passed the host checks but Docker Desktop mounted that path as an empty directory. The recorded run used a clean detached worktree under `/Users/khanglq1/workplace/Thesis`, which Docker mounted correctly; the successful smoke took 88 seconds.

## Re-review phase semantics and provenance

- Phase-role RED: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py -q` — 5 failures. The audit still reported all 147 non-empty phases as greens, no contract builder existed, and the tracked phase contract was absent.
- Phase-role GREEN: `PYTHONPATH=src pytest tests/network/test_haichau_dataset.py -q` — 8 passed. The deterministic contract classifies 107 min-green-compatible movement phases as selectable and 127 short/empty phases as transitions across exactly 53 agents; every ordered switch has a non-empty declared transition sequence.
- Manifest phase binding RED: `PYTHONPATH=src pytest tests/scripts/test_prepare_haichau_network.py -q` — the manifest lacked `phase_contract` even though the fixture config supplied a hash-bound contract.
- Manifest phase binding GREEN: the builder verifies the config-bound contract, audits the network through it, and writes the exact `{path, sha256}` record at manifest top level.
- Semantic/provenance RED: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_foundation.py -q` — 18 failures exposed old audit field assumptions, missing phase-contract verification, accepted fabricated nested provenance, and missing synthetic-repair labeling.
- Semantic/provenance GREEN: verifier suite — 30 passed. It regenerates the phase contract, rejects promoted short phases or missing directed transitions, enforces exact nested provenance schemas/allowed unknowns, validates all four tracked source/intermediate artifact hashes, binds provenance through YAML and manifest, and applies the documented source→canonical transformation to require exact roadnet equality.
- Repair provenance: node `5896811072` is explicitly `synthetic_engineering_normalization` with `source_evidence: unknown_not_recorded`; the dataset README states it is not an observed/source-derived signal plan.
- Source preservation: the clipped PBF, OSM XML, SUMO network and original CityFlow roadnet are tracked under `datasets/haichau_network_v2/source/` with their previously measured SHA-256 values.
- Re-review full-suite GREEN before evidence refresh: `make test` — 165 passed, 1 Docker-marked test deselected, zero failures.
- Re-review host verifier GREEN: 53 agents, 107 selectable phases, 127 transition phases, 30 cases and 1,418 route families.
- Re-review runtime smoke GREEN: `make haichau-smoke` rebuilt/inspected image `sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517` and completed the real 60-step CityFlow episode.
- Evidence-hardening RED: the enhanced evidence contract failed because the old `foundation.json` did not record artifact blob hashes.
- Evidence-hardening GREEN: clean detached worktree at `23151a9fde5a5ae68280a33aa9976d026611609e` passed 165 host tests, the canonical verifier and Docker smoke. Refreshed `foundation.json` records 10 verified artifact/blob hashes including the phase contract and four provenance sources; the test now proves the commit exists, is an ancestor, and every recorded hash matches `git show <verified_commit>:<path>`.

## Final re-review: canonical trust anchor and SUMO phase semantics

- SUMO phase-role RED: `PYTHONPATH=src pytest -q tests/network/test_haichau_dataset.py -k 'phase_contract or canonical_network'` — 4 failures because the builder accepted no SUMO source inputs and the old contract lacked `source_sumo_network` and per-stage source semantics.
- Canonical provenance RED: `PYTHONPATH=src pytest -q tests/scripts/test_verify_haichau_foundation.py -k 'canonical_provenance_semantic_anchor'` — 5 failures because no external semantic trust anchor existed.
- SUMO phase-role GREEN: all 53 CityFlow signal IDs map uniquely to tracked SUMO `tlLogic` entries by exact ID or `GS_` prefix. The regenerated hash-bound contract preserves source state strings and classifies 107 `selectable_green`, 10 short `compound_service`, 116 `clearance_yellow`, and 1 `all_red` stages. The documented synthetic split at `5896811072` is validated separately and maps canonical source indices `[0, 1, 0, 2]`.
- Canonical provenance GREEN: the verifier pins canonical JSON semantics to SHA-256 `de9cc6003a4b39ca478cdae13c8ebb68937e27adcd4172df515cc724311b28d1`. Mutations to bounding box, license, historical paths, demand basis, or study scope are rejected after computing a new self-consistent hash.
- Mutation suite GREEN: rehashed phase-contract changes to source state, role, or movement records are rejected by deterministic regeneration from the tracked SUMO network and repaired CityFlow network.
- Final re-review focused GREEN: `PYTHONPATH=src pytest -q tests/network/test_haichau_dataset.py tests/scripts/test_prepare_haichau_network.py tests/scripts/test_verify_haichau_foundation.py` — 50 passed.
- Final re-review host GREEN before evidence refresh: `make test` — 174 passed, 1 Docker-marked test deselected in 10.44 seconds.
- Final re-review verifier GREEN before evidence refresh: 53 signals, 107 selectable phases, 127 transition phases, 30 cases, 1,418 route families, split counts 9/6/15.
- Final re-review clean-checkout GREEN: detached worktree at `80306efbbda780819c85ea1748f7ac08e7dfdcc3` contained no ignored source and remained clean. `make test` passed 174 tests with 1 deselected in 10.83 seconds; canonical verification passed in 5.46 seconds; `make haichau-smoke` rebuilt/inspected image `sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517` and passed the real 60-step/53-agent episode in 193.46 seconds.
