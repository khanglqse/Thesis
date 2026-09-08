# Hai Chau evaluation/demo progress

Branch: `feat/haichau-evaluation-demo`

## Baseline

- `make test`: 110 passed, 1 failed, 1 deselected.
- Pre-existing failure: `tests/network/test_roadnet_neighbors.py::test_upstream_neighbors_on_haichau` cannot find Git-ignored `data/danang/roadnet_haichau.json` in this worktree.

## Work items

- [x] Network metric contract and runner integration
- [x] Resume-safe matched campaign framework
- [x] Hierarchical statistics and acceptance gates
- [ ] Frozen five-seed campaign (blocked pending foundation/model artifacts)
- [ ] Thesis artifact and claim generator
- [ ] Replay exporter and offline 53-node viewer
- [ ] Fail-closed project verifier and operator documentation

## TDD log

RED and GREEN commands are recorded here as each task is implemented.

- Task 1 RED: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py -v` — 5 expected failures from the unimplemented accumulator; after adding the next contract tests, 2 expected failures for missing engine snapshot/runner propagation.
- Task 1 GREEN: `PYTHONPATH=src pytest tests/eval/test_network_metrics.py tests/eval/test_runner.py -v` — 8 passed.
- Task 2 RED: `PYTHONPATH=src pytest tests/eval/test_network_campaign.py -v` — 6 expected failures from unimplemented expansion/execution (after correcting a test fixture setup error).
- Task 2 GREEN: same command — 6 passed.
- Task 3 RED: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py -v` — 7 expected failures from unimplemented statistics; candidate-only seed gate mutation test then failed as expected.
- Task 3 GREEN: `PYTHONPATH=src pytest tests/eval/test_network_statistics.py tests/eval/test_multiseed.py -v` — 13 passed.
