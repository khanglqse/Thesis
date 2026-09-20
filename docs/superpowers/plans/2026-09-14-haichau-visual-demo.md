# Hai Chau visual demo implementation plan

> **For agentic workers:** Use superpowers:executing-plans to execute the assigned tasks. User explicitly requested Sol execution. Do not create new tests; use focused existing checks and manual visual verification.

**Goal:** Make the thesis demo show the actual modeled Hai Chau road network, changing traffic signals, distinguishable motorcycles/cars, and synchronized controller comparisons suitable for a 30-minute defense.

**Architecture:** Extend the existing offline Canvas replay viewer and generate a separate enriched demo bundle from the existing simulation assets. Preserve frozen research artifacts. The network overview and intersection close-up share one simulation clock across both controllers.

**Tech stack:** Existing Python exporters, CityFlow simulation, HTML/CSS/Canvas JavaScript; offline local serving.

**Spec:** User request of 2026-09-14: geographically recognizable Hai Chau; visible green/red signals; visible vehicle counts; visually distinct motorcycle/car boxes; plan and dispatch to Sol.

## Constraints and observed baseline

- The current viewer draws straight signal-adjacency links, not complete road/lane geometry. These must not be presented as physical streets.
- `NetworkReplayObserver._frame` currently emits an empty `vehicles` array. Vehicle movement cannot be recovered from queue totals alone.
- Node green/red currently encodes congestion, not signal state. Separate these meanings explicitly.
- Use source geometry in `datasets/haichau_network_v2/source/danang_haichau.net.xml` and the experiment's CityFlow roadnet; verify their coordinate correspondence before combining geometry.
- Scope is the modeled Hai Chau network with 53 controlled signals, not all of Da Nang. Demand remains synthetic and evidence-constrained; do not call it observed real traffic.
- No fabricated vehicle positions, vehicle classes, signal states, landmark coordinates, or improvements. Unknown vehicle classes remain labeled unknown. If class metadata is absent, disclose the limitation and implement explicit typed simulation demand as a separately labeled demo scenario before claiming motorcycle/car counts.
- Reuse trained checkpoints; do not retrain or launch a research sweep. Additional simulation runs are for exporting trajectories, with exact run provenance.
- Preserve frozen campaign files, metrics, checkpoints and hashes. Build a new bundle directory. Any new replay is identified separately and must not inherit acceptance or old metrics without checking equivalence.
- Keep tool calls and status reports sparse. No new automated tests. Do not install dependencies unless existing capabilities are insufficient.

## Task 1 — Data and geometry (Sol data worker)

**Files:** `src/traffic_rl/eval/network_replay.py`, its observer callers, `scripts/prepare_haichau_viewer_network.py`, and a separate enriched export entry point if necessary.

- [ ] Identify exact roadnet, demand, checkpoint and simulator configuration used by each selected replay; inspect vehicle class availability and simulator telemetry APIs.
- [ ] Export physical road polylines, lane geometry, junction positions and movement-to-phase mapping. Keep existing adjacency exclusively for neighborhood analysis. Preserve north orientation and aspect ratio. Include geometry source identifiers and hashes.
- [ ] Capture stable vehicle IDs, actual simulation positions or lane-plus-distance, heading, actual class, and dimensions. Capture signal states for each controlled movement, including any actual yellow/all-red state. Phase index alone must be mapped through the actual roadnet definitions.
- [ ] Record current active counts by available class, current queue, and explicit distinction between whole-network totals and vehicles rendered. Use a one-second sample interval where affordable; interpolate positions along lanes, never across unrelated edges or disappearing IDs. Signals change at recorded event times and are not interpolated.
- [ ] Start with a matched PM pair from existing controller settings. Export a short inspected segment first, then full normal/AM/PM replays as runtime permits; clearly label any incomplete scenario.
- [ ] Define the enriched schema and deliver a small valid sample to the UI worker before final integration. Keep old replay reading supported; missing telemetry shows unavailable rather than invented traffic.

**Acceptance:** Nonempty actual trajectories when traffic is present; all displayed vehicles traceable to telemetry; classes traceable to source definitions; road positions and signal movement associations consistent; saved provenance and run commands.

