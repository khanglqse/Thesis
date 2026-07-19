# 3D A/B Replay Demo (deck.gl) — Design Spec

**Date:** 2026-07-19
**Status:** Approved by user ("Duyệt — làm luôn")
**Branch:** `demo/replay-3d`

## Problem

The 2D A/B replay demo (`frontend/replay_ab.html`) collapses each road's
per-lane signal states into ONE colored dot (`roadSignal`: any-green → green).
An intersection with 4 approaches shows 4 overlapping dots at city zoom, so the
viewer cannot tell **which approach is green**. The replay data already carries
one `g/r/i` character **per lane per road** — the collapse happens only in
rendering.

The user chose a 3D view (deck.gl) over 2D-only fixes, with per-lane signal
rendering so the original readability complaint is actually solved.

## Related work (grounds the design; usable in thesis Related Work)

- **MARLens** (IEEE TVCG 2024, arXiv:2410.01364) — visual analytics for MARL
  traffic signal control: replay of simulation scenarios + coordinated views to
  inspect agent decisions. Academic precedent for our A/B replay approach.
- **DTUMOS** (2023, PMC10057692) — city-scale web digital twin rendering 20k+
  vehicles smoothly **with deck.gl**. Direct precedent for the tech choice
  (our data: ≤1,480 vehicles/frame, 120 frames — far smaller).
- **sumo3Dviz** (arXiv:2604.19194, Apr 2026) — lightweight open-source 3D
  visualization for SUMO that explicitly avoids game engines; offline video
  only. Validates "lightweight 3D, no Unity/CARLA"; our interactive web page
  remains differentiated.
- Game-engine digital twins (Unity — Sci. Reports 2025; SUMO+CARLA — 6G-PATH
  2025, Frontiers 2023): high fidelity but heavy installs — rejected for a
  thesis-defense demo.

## Goals / Non-goals

**Goals**

1. New page `frontend/replay_3d.html`: two synchronized 3D panels
   (left default Fixed-Time, right default DQN), tilted-camera view of the real
   Hải Châu network, same scenario/controller/playback controls and scoreboard
   as the 2D page.
2. **Per-lane signal bars in 3D**: at each road's stop line, one upright bar
   per lane, green/red from the replay's per-lane status characters. This is
   the core fix.
3. Runs fully offline at demo time (vendored deck.gl, local data, localhost
   server).
4. Keep the 2D page untouched and cross-link the two pages.

**Non-goals**

- No live inference (the honesty pivot stands: this replays real CityFlow
  runs; on-screen note says so).
- No photorealism (no buildings, textures, glTF vehicles).
- No click-node inspector in this iteration (possible follow-up).

## Architecture

```
frontend/
  replay_3d.html      page: 2 deck.gl canvases + controls + scoreboard
  replay_3d.css       layout (mirrors replay_ab.css conventions)
  replay_3d.js        app wiring: deck instances, playback loop, sync, fetch
  replay_3d_core.js   PURE geometry/logic (UMD, Node-testable, no deck.gl)
  vendor/deck.min.js  vendored deck.gl UMD bundle (committed to git)
```

Data loading, parsing, and the scoreboard reuse `frontend/replay_ab_core.js`
(`parseRoadnet`, `parseReplay`, `waitHours`, `scoreboard`) unchanged.

### Vendored deck.gl

- Download `https://unpkg.com/deck.gl@9/dist.min.js` to
  `frontend/vendor/deck.min.js` once, commit it. Loaded via `<script>`; exposes
  global `deck` (`deck.Deck`, `deck.OrbitView`, `deck.PathLayer`,
  `deck.SolidPolygonLayer`).
- **Acceptance check in Task 1:** Playwright loads the page and roads render
  under an orbitable camera. If the v9 UMD bundle fails in-browser, fall back
  to `deck.gl@8.9.36/dist.min.js` (battle-tested standalone; same layer API for
  our usage). The chosen version is recorded in `docs/demo_replay_3d.md`.

### Views & camera

- One `deck.Deck` per panel, `views: new deck.OrbitView({orbitAxis: 'Z'})`,
  plain Cartesian meters (CityFlow world coords; +y = north, no flip — OrbitView
  shows +y up-screen at rotationOrbit 0).
