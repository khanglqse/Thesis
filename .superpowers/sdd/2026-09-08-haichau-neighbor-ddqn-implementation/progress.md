# Hai Chau neighbor DDQN implementation progress

- Branch: `feat/haichau-neighbor-ddqn`
- Worktree: `/Users/khanglq1/workplace/Thesis/traffic-rl/.worktrees/haichau-ddqn`
- Base commit: `4b65023`
- Runtime constraint: Python 3.6-compatible source under `src/` and training CLI.
- Evidence rule: record only commands actually run; do not infer smoke, pilot, or final results.

## Task status

- [x] Task 1: phase-centric neighbor encoder
- [x] Task 2: signal constraints, switch cost, service timers
- [x] Task 3: phase-scoring Double DQN and checkpoint contract
- [x] Task 4: balanced case sampler and replay
- [x] Task 5: validation regret and non-inferiority selection
- [x] Task 6 code/config/unit tests: multi-case trainer and training CLI
- [x] Task 6 runtime smoke gate: final 53-node contract, real CityFlow, updates > 0
- [ ] Task 6 pilot/final campaign: requires a separately authorized full-horizon run
- [x] Review C1/I1/M1: explicit phase-role contract, safe transition state machine,
  min-green-first arbitration, feasible max-red validation, lane-link movement count
- [x] Review I2-I5/M2 code gates: validation grid tuning, mandatory foundation
  verifier, deterministic negative-result checkpoint, audit/status artifacts, and
  smoke optimizer-update assertion
- [x] Review R2: maximum-red early scheduling/episode peak and end-to-end
  tuning-inclusive wall-time/profile projection
- [x] Foundation R3: source-bound phase semantics, movement service during
  compound stages, clearance-only lost time, and final contract integration

## RED/GREEN evidence

- Baseline: `PYTHONPATH=src pytest -q` -> 110 passed, 1 failed because Git-ignore `data/danang/roadnet_haichau.json` is absent from this worktree.
- Task 1 RED: `PYTHONPATH=src pytest tests/sim/test_phase_encoder.py -v` -> collection failed with expected `ModuleNotFoundError: traffic_rl.sim.phase_encoder`.
- Task 1 GREEN: `PYTHONPATH=src pytest tests/sim/test_phase_encoder.py tests/sim/test_encoder.py tests/network/test_roadnet_phases.py -v` -> 11 passed.
- Task 2 RED: `PYTHONPATH=src pytest tests/sim/test_multi_agent_constraints.py -v` -> 5 expected failures because the constructor did not accept `maximum_red`/`encoder`.
- Task 2 GREEN: `PYTHONPATH=src pytest tests/sim/test_multi_agent_constraints.py tests/sim/test_multi_agent_env.py tests/sim/test_intersection.py -v` -> 19 passed.
- Task 3 RED: `PYTHONPATH=src pytest tests/agents/test_phase_ddqn.py -v` -> collection failed with expected `ModuleNotFoundError: traffic_rl.agents.phase_ddqn`.
- Task 3 GREEN: `PYTHONPATH=src pytest tests/agents/test_phase_ddqn.py tests/agents/test_dqn.py -v` -> 17 passed, including numeric Double DQN target and 100-update stability tests.
- Task 4 RED: `PYTHONPATH=src pytest tests/train/test_case_sampler.py tests/train/test_network_replay.py -v` -> collection failed with expected missing sampler/replay modules.
- Task 4 GREEN: same command -> 4 passed, including ring-buffer overwrite coverage.
- Task 5 RED: `PYTHONPATH=src pytest tests/eval/test_checkpoint_selection.py -v` -> collection failed with expected missing checkpoint-selection module.
- Task 5 GREEN: same command -> 6 passed, including normal/completion gates and deterministic tie-breaking.
- Task 6 RED: `PYTHONPATH=src pytest tests/train/test_network_trainer.py -v` -> collection failed with expected missing network trainer.
- Task 6 GREEN (trainer): same command -> 2 passed; after tier-resolution RED, 3 passed.
- Completion fail-closed RED: missing completion was incorrectly eligible and env lacked arrived/completion fields -> 2 expected failures.
- Completion fail-closed GREEN: checkpoint/environment focused suites -> 20 passed; CityFlow runtime now tracks seen/active vehicle IDs when the engine exposes no finished counter.
- Task 6 integration unit suite: `PYTHONPATH=src pytest tests/train/test_network_trainer.py tests/train/test_case_sampler.py tests/train/test_network_replay.py tests/agents/test_phase_ddqn.py -v` -> 12 passed.
- Final host verification: `PYTHONPATH=src pytest -q --ignore=tests/network/test_roadnet_neighbors.py` -> 140 passed, 1 deselected.
- Python 3.6 runtime verification in `traffic-rl-cityflow-research:v2`: selected new suites -> 30 passed (one pytest config warning because pytest 6.2.5 does not recognize the host `pythonpath` option).
- Read-only local roadnet encoder smoke: 53 agents, `max_green=6`, feature shape `(6, 12)` for every agent.
- `python3 -m compileall -q src/traffic_rl scripts/train_haichau_network.py` and `git diff --check` -> exit 0.
- Review RED C1: short non-empty subset phases appeared as actions and a 53-node
  probe found 10 signals without empty clearance. GREEN: 27 phase/env tests; the
  final explicit foundation contract loads 53/53 signals with zero errors,
  selectable count 2-3, and safe directed transition paths.
