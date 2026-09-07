# Research execution status

Updated: 2026-09-07 (Asia/Ho_Chi_Minh)

Active branch: `thesis/end-to-end` in `.worktrees/thesis-end-to-end`.
Foundation run: `results/research_foundation/20260907T133327743207Z`.

| Work package | State | Evidence / next gate |
|---|---|---|
| F0 snapshot | complete | 66 input files hashed in `inputs-before.json`; environment in `environment.json` |
| F1 baseline and simulator smoke | complete with recorded legacy-image repair | host: 85 Python tests; replay: 18 Node tests; CityFlow 60-second smoke in `smoke-cityflow.json` |
| F2 legacy claims audit | complete | `legacy-claims-audit.md`; old results are historical only |
| F3 research tooling | in progress | web/browser tools available; Chrome Web Store listing verified; UI provider rejected opening a new Chrome tab, installation remains pending |
| F4 literature review | in progress | initial matrix created; full-text extraction remains |
| F5 data feasibility | complete for public sources | one observed peak intersection is usable; no raw multi-day Hai Chau corridor dataset found yet |
| F6 foundation handoff | complete | `survey-protocol.md` and `foundation-handoff.md` select the next code gates |
| T04–T06 network, demand, calibration | in progress | pinned OSM pilot, 3 demand presets and safe route smoke built; signal program/controller calibration next |
| T07–T10 training and evaluation | pending | blocked only by implementation, not by user input |
| T11 thesis and slides | pending | generated after final experiment tables |
| T12 defense bundle | pending | legacy replay audited; final artifact not yet certified |

## Decisions made

1. The existing CityFlow Hai Chau runs remain a historical synthetic benchmark. They cannot support claims about observed Da Nang traffic demand.
2. The observed-data pilot will start at the Nguyen Thanh Nghi–Cach Mang Thang 8–2/9 signalized intersection using the published 2022 turning movements (6171 PCU/h at peak) and the reported 103-second plan.
3. SUMO 1.24 with the sublane model is the primary pilot simulator because motorcycle side-by-side and lateral behavior are material. CityFlow remains the scalability and legacy comparison backend.
4. The final protocol separates train, validation, and test demand groups and varies training, demand, and simulator seeds. A fixed test set is never used for checkpoint selection.
5. The defense path is offline replay A/B with a local manifest, plus MP4/PDF fallback. Training will never run during the presentation.

These decisions can be revised only by new evidence; revisions must be appended to the decision log rather than silently replacing history.