- Initial `viewState` from `fitView(bounds, W, H)` (pure, in core module):
  `target=[cx, cy, 0]`, `zoom=log2(min(W/bw, H/bh)) - small pad`,
  `rotationX=45`, `rotationOrbit=0`, `minZoom/maxZoom` sane clamps.
- **Camera sync:** single shared `viewState` object; either panel's
  `onViewStateChange` writes it and re-applies to BOTH decks. "Reset camera"
  button restores `fitView` state.

### Layers (per panel, per frame)

| Layer | Type | Source | Notes |
|---|---|---|---|
| Roads | `PathLayer` | roadnet (static per scenario) | `getWidth = nLanes*3` m, `widthUnits:'meters'`, rounded joints, gray |
| Vehicles | `SolidPolygonLayer` extruded | frame cars | footprint = `carFootprint(x,y,angle,len,wid)` (rotated rect), `getElevation ≈ 1.6` m, palette = same 5 pastels as 2D page |
| Signals | `SolidPolygonLayer` extruded | frame tl + roadnet | quads from `laneBars(road.points, road.nLanes, statuses, {laneWidth:3, barLen:1.5, setback:4})`; `getElevation = 2.5` m; bright green `#2ecc40` / red `#ff4136`; status `i` → no bar |

Static road layer is built once per scenario; vehicle/signal layers get new
data arrays each displayed frame (≤1.5k cars — trivial for deck.gl).

### Pure core module `replay_3d_core.js` (UMD like replay_ab_core.js)

- `carFootprint(x, y, angle, len, wid)` → `[[x,y]×4]` rotated rectangle
  (angle in radians, CityFlow convention: 0 = +x, CCW).
- `laneBars(points, nLanes, statuses, opts)` → array of
  `{polygon: [[x,y]×4], color: 'g'|'r'}`; bars laid perpendicular to the last
  road segment, road width `nLanes*laneWidth` centered on the polyline,
  divided into `min(nLanes, statuses.length)` slots, set back `setback` meters
  from the endpoint; `i` slots skipped. Lane order follows replay status order
  across the road width (documented caveat: absolute left/right lane identity
  is not verified against the official viewer; per-approach color is what the
  demo claims).
- `fitView(bounds, W, H)` → initial OrbitView viewState (pure math).

### Page behavior (mirrors 2D page)

- Same scenario list + default (`haichau_rush`), same controller dropdowns
  (Fixed-Time / DQN / Max-Pressure / Random), play/pause, scrub slider, speed
  select, both panels frame-locked to one clock.
- Same stale-response protection: monotonic generation counter on
  scenario/controller loads.
- Scoreboard identical to 2D (reuses `scoreboard()` + real
  `comparison.json` numbers).
- Honest-framing note (Vietnamese): "Replay từ CityFlow thật (không phải suy
  luận trực tiếp)". Cross-links: 2D page ↔ 3D page.
- `scripts/serve_replay.py` prints the 3D URL alongside the 2D one.

## Testing

- `tests/replay_3d/core.test.cjs` (Node, like `tests/replay_ab/core.test.cjs`):
  - `carFootprint`: angle 0 → axis-aligned rect of len×wid; angle π/2 → swapped
    extents; centroid = (x,y).
  - `laneBars`: bar count = per-lane statuses minus `i`s; colors map g/r;
    bars perpendicular to road direction (dot product ≈ 0); setback respected;
    2-lane road with `["g","r"]` yields one green + one red bar at distinct
    offsets.
  - `fitView`: target = bounds center; zoom finite; wider bounds → smaller zoom.
- Playwright smoke: page loads with no console errors, two WebGL canvases,
  scoreboard shows real numbers, scrub changes frame, camera-sync hook
  (`window.__viewState` exposed for test) identical across panels after a
  programmatic view change.
- Existing suites must stay green: `pytest` and
  `node --test tests/replay_ab/*.test.cjs`.

## Global constraints

- Node tests must run on Node v25 with the glob form
  `node --test tests/replay_3d/*.test.cjs` (bare-dir arg is broken).
- No network calls at page runtime except same-origin fetches (CSP-friendly,
  offline demo).
- All UI copy in Vietnamese, matching the 2D page's tone/labels.
- Honest framing: never present the demo as live inference.
- Real numbers only: scoreboard reads `results/*/comparison.json`; never
  hard-code metric values in the page.
