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

## Independent-review remediation

All Critical and Important findings in `/tmp/review-haichau-evaluation-demo.md` are addressed without creating release evidence:

- [x] C1: the verifier now reconstructs the run matrix from the hash-verified case manifest and frozen protocol, verifies runtime/network/checkpoint inputs, recomputes the numeric summary and acceptance decision, and content-hashes thesis/demo/fallback outputs end to end.
- [x] C2: every completed run stores a canonical full-run-spec digest; resume and verification compare the current campaign entry, persisted run manifest, resolved configuration, metric provenance and checkpoint contract exactly.
- [x] C3: gates require the exact declared seed set in every required regime, at least five independent learning seeds, declared minimum matched demand units, identical seed coverage and no duplicate seed/case cell.
- [x] I1/I2: scheduled, inserted/departed, arrived, running, unreleased/pending and removed are explicit; conservation, finite values, all 53 node metrics and completed travel-time counts fail closed.
- [x] I3: replay network bytes are bound to the frozen viewer hash; frames must be exactly `0,5,...,horizon`; paired grids match; final audit reparses every replay and compares it with its hash-verified source run.
- [x] I4/M1: artifact generation cleans the output directory and hashes both complete tables, figures, sidecars, source and PDF; the comparison table contains all five controllers.

### Review TDD log

- Metrics RED: 7 failures covered NaN, missing completed travel times, contradictory accounting and conservation. Additional duration RED: 3 failures showed NaN/positive infinity were accepted and negative infinity had the incomplete diagnostic. GREEN: `tests/eval/test_network_metrics.py` — 19 passed.
- Campaign RED: 3 failures covered missing resolved configuration, stale completed-run relabeling and incomplete network metric schema. GREEN: the campaign suite passes with exact run-spec/resolved-config/metric identity checks.
- Statistics RED: 5 failures covered non-finite inputs, missing per-regime seeds, unequal seed coverage, duplicate seed/case cells and insufficient demand units. GREEN: gates consume the frozen minimum seed/unit declarations.
- Replay RED: 2 failures covered an unrelated 53-node topology and a one-frame replay. GREEN: shared exporter/verifier replay validation requires the frozen network and full sampling grid.
- Reporting RED: 3 failures covered omitted controllers, unhashed artifacts and stale generated files. GREEN: generation replaces a summary-addressed output set and records every artifact hash.
- Verifier RED: disconnected placeholder evidence was accepted; later adversarial tests exposed summary replay/artifact self-relabeling and a malformed checkpoint entry crash. GREEN: a coherent hash-bound numeric fixture completes with an honestly negative decision, while all mutations fail their gate without crashing.

### Review verification

- Host focused Python suite: 61 passed before the final malformed-entry regression; final rerun recorded below.
- Live offline UI: a coherent synthetic test fixture at `/tmp/haichau-review-ui` was served on `127.0.0.1:8767` and opened in Chrome. The browser reported `Verified bundle loaded`, 53 controlled signals, and switched from normal to PM peak while loading the corresponding local paired replay files and changing the aggregate result from +10% to -10%. The visual map, controls, selected-node rail and frozen-evidence panel rendered without clipping. HTTP logs contained only localhost assets; the server was stopped afterward.
- Citation/offline review: the independent review found no citation defect; Tectonic resolved the added primary-source keys. The viewer has no remote import/CDN, and the final manifest must enumerate every local payload.
- Current project audit remains `complete=false` with all 12 gates blocked by absent integrated frozen artifacts. This is intentional and is not acceptance evidence.
- Final focused rerun: 68 Python tests passed; focused offline viewer core: 4 Node tests passed.
- Python 3.6.5 CityFlow container focused compatibility: 52 tests passed; `make cf-test` equivalent: 1 passed, 144 deselected.
- Final `make test`: 172 passed, 1 failed, 1 deselected. The only failure remains `test_upstream_neighbors_on_haichau`, whose Git-ignored `data/danang/roadnet_haichau.json` input is absent.

## R2 independent-review remediation

- [x] Code/runtime root: the frozen protocol now supplies a full Git `code_commit`, immutable Docker repo digest, inspected image ID and Dockerfile path/hash. These fields enter every run, resolved config, metric identity, completion status and canonical run digest. The runner checks a clean descendant checkout, rejects code-path drift, inspects the local Docker image and executes controller commands inside that image with networking disabled. The final verifier repeats the actual Git, Docker image and Dockerfile checks.
- [x] Exact statistical cells: every learned seed must contain the same cells and that set must exactly equal the tuned-fixed `(regime, case, demand seed, simulator seed)` set. `matched_demand_units` is recorded and compared with the frozen minimum for every required regime.
- [x] Completed travel aggregates: executor outputs with a negative mean/median/p95 or p95 below median fail before status can become complete.
- [x] Usable replay topology: all 53 nodes require unique nonempty IDs, finite coordinates and explicit neighbor lists containing only known unique IDs; links must be objects with known endpoints. The browser core validates the same node contract before rendering.
- [x] Decoder-backed release media: `ffprobe` requires decodable PNG dimensions and an MP4 video stream with positive dimensions/duration. `pdfinfo` requires a nonzero page count and `pdftoppm` must render page one to a decodable PNG. These checks cover generated thesis figures, the compiled thesis and all three demo fallbacks.
- [x] Clean-checkout trust: verification version 2 records a full evidence commit and output hashes. The verifier checks that commit is an actual ancestor, the present tree is clean, code has not changed since the frozen commit, and release outputs have not changed since verification; arbitrary command/tool-version strings no longer satisfy the gate.

