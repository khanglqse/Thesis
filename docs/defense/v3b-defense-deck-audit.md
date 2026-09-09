# V3-B defense deck and demo audit

**Audit scope:** the tracked thesis deck, its generator, the released `v1` defense replay,
the defense runbook and Q&A, plus the archived browser-demo and presentation-result pages.
**Audit rule:** no result, replay, slide, screenshot, or spoken claim is eligible for the
53-signal V3-B defense unless it is generated from the final frozen V3 campaign and
`scripts/verify_haichau_thesis.py` reports `"complete": true`.

## Finding

The current PowerPoint and the only packaged replay are evidence for a different study:
a reconstructed, isolated SUMO junction controlled by Dueling DDQN. They must not be
relabeled as V3-B, Hai Chau network evidence, or a 53-signal result. The claim boundary is
especially important because the V3 network is OSM-derived with **synthetic network demand
constrained by Da Nang evidence**. It is not observed or calibrated district-wide demand.

The V3-B residual pilot document also says that it does not yet claim a traffic outcome.
Until the final campaign is accepted, the final slide must report the generated negative or
inconclusive decision rather than any improvement percentage.

## Artifacts that must be replaced or excluded

| Artifact | Exact section | Current claim or behavior | Required V3-B action |
|---|---|---|---|
| `presentation/thesis_defense_danang.pptx` | Slides 1--15 | The rendered deck is wholly single-junction: title and scope on slides 1--5; Dueling DDQN design on 6--8; headline 320.7%, 1.0%, and 34.5% results on 9--10; synthetic sensitivity on 11; 105-run safety result on 12; single-junction limits on 13; single-junction replay on 14; 34.5% conclusion on 15. | Replace the whole deck from a V3-B result-bound source. Keep an explicitly labelled single-junction anchor only if useful as background, with no contribution to the V3-B conclusion. |
| `scripts/build_defense_deck.mjs` | Slides 1--15, especially lines 49--65, 97--110, 119--128, 151--176, 182--223, 227--272 | Hard-codes all single-junction architecture, counts, result values, safety totals, and conclusion. Rebuilding it will recreate unsupported V3-B slides. | Do not rebuild the final deck from this script. Replace it with a generator that reads the hash-bound V3 summary and the generated thesis artifacts; fail if the report is incomplete or the hashes disagree. |
| `presentation/danang_thesis_defense_bundle_v1.zip` | Entire archive | Portable copy of the old deck/replay bundle. | Exclude from the V3-B laptop/USB set. Build a new portable folder only through `scripts/package_haichau_demo.py` after release verification. |
| `results/defense_bundle/v1/` | Entire bundle; `manifest.json` rows for normal and PM cases | Legacy SUMO single-junction fixed-time/Dueling-DDQN outputs, including 9.9 vs 15.3 and 152.5 vs 76.3 vehicle-hours. | Exclude from the V3-B demo. Do not copy its MP4, PDF, screenshot, or JSON into a new bundle. |
| `frontend/danang_defense.html` and `frontend/danang_defense.js` | HTML lines 5--16; JS scenario loader and aggregate/episode text | Browser title and panels claim published fixed time vs Dueling DDQN, a partial observed junction, representative seed 103, and five-seed aggregate result. | Exclude from the V3-B launcher and deck links. The V3 viewer must load only the release-gated 53-signal export and display generated provenance/status. |
| `scripts/package_defense_bundle.py`, `scripts/verify_defense_bundle.py`, `scripts/export_defense_replays.py` | Entire legacy path | Packages/verifies/exports the SUMO single-junction bundle; the exporter imports `SumoSingleJunctionEnv`. | Never use this path for V3-B. Use `build_haichau_demo_fallbacks.py`, `export_haichau_replays.py`, `serve_haichau_demo.py`, and `package_haichau_demo.py` only after the V3 verifier passes. |
| `docs/defense/demo-runbook.md` | “Legacy single-junction defense bundle”, lines 294--332 | Gives an executable legacy path and repeats the representative 50.0%, aggregate 34.5%, and normal 320.7% claims. | Retain as an archive only. Put the V3 53-signal path first and use only that path in rehearsal. Do not read the legacy five-minute script at defense. |
| `docs/defense/demo-qa.md` | Entire table, especially rows 12--13 | QA record validates the old PM/Normal metrics and aggregate labels. | Do not call it V3-B readiness. Create a new dated QA record after the V3 bundle has passed the final verifier and been tested on the presentation copy. |
| `docs/defense/questions-and-answers.md` | Lines 3--19 | Mixes single-junction answers (counts, collision, headway, Max-Pressure) with an early V3 scope answer. | Replace with V3-B Q&A generated/reviewed after results. Preserve the synthetic-OSM disclosure; remove any answer that presents 105-run DDQN behavior as network evidence. |
| `docs/demo_quickstart.md`, `docs/demo_replay_ab.md`, `docs/demo_replay_3d.md`, `docs/presentation_results.md` | All are marked archived legacy but contain old 53-node synthetic CityFlow performance tables and DDQN/DQN improvement values | Their warnings are good, but they remain unsafe sources for screenshots, speaking notes, or a new deck. | Keep archived labels and do not link them from the V3-B deck, runbook, or portable demo. Do not reuse headline values such as +37.1%, +40.1%, or −39.9%. |
| `scripts/build_presentation.py` | Demand sweep, improvement chart, and optimisation journey | Generates charts/tables from legacy `results/haichau*` rows and hard-coded historic values. | Do not run for V3-B presentation evidence. Generate tables/charts only from the frozen V3 final summary. |