## Task 2 — Presentation viewer (Sol UI worker)

**Files:** `frontend/haichau_network_demo.html`, `frontend/haichau_network_demo.css`, `frontend/haichau_network_demo.js`, `frontend/haichau_network_demo_core.js`.

- [ ] Build a clear overview with actual street polylines, readable labels where source names exist, north indicator and explicit Hai Chau/53-signal scope. Use a light high-contrast road surface suitable for a projector. Avoid online tile dependence.
- [ ] Add synchronized pan/zoom and selected-intersection close-up for both controllers. Overview conveys network congestion; close-up reveals lanes, turning movements and vehicles. Click a node to open its detail; provide a return-to-network control.
- [ ] Draw red/green lamps or stop-line indicators per approach/movement from phase telemetry. Separate queue encoding from lamp colors; include textual state/legend so color is not the only cue.
- [ ] Draw motorcycles as narrow short boxes with an M marker, cars as wider longer boxes with a C marker; use distinct non-signal colors and persistent legend. Draw heading, preserve screen readability at junction scale, and label any other/unknown classes accurately.
- [ ] Display live current active vehicles, motorcycle/car counts when known, current queue, and DDQN-minus-fixed deltas. Label end-of-run statistics separately so Play visibly changes current values without misrepresenting final totals.
- [ ] Add a guided demo entry: PM peak, a documented informative time, synchronized clock and selected busy junction. Include Play/Pause, seek, reset and useful speed controls. Choose the start time from observed traces, without implying selected replay improvement proves every scenario.
- [ ] Normal fallback parity must be explained when present; bad or equal DDQN results must remain visible. Preserve provenance and aggregate evidence in an expandable secondary panel.
- [ ] Make missing telemetry explicit and keep legacy replays usable. Do not add decorative fake vehicle motion.

**Acceptance:** A viewer can identify controller, scenario, time, red/green movements, motorcycles, cars and counts within 10 seconds; both panels remain synchronized through seek, pause and scenario switching; text is legible at presentation resolution.

## Task 3 — Integration and defense handoff (Sol, after tasks 1–2)

**Files:** enriched bundle builder, new output under `results/haichau_network_v2/`, `docs/defense/demo-runbook.md`.

- [ ] Integrate schema and rebuild into a new bundle, updating all changed asset hashes correctly. Do not copy new UI into an old hash-verified bundle without rebuilding its manifest.
- [ ] Verify geometry against local source coordinates and inspect at least three geographically separated junctions. Verify full network extent and connections rather than judging by one screenshot.
- [ ] Manually inspect moving motorcycles/cars, phase changes, stopped queues, both controllers, Play/Pause, seeking and normal/AM/PM selection. Reconcile displayed counts with sampled telemetry. Run relevant existing checks for modified contracts; no new test files.
- [ ] Check offline reload, server startup and loading responsiveness; chunk trajectories if whole-file loads are too large. Record actual bundle size and any sampling/render limits.
- [ ] Save presentation screenshots and a concise 3–5 minute demo script: network scope → junction traffic and lamps → controller comparison → normal parity → evidence caveat.
- [ ] Report actual completed features, verified commands, local launch URL and remaining data limitations. Do not claim a live policy demo for a recorded replay.

## Dispatch ownership

### Approved presentation scope extension

The user additionally requires three explicit demo modes on the same matched network replay: Single junction, Linked junctions, and Whole network. Single junction shows actual approach lamps and typed vehicles. Linked junctions fits the selected signal and its upstream/downstream controlled neighbors to demonstrate connected operation using physical roads. Whole network fits the complete modeled geometry and all 53 controlled signals. Cameras and time remain synchronized between controllers in every mode. Counts distinguish visible viewport vehicles, exported vehicles, and whole-network totals. A geographically partial model must never be described as verified coverage of the entire administrative district. The five-minute demo visits all three modes; it does not substitute the legacy isolated-junction experiment.

- Sol data worker: data audit followed by telemetry/geometry implementation; no frontend edits.
- Sol UI worker: frontend implementation; consume the data worker's agreed schema; no campaign/export edits.
- Integrate only after both workers agree on data fields. Parent reviews evidence and handoff; no automatic retraining or research-result changes.