- Review RED long path: a declared 9-second transition failed construction at a
  5-second action interval. GREEN: the transition state machine carries exact
  phase durations across decisions; the corrected 53-node contract includes
  paths up to 18 seconds and now constructs successfully.
- Review RED I2-I5/M2: imports for reporting selection/hash contract were absent;
  a rejected verifier was trusted, Fixed-Time used a literal 40 seconds, and
  smoke could finish with zero updates. GREEN focused suite: 44 passed; fake
  smoke covered all regimes with 6 optimizer updates and a reloadable selected
  checkpoint.
- Final review host verification: `155 passed, 1 deselected` (the deselected
  pre-foundation neighbor test reads an ignored local file).
- Final Python 3.6.5 verification: `44 passed`, with only the known pytest
  `pythonpath` config warning.
- R2 maximum-red RED reproduced the hidden 198-second peak behind a reported
  20 seconds on a declared 18-second path. GREEN: early deadline reservation,
  decision-granularity feasibility, and episode peak tracking pass two- and
  three-green adversarial tests. A read-only 53-signal/3600-step contract run
  reported a true peak of 178 seconds against the 180-second bound on the
  superseded pre-R3 contract; the final R3 real smoke evidence is recorded below.
- R2 timing RED showed tuning time absent from `wall_time_seconds`. GREEN:
  focused host/Python 3.6 suites each pass 36 tests; summary records foundation,
  baseline-tuning, training/validation, and measured end-to-end time, while the
  five-seed profile projects from end-to-end elapsed.
- Foundation R3 RED: compound service stages were counted as intergreen and
  their declared movements did not reset maximum-red timers; on the final
  contract this produced a 190-second movement peak. GREEN: role-aware service
  and movement-deadline scheduling pass focused tests; the 53-signal/3600-step
  deterministic probe reached 144 seconds.
- Final R3 fresh verification after runtime smoke: host full suite
  `163 passed, 1 deselected`; Python 3.6.5 focused suite `53 passed`; compileall and
  `git diff --check` exited zero.
- Final re-review RED: the default verifier import failed under file-script Make
  invocation, the `final` Make target was absent, and current maximum-red telemetry
  omitted movement timers outside selectable projections. GREEN: three focused
  regression tests pass; the full host suite passes 166 tests and the pinned
  Python 3.6.5 focused suite passes 56 tests.

## Runtime evidence

- Final foundation evidence HEAD: `a186d9a62aaf9a44f7db052000c7293464de9669`; phase-contract SHA-256: `41c10aa7de5da3c7cd215577a7929ee8495ba3317d8e094a9d92cdb90611acae`.
- The final contract loads 53 controlled signals, 107 selectable greens, 127
  transition phases, and 10 compound-service stages. Exact roles are 107
  `selectable_green`, 10 `compound_service`, 116 `clearance_yellow`, and one
  `all_red`.
- Documented production target `make haichau-train-smoke LEARNING_SEED=11`
  completed in the pinned `traffic-rl-cityflow-research:v2` image without any
  import-path override. Its prerequisite verifier returned `status: verified`,
  then the trainer independently loaded the verifier from the requested root.
- The production smoke visited normal/PM peak/AM peak with 53 agents each, made
  25 optimizer updates, reloaded checkpoint `step-3` for 120 steps, and retained
  `ineligible_negative_result`. Train episode maximum-red peaks were 106, 120,
  and 106 seconds against the 180-second bound.
- Trainer end-to-end wall time was 373.009 seconds, including 88.800 seconds of
  internal foundation verification, 207.232 seconds of Fixed-Time tuning, and
  53.687 seconds of validation. Scope was
  `foundation_verification_through_artifact_verification`. The Make prerequisite
  verifier is an additional independent gate before this measured CLI scope.
- Smoke artifacts existed only in the disposable integration checkout and were
  deleted with it. No foundation dataset or result was copied or committed.
- No real pilot or final result is claimed. Runs against foundation `e7b41e3`
  remain invalidated and deleted after route-family leakage review.

## Blockers and dependencies

- The final leak-free foundation is available and the real smoke gate passed. A
  full-horizon pilot/five-seed campaign remains outside this implementation run.
- The DDQN production loader requires manifest `phase_contract.path/sha256`,
  checks the artifact and roadnet hashes, and validates the exact 53-agent role
  partition plus every directed transition. Deterministic phase derivation remains
  available only to small unit fixtures and legacy callers; the training CLI does
  not use it.
- The smoke reporting checkpoint is intentionally ineligible because it is a
  negative validation result. Test evaluation remains closed until a later
  full-horizon candidate satisfies validation non-inferiority with complete
  completion evidence.