### R2 adversarial RED to GREEN

- Campaign RED: code was absent from expanded runs; new status provenance assertions failed, and two invalid travel aggregates reached the old trust boundary. GREEN: campaign suite passes with frozen code/runtime format requirements and immutable status bindings.
- Statistics RED: five candidate seeds using one cell each passed when tuned fixed had two. GREEN: aggregation refuses candidate/baseline cell-set asymmetry and acceptance counts candidate matched cells.
- Topology RED: four Python cases accepted missing/NaN coordinates, non-list neighbors and unknown neighbors; Node had no topology validator. GREEN: 9 replay/export Python tests and 5 viewer-core Node tests pass.
- Source/runtime RED: the new identity test initially failed collection because the module did not exist. GREEN: 3 tests cover dirty/code-drift Git state, Dockerfile hashing and rejection of a digest-shaped image absent from inspected RepoDigests. A real local probe verified `cityflowproject/cityflow@sha256:b57e...e32` and `docker/haichau-evaluation.Dockerfile` against Docker.
- Media RED: the decoder test initially failed collection because no validation module existed; the old 12-byte MP4/minimal PDF/signature-only PNG fixtures were accepted. GREEN: 4 direct media tests and verifier adversarial tests reject rehashed placeholders while accepting real generated media.
- Verifier GREEN: 14 tests pass, including actual temporary Git history/clean state, mocked inspected runtime identity, full numeric evidence, and decoder-valid media. The complete fixture remains an explicitly synthetic test fixture with a negative acceptance result.
- Python 3.6 RED/GREEN: the first focused container run exposed old Git rejecting `--porcelain=v1`; using portable `--porcelain` produced 66 passing focused tests. Docker marker collection then exposed optional matplotlib absence; module-level `importorskip` restored `make cf-test` to 1 passed, 1 skipped, 162 deselected.

### R2 verification

- Focused host Python: 90 passed.
- Focused Python 3.6.5 CityFlow image: 66 passed.
- Viewer core: 5 passed.
- Full host `make test`: 194 passed, 1 failed, 1 deselected. The sole failure remains the baseline missing Git-ignored `data/danang/roadnet_haichau.json` input.
- `make cf-test`: 1 passed, 1 skipped, 162 deselected.
- Live offline Chrome check: the new topology validation loaded the 53-node fixture, switched normal to PM peak, preserved synchronized metrics/detail rendering, and logged zero console warnings/errors. HTTP traffic remained localhost-only.
- Current verifier version 4 exits 1 with 13 dependency gates, including the new `source_revision` gate. No release artifact was created to clear them.

## Final-review trust-boundary remediation

- [x] Release execution provenance: `run_pending(..., executor=...)` remains available for
  unit fixtures but records `mode: injected` and `release_eligible: false`; the final audit,
  summarizer, replay CLI and `--verify-only` reject it. The production runner now uses only
  the library-owned Docker path with networking disabled and an immutable image.
- [x] Container-output binding: every release status stores the exact Docker argv, Docker
  container ID from `--cidfile`, actual execution Git head, inspected image identity, exit
  status and stdout/stderr hashes. Verification re-hashes both logs and compares the final
  stdout JSON with the resolved-config, metrics and optional replay artifacts.
- [x] Generated clean-checkout attestation: `scripts/attest_haichau_release.py` verifies a
  clean frozen checkout and actual Docker runtime, executes the canonical host, CityFlow,
  replay, Tectonic and pre-attestation audit commands, probes eleven tool versions, and
  writes version-3 records with exact argv/environment/exit/duration and hashed logs. The
  final gate validates the generator hash, command contract, Git ancestry/cleanliness,
  runtime identity, seven release hashes and every file under `final/runs`.
- [x] Full media decode: PNG validation decodes the complete selected image frame and MP4
  validation decodes the complete video stream through `ffmpeg -v error -xerror` after
  metadata checks. PDF page-one rendering passes through the same PNG decoder.
- [x] No positive synthetic release proof remains: the former all-green in-process fixture
  now explicitly asserts `complete=false` at the injected-executor and handwritten-record
  gates. It remains useful only for independent summary/thesis/demo mutation tests.

### Final-review adversarial RED to GREEN