## Required V3-B deck and demo contents

Build the final deck only after the V3 release gates succeed. The following checklist gives a
minimal defense structure; values marked **generated** must come from the frozen summary,
not hand-entered speaker notes or slide text.

1. **Scope and evidence boundary.** State: 53 controlled signals on an OSM-derived Hai
   Chau topology; CityFlow network demand is synthetic and constrained by Da Nang evidence.
   State plainly that JICA/DaCRISS are planning context and do not calibrate signal timings,
   routes, or flows. Do not say district-wide performance, real traffic, or citywide
   deployment.
2. **V3-B controller.** Identify the selected controller exactly as recorded in the frozen
   protocol. Explain the reference schedule and residual macro action at 300-second
   boundaries. Do not call it the legacy Dueling DDQN or imply CoLight graph attention.
3. **Experiment contract.** Show the frozen 30-case split, confirmation seeds 12--16,
   three regimes, matched demand units, baselines, checkpoint identity, CityFlow image
   digest, and predeclared acceptance thresholds. Seed 11 belongs only to selection/pilot.
4. **Result slide.** Render normal, AM peak, and PM peak result fields directly from
   `results/haichau_network_v2/final/summary.json`, including the interval, completion
   degradation, number of independent units, and the generated acceptance decision. A
   negative decision remains visible.
5. **Claim-boundary slide.** Separate evidence from assumptions: no observed district-wide
   demand, no calibrated network signal plans, no field safety or deployment claim. The
   empirical single-junction study may appear only as an anchor with its own scope label.
6. **Provenance/demo slide.** Show only the verified 53-signal viewer: the acceptance state,
   run/case IDs, controller, checkpoint and contract hashes, learning seed, and
   pending-demand fields. A single replay illustrates a case and never substitutes for the
   aggregate result.
7. **Conclusion.** Generate its text from acceptance status. If any gate fails, say which
   predeclared criterion failed and make no improvement/deployment conclusion.

## Defense-day release checklist

- [ ] Run `PYTHONPATH=src python3 scripts/verify_haichau_thesis.py` in the clean frozen
  checkout. Capture exit zero and a report whose `complete` field is `true`.
- [ ] Confirm the deck's summary hash, final report hash, and displayed figures/tables match
  the generated thesis-artifact manifest. Rebuild the deck if any source hash changes.
- [ ] Run `build_haichau_demo_fallbacks.py`, then `export_haichau_replays.py` with exactly
  six verified run IDs, then `serve_haichau_demo.py`; do not use a legacy export command.
- [ ] Verify the viewer shows exactly 53 signals, the synthetic-demand label, accepted or
  rejected status, and the selected replay provenance. Check normal, AM, and PM screens.
- [ ] Package only that canonical bundle with `package_haichau_demo.py`. On a second local
  copy, test loopback launch, seeking, all regimes, node selection, MP4, PDF, and PNG
  fallbacks while offline.
- [ ] Create a new V3-B QA record. It must identify the frozen commit, image digest, summary
  hash, deck hash, bundle hash, host/date, and projector rehearsal result.
- [ ] Search the staged defense folder and speaker notes for: `34.5%`, `320.7%`, `50.0%`,
  `Dueling DDQN`, `seed 103`, `published fixed`, `1 junction`, `+37.1%`, and `−39.9%`.
  Each match must either be removed or clearly labelled as the separate single-junction or
  archived legacy study.

## Sources used for this audit

- `docs/defense/demo-runbook.md` defines the V3 release-gated path, 53-signal scope,
  synthetic-demand disclosure, verified viewer fields, fallback order, and final preflight.
- `docs/research/haichau-v3b-residual-protocol.md` defines the V3-B residual controller and
  explicitly withholds an outcome claim before final release integration.
- `scripts/verify_haichau_thesis.py` validates the frozen 53-signal topology, V3 controller
  contract, final summary, thesis artifacts, and offline demo as one release decision.
