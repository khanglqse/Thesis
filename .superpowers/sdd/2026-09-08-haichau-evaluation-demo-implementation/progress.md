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
- [ ] Fail-closed project verifier and operator documentation

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
- Task 6 RED: Node core tests failed 4/4 and Python exporter tests failed 2/2 against explicit stubs; replay hash-set test failed before optional `replay.json` was included in run status.
- Task 6 GREEN: `node --test tests/replay_ab/haichau_network_demo_core.test.cjs` — 4 passed; `PYTHONPATH=src pytest tests/report/test_haichau_replay_export.py -v` — 2 passed; campaign suite — 7 passed.
- Task 6 UI: exported a synthetic 53-node test fixture, served it only on `127.0.0.1:8766`, and exercised Chrome play/pause, seek to 00:05 and canvas node selection (N37). Status showed `Verified bundle loaded`; console had 0 warnings/errors; source scan found no remote URL/CDN/import. Superdesign draft informed the map-first comparison/detail/aggregate layout, while fabricated draft numbers and its Tailwind CDN were excluded.
- Task 6 dependency gap: no MP4/PDF/PNG fallbacks were generated because the frozen representative runs and summary do not exist. The exporter accepts only caller-supplied real fallback files and hashes them into the bundle.