- RED: 4/4 focused failures proved that an injected executor could omit provenance, a
  handwritten five-field record could complete the release, a corrupted PNG IDAT still
  exposed dimensions to ffprobe, and a truncated fast-start MP4 still exposed duration.
- GREEN: 48 focused campaign/attestation/media/export/runner/verifier tests passed before
  the allowed-dirty resume regression; the final focused set passed 52 tests. The broader
  eval/report/script group passed 118 tests on the committed implementation.
- Python 3.6.5 pinned-image check: 37 campaign/attestation/identity/statistics/runner tests
  passed (one pytest config warning). `make cf-test`: 1 passed, 1 skipped, 167 deselected.
- Viewer core: 5 Node tests passed.
- Full host `make test`: 200 passed, 1 failed, 1 deselected. The only failure remains the
  pre-existing absent Git-ignored `data/danang/roadnet_haichau.json` fixture.
- Dependency gap remains unchanged: no frozen protocol, 30-case release split, ten learned
  checkpoints, real campaign, derived thesis/demo artifacts or clean attestation exists on
  this branch. The generator was tested only in temporary fixtures; no release evidence was
  fabricated.

## Final R2 authenticated-execution remediation

- [x] Retained Docker proof: release runs no longer use `--rm`. The final verifier invokes
  a captured direct subprocess implementation for `docker container inspect` and
  `docker logs`, then matches the retained container's real ID, image ID/reference, frozen
  command, workdir, disabled network, project mount, stopped/zero-exit state and log hashes.
  A regex-valid hand-edited container ID is rejected when Docker cannot inspect it.
- [x] Non-injectable production attestation: `create_attestation` exposes only root,
  protocol and output path. The explicit test capture hook always writes
  `attestation_mode: synthetic_test` and `passed: false`; final validation accepts only
  `direct_subprocess` evidence created with the fixed command/tool contracts.
- [x] Final verifier execution: after validating the historical logs, it directly re-runs
  all five required release commands. It also reads the generator, seven release artifacts
  and every campaign run artifact from the attested Git commit and compares those blob
  hashes with both the current files and record.

### Final R2 adversarial RED to GREEN

- RED: a forged `network_campaign_docker` status with a fake 64-hex container ID reached no
  Docker inspection; the production attestation API exposed runner/command injection and a
  fake-success runner could mint `passed: true` evidence.
- GREEN: the fake retained-container record is rejected through a real Docker CLI even when
  `subprocess.run` is monkeypatched; the public production generator has no injection
  parameters; fake runners can create only synthetic/ineligible records. A Git-blob test
  proves committed evidence is read independently of a forged working-tree file.
- Focused final trust/media/verifier tests: 54 passed, including the Git-blob regression;
  broad eval/report/script suite: 120 passed. Pinned Python 3.6.5 suite: 39 passed with one config
  warning.
- Post-commit `make cf-test`: 1 passed, 1 skipped, 169 deselected. Full `make test`:
  203 passed, 1 failed, 1 deselected; the sole failure is still the absent ignored
  `data/danang/roadnet_haichau.json` baseline input.
- Frozen campaign and production attestation remain blocked on upstream release inputs; no
  stopped release container, release record or result artifact was fabricated.

## Final R3 Docker-stream remediation

- [x] Canonical container streams: release execution now uses detached `docker run` followed
  by `docker wait`; it obtains both canonical run streams only from `docker logs`. Host/client
  stderr is preserved separately in a hashed `docker-cli-diagnostics.json` artifact and is
  excluded from the container stderr receipt.
- [x] Retained verification: provenance version 3 binds the exact run/wait argv, container ID,
  run/wait stdout, diagnostic artifact, inspected receipt and canonical stdout/stderr. Direct
  verification still compares the retained container logs with the stored artifacts, so adding
  the platform warning to `stderr.log` or otherwise changing container output fails closed.
- RED: the platform-warning contract test failed because the old argv attached to the
  container and no diagnostic-channel contract existed.
- GREEN: focused campaign/runner/verifier tests passed 32 tests with one host-Docker test
  deselected; broad eval/report/script tests passed 121 with one host-Docker test deselected.
  The explicit host-Docker lifecycle test passed against immutable image
  `traffic-rl-cityflow-research@sha256:8a9461...0517` on arm64. A direct probe measured a
  152-byte Docker platform warning and zero bytes of container stderr, then proved canonical
  re-verification succeeds and a warning-contaminated `stderr.log` is rejected.
- Python 3.6.5 focused compatibility: 22 passed, 1 host-Docker test deselected. `make cf-test`:
  1 passed, 1 skipped, 171 deselected. The real release campaign remains blocked on the same
  upstream frozen protocol/case/checkpoint inputs; no release result was created.
- Final `make test`: 204 passed, 1 failed, 2 deselected. The only failure is the unchanged
  baseline test whose ignored `data/danang/roadnet_haichau.json` input is absent. One first
  Python 3.6 attempt saw emulated Git exit with SIGSEGV; an exact retry passed all 22 focused
  tests, and the generated ignored core file was removed.
