# Research execution status

> **HISTORICAL STATUS SNAPSHOT (2026-09-07).** This records the empirical-anchor handoff,
> not release completion for the current 53-signal v2 study. For current release status, run
> `scripts/verify_haichau_thesis.py`; a v2 performance or demo claim requires `"complete": true`.

Updated: 2026-09-07 22:55 (Asia/Ho_Chi_Minh)

Active branch: `thesis/end-to-end` in `.worktrees/thesis-end-to-end`.
Foundation run: `results/research_foundation/20260907T133327743207Z`.

| Work package | State | Evidence / next gate |
|---|---|---|
| F0 snapshot | complete | 66 input files hashed in `inputs-before.json`; environment in `environment.json` |
| F1 baseline and simulator smoke | complete with recorded legacy-image repair | host: 85 Python tests; replay: 18 Node tests; CityFlow 60-second smoke in `smoke-cityflow.json` |
| F2 legacy claims audit | complete | `legacy-claims-audit.md`; old results are historical only |
| F3 research tooling | complete for thesis | web/browser research and local build tools available; optional Perplexity extension remains uninstalled |
| F4 literature review | complete for final manuscript | focused verified bibliography in `paper/references_verified.bib` |
| F5 data feasibility | complete for public sources | one observed peak intersection is usable; no raw multi-day Hai Chau corridor dataset found yet |
| F6 foundation handoff | complete | `survey-protocol.md` and `foundation-handoff.md` select the next code gates |
| T04 network and signal | complete for target pilot | pinned OSM reference plus isolated 300 m target; tested published 103-second program |
| T05 demand and simulator calibration | complete with stated limits | direct four-line camera cases separated from 12-movement estimates; lane backend passes full-hour safety; see `pilot-calibration.md` |
| T06 experiment protocol and runner | complete | split manifest, exact queue integral, pending accounting, safety output, and replay callback verified |
| T07–T10 training and evaluation | complete | five-seed DDQN, ablation, 105 primary held-out runs, and 120 sensitivity runs summarized |
| T11 thesis and slides | complete | 33-page thesis PDF and 15-slide editable PPTX built and visually inspected |
| T12 defense bundle | complete on test host | offline A/B replay, launcher port fallback, hashes, MP4/PDF/image fallback, browser QA, and runbook |

## Decisions made

1. The existing CityFlow Hai Chau runs remain a historical synthetic benchmark. They cannot support claims about observed Da Nang traffic demand.
2. The observed-data pilot will start at the Nguyen Thanh Nghi–Cach Mang Thang 8–2/9 signalized intersection using the published 2022 turning movements (6171 PCU/h at peak) and the reported 103-second plan.
3. SUMO 1.24 standard lanes are primary. The sublane model remains sensitivity-only because uncalibrated lateral behavior produced collisions.
4. The final protocol separates train, validation, and test demand groups and varies training, demand, and simulator seeds. A fixed test set is never used for checkpoint selection.
5. The defense path is offline replay A/B with a local manifest, plus MP4/PDF/image fallback. Training will never run during the presentation.

These decisions can be revised only by new evidence; revisions must be appended to the decision log rather than silently replacing history.
