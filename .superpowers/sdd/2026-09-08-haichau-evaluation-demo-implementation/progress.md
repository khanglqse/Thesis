# Hai Chau evaluation/demo progress

Branch: `feat/haichau-evaluation-demo`

## Baseline

- `make test`: 110 passed, 1 failed, 1 deselected.
- Pre-existing failure: `tests/network/test_roadnet_neighbors.py::test_upstream_neighbors_on_haichau` cannot find Git-ignored `data/danang/roadnet_haichau.json` in this worktree.

## Work items

- [x] Network metric contract and runner integration
- [x] Resume-safe matched campaign framework
- [x] Hierarchical statistics and acceptance gates
- [ ] Frozen five-seed campaign — BLOCKED pending canonical case manifest, checkpoint contracts and five trained model seeds from the foundation/model branches.
- [x] Thesis artifact and claim generator
- [x] Replay exporter and offline 53-node viewer framework
- [x] Fail-closed project verifier and operator documentation

## TDD log

RED and GREEN commands are recorded here as each task is implemented.

- Task 1 RED: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py -v` — 5 expected failures from the unimplemented accumulator; after adding the next contract tests, 2 expected failures for missing engine snapshot/runner propagation.
- Task 1 GREEN: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py tests/eval/test_runner.py -v` — 8 passed.
- Task 2 RED: `PYTHONPATH=src pytest tests/eval/test_network_campaign.py -v` — 6 expected failures from unimplemented expansion/execution (after correcting a test fixture setup error).
- Task 2 GREEN: same command — 6 passed.
- Task 3 RED: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py -v` — 7 expected failures from unimplemented statistics; candidate-only seed gate mutation test then failed as expected.
- Task 3 GREEN: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py tests/eval/test_multiseed.py -v` — 13 passed.
- Task 5 RED: `PYTHONPATH=src pytest tests/report/test_haichau_network.py -v` — 4 expected failures from unimplemented table, claim and artifact functions.
- Task 5 GREEN: same command — 4 passed.
- Task 5 PDF: `tectonic paper/thesis_danang.tex` succeeded. Rendered physical pages 20 and 26 at 140 DPI; the new protocol/status sections have no clipping or overflow. No generated network result table was inserted because a frozen summary does not yet exist.
- Task 5 dependency gap: the summary-only generator covers the matched controller table, paired queue difference and completion figures. Per-node maps, training curves, robustness and coordination ablation still require frozen fields/artifacts from the foundation/model pipeline; none were synthesized.
- Task 6 RED: Node core tests failed 4/4 and Python exporter tests failed 2/2 against explicit stubs; replay hash-set test failed before optional `replay.json` was included in run status.
- Task 6 GREEN: `node --test tests/replay_ab/haichau_network_demo_core.test.cjs` — 4 passed; `PYTHONPATH=src pytest tests/report/test_haichau_replay_export.py -v` — 2 passed; campaign suite — 7 passed.
- Task 6 UI: exported a synthetic 53-node test fixture, served it only on `127.0.0.1:8766`, and exercised Chrome play/pause, seek to 00:05 and canvas node selection (N37). Status showed `Verified bundle loaded`; console had 0 warnings/errors; source scan found no remote URL/CDN/import. Superdesign draft informed the map-first comparison/detail/aggregate layout, while fabricated draft numbers and its Tailwind CDN were excluded.
- Task 6 dependency gap: no MP4/PDF/PNG fallbacks were generated because the frozen representative runs and summary do not exist. The exporter accepts only caller-supplied real fallback files and hashes them into the bundle.
- Engine integration RED: the explicit environment vehicle-accounting test failed with `TypeError` because `network_metric_snapshot` did not accept authoritative departed/arrived counters.
- Engine integration GREEN: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py tests/eval/test_runner.py -v` — 9 passed. The read-only adapter defaults to CityFlow-observable running + finished vehicles; the campaign environment must pass explicit departed/arrived counters when scheduled, unreleased or censored demand belongs in the denominator.
- Task 7 RED: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_thesis.py -v` — 3 expected failures from the verifier stubs.
- Task 7 file-set RED: a demo with an unlisted `network.json` reached replay validation instead of failing the hash-manifest audit.
- Task 7 GREEN: `PYTHONPATH=src pytest tests/scripts/test_verify_haichau_thesis.py -v` — 5 passed, including a complete hash-valid fixture whose acceptance decision is negative. The verifier treats a fully reported negative outcome as valid evidence rather than changing it into a failed release gate.
- Task 7 current audit: emitted a real incomplete `results/haichau_network_v2/verification/final-report.json`. It fails all 12 release gates because the frozen protocol, case/network manifests, five checkpoints, fresh campaign, summary-derived paper/demo and clean-checkout record do not yet exist. No placeholder evidence was created.

## Verification log

- Changed Python surface: 40 tests passed; the focused verifier suite contributes 5 of them.
- `node --test tests/replay_ab/haichau_network_demo_core.test.cjs`: 4 passed.
- `npm run test:replay`: 16 passed, 2 pre-existing failures because Git-ignored `data/danang/replay_roadnet_haichau_rush.json` is absent.
- `make test`: 143 passed, 1 failed, 1 deselected. The sole failure is the baseline missing-file issue in `tests/network/test_roadnet_neighbors.py`.
- `make cf-test`: 1 CityFlow Docker integration test passed (115 deselected).
- `tectonic paper/thesis_danang.tex`: succeeded; only the pre-existing underfull-box/object warnings remained. The generated PDF was restored after this repeat build because it differed only in generated binary metadata.
- Current project verifier: exits 1 by design and records the 12 unresolved evidence gates; this is the dependency-safe result until the integrated frozen campaign exists.
