# 3D A/B Replay Demo (deck.gl) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `frontend/replay_3d.html` page: two camera-synced 3D deck.gl panels replaying real CityFlow runs (default Fixed-Time vs DQN) with per-lane 3D signal bars, on the vendored offline deck.gl bundle.

**Architecture:** Pure geometry in `frontend/replay_3d_core.js` (UMD, Node-tested); app wiring in `frontend/replay_3d.js`; data parsing/scoreboard reused from `frontend/replay_ab_core.js`. Spec: `docs/superpowers/specs/2026-07-19-replay-3d-demo-design.md`.

**Tech Stack:** deck.gl UMD (vendored, global `deck`), vanilla JS/CSS, Node `node:test`, Python http server (`scripts/serve_replay.py`).

## Global Constraints

- Node tests run as `node --test tests/replay_3d/*.test.cjs` (glob form — bare dir broken on Node v25).
- Page makes NO network calls except same-origin fetches; must work offline once served.
- All UI copy in Vietnamese, same tone as `frontend/replay_ab.html`; on-page honest-framing note: "Replay từ CityFlow thật (không phải suy luận trực tiếp)".
- Never hard-code metric numbers in pages; scoreboard reads `results/<sc>/comparison.json` via `ReplayAB.scoreboard`.
- Do not modify `frontend/replay_ab_core.js`, `frontend/replay_ab.js`, or any Python under `src/`.
- Existing suites must stay green: `python3 -m pytest -q` and `node --test tests/replay_ab/*.test.cjs`.
- Coordinates are CityFlow world meters; +y is north; do NOT flip y (OrbitView shows +y up-screen).
- Angle convention: radians, 0 = +x axis, counter-clockwise.

---

### Task 1: Pure geometry core `replay_3d_core.js` + Node tests

**Files:**
- Create: `frontend/replay_3d_core.js`
- Test: `tests/replay_3d/core.test.cjs`

**Interfaces:**
- Consumes: `frontend/replay_ab_core.js` (`parseRoadnet`, `parseReplay`) — in tests only, to run against real fixtures.
- Produces (used verbatim by Task 3):
  - `carFootprint(x, y, angle, len, wid) -> [[x,y],[x,y],[x,y],[x,y]]`
  - `laneBars(points, nLanes, statuses, opts) -> [{polygon:[[x,y]×4], status:'g'|'r'}]`
  - `fitView(bounds, W, H) -> {target:[x,y,0], zoom, rotationX:45, rotationOrbit:0, minZoom, maxZoom}`
  - UMD global name in browser: `window.Replay3D`.

- [ ] **Step 1: Write the failing tests** — `tests/replay_3d/core.test.cjs`:

```js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const R3 = require("../../frontend/replay_3d_core.js");
const RAB = require("../../frontend/replay_ab_core.js");

test("carFootprint axis-aligned at angle 0, centered", () => {
  const p = R3.carFootprint(10, 20, 0, 4, 2);
  assert.equal(p.length, 4);
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...xs) - Math.min(...xs) - 4) < 1e-9);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 2) < 1e-9);
  assert.ok(Math.abs(xs.reduce((a, b) => a + b, 0) / 4 - 10) < 1e-9);
  assert.ok(Math.abs(ys.reduce((a, b) => a + b, 0) / 4 - 20) < 1e-9);
});

test("carFootprint rotated pi/2 swaps extents", () => {
  const p = R3.carFootprint(0, 0, Math.PI / 2, 4, 2);
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...xs) - Math.min(...xs) - 2) < 1e-9);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 4) < 1e-9);
});

test("laneBars: g/r bars, i skipped, set back from endpoint, distinct lanes", () => {
  const points = [{ x: 0, y: 0 }, { x: 100, y: 0 }]; // travel +x
  const bars = R3.laneBars(points, 3, ["g", "i", "r"],
    { laneWidth: 3, barLen: 1.5, setback: 4 });
  assert.equal(bars.length, 2);
  assert.deepEqual(bars.map((b) => b.status), ["g", "r"]);
  for (const b of bars)
    for (const [x] of b.polygon) assert.ok(x > 95 && x < 97.1, "setback ~4m, got x=" + x);
  const mean = (b) => b.polygon.map((q) => q[1]).reduce((a, c) => a + c, 0) / 4;
  assert.ok(Math.abs(mean(bars[0]) - mean(bars[1])) >= 3, "bars in distinct lane slots");
  const ys = bars[0].polygon.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 3) < 1e-9, "bar spans one laneWidth");
});

test("laneBars: degenerate inputs give []", () => {
  assert.deepEqual(R3.laneBars([{ x: 0, y: 0 }], 2, ["g"], {}), []);
  assert.deepEqual(R3.laneBars([{ x: 0, y: 0 }, { x: 1, y: 0 }], 2, null, {}), []);
});

test("fitView: centered target, finite zoom, wider bounds -> smaller zoom", () => {
  const v = R3.fitView({ minX: 0, maxX: 1000, minY: 0, maxY: 500 }, 640, 480);
  assert.deepEqual(v.target, [500, 250, 0]);
  assert.ok(Number.isFinite(v.zoom));
  assert.equal(v.rotationX, 45);
  const v2 = R3.fitView({ minX: 0, maxX: 2000, minY: 0, maxY: 500 }, 640, 480);
  assert.ok(v2.zoom < v.zoom);
});

test("laneBars on real haichau_rush frame 0 produces >0 bars", () => {
  const root = path.join(__dirname, "..", "..");
  const rn = RAB.parseRoadnet(JSON.parse(fs.readFileSync(
    path.join(root, "data/danang/replay_roadnet_haichau_rush.json"), "utf8")));
  const line0 = fs.readFileSync(
    path.join(root, "results/haichau_rush/demo/replay_dqn_demo.txt"), "utf8").split("\n")[0];
  const step = RAB.parseReplay(line0)[0];
  let total = 0;
  for (const road of rn.roads) {
    const st = step.tl[road.id];
    if (st) total += R3.laneBars(road.points, road.nLanes, st, {}).length;
  }
  assert.ok(total > 0, "expected some g/r bars in frame 0, got " + total);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/replay_3d/*.test.cjs`
Expected: FAIL (`Cannot find module '../../frontend/replay_3d_core.js'`)

- [ ] **Step 3: Implement `frontend/replay_3d_core.js`** (complete file):

```js
// Pure geometry for the 3D A/B replay demo. Browser (window.Replay3D) + Node.
// No deck.gl dependency here — everything below is plain math, unit-tested.
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Replay3D = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Rotated-rectangle footprint. angle: radians, 0 = +x, CCW (CityFlow replay).
  function carFootprint(x, y, angle, len, wid) {
    const dx = Math.cos(angle), dy = Math.sin(angle);
    const nx = -dy, ny = dx;
    const hl = len / 2, hw = wid / 2;
    return [
      [x + dx * hl + nx * hw, y + dy * hl + ny * hw],
      [x + dx * hl - nx * hw, y + dy * hl - ny * hw],
      [x - dx * hl - nx * hw, y - dy * hl - ny * hw],
      [x - dx * hl + nx * hw, y - dy * hl + ny * hw],
    ];
  }

  // Per-lane stop bars near the end of a road polyline. One slot per lane
  // across the road width (nLanes*laneWidth, centered on the polyline); slot i
  // colored by statuses[i] ('g'|'r'; 'i' = no light -> skipped). Lane order
  // follows replay status order across the width; per-approach color is the
  // claim, absolute left/right lane identity is not (documented caveat).
  function laneBars(points, nLanes, statuses, opts) {
    opts = opts || {};
    const laneWidth = opts.laneWidth || 3;
    const barLen = opts.barLen || 1.5;
    const setback = opts.setback || 4;
    if (!statuses || !points || points.length < 2) return [];
    const p1 = points[points.length - 1], p0 = points[points.length - 2];
    let dx = p1.x - p0.x, dy = p1.y - p0.y;
    const L = Math.hypot(dx, dy) || 1;
    dx /= L; dy /= L;                     // direction of travel
    const nx = -dy, ny = dx;              // left normal
    const cx = p1.x - dx * setback, cy = p1.y - dy * setback;
    const n = Math.min(nLanes || 1, statuses.length);
    const total = (nLanes || 1) * laneWidth;
    const bx = dx * (barLen / 2), by = dy * (barLen / 2);
    const bars = [];
    for (let i = 0; i < n; i++) {
      const s = statuses[i];
      if (s !== "g" && s !== "r") continue;
      const off0 = -total / 2 + i * laneWidth, off1 = off0 + laneWidth;
      bars.push({
        status: s,
        polygon: [
          [cx - bx + nx * off0, cy - by + ny * off0],
          [cx - bx + nx * off1, cy - by + ny * off1],
          [cx + bx + nx * off1, cy + by + ny * off1],
          [cx + bx + nx * off0, cy + by + ny * off0],
        ],
      });
    }
    return bars;
  }

  // Initial OrbitView viewState fitting bounds into a W×H viewport.
  // OrbitView zoom is log2(pixels per world unit).
  function fitView(bounds, W, H) {
    const bw = (bounds.maxX - bounds.minX) || 1;
    const bh = (bounds.maxY - bounds.minY) || 1;
    const zoom = Math.log2(Math.min(W / bw, H / bh)) - 0.15;
    return {
      target: [(bounds.minX + bounds.maxX) / 2, (bounds.minY + bounds.maxY) / 2, 0],
      zoom: zoom,
      rotationX: 45,
      rotationOrbit: 0,
      minZoom: zoom - 2,
      maxZoom: zoom + 8,
    };
  }

  return { carFootprint, laneBars, fitView };
});
```

- [ ] **Step 4: Run tests to verify pass**

Run: `node --test tests/replay_3d/*.test.cjs`
Expected: 6/6 PASS

- [ ] **Step 5: Regression + commit**

Run: `node --test tests/replay_ab/*.test.cjs` (expected 5/5 PASS)
```bash
git add frontend/replay_3d_core.js tests/replay_3d/core.test.cjs
git commit -m "feat(3d): pure geometry core — car footprints, per-lane signal bars, fitView"
```

---

### Task 2: Vendor deck.gl + page skeleton (roads under synced orbit cameras)

**Files:**
- Create: `frontend/vendor/deck.min.js` (downloaded, committed)
- Create: `frontend/replay_3d.html`, `frontend/replay_3d.css`, `frontend/replay_3d.js` (skeleton — Task 3 replaces the JS wholesale)
- Modify: `scripts/serve_replay.py` (print the 3D URL after the 2D URL line)

**Interfaces:**
- Consumes: `window.ReplayAB.parseRoadnet` (Task 0/existing), `window.Replay3D.fitView` (Task 1), global `deck` from the vendored bundle.
- Produces: page skeleton + DOM ids used by Task 3: `scenario`, `play`, `scrub`, `clock`, `speed`, `reset-cam`, `ctrl-left`, `ctrl-right`, `deck-left`, `deck-right`, `scoreboard`. Test hooks `window.__viewState`, `window.__decksReady` (Promise resolving after first road render).

- [ ] **Step 1: Vendor the bundle**

```bash
mkdir -p frontend/vendor
curl -sSL -o frontend/vendor/deck.min.js "https://unpkg.com/deck.gl@9/dist.min.js"
head -c 300 frontend/vendor/deck.min.js   # note the resolved version banner for the docs
git check-ignore frontend/vendor/deck.min.js && echo "IGNORED — fix .gitignore" || echo "ok, tracked"
grep -c "OrbitView" frontend/vendor/deck.min.js   # expected >= 1
grep -c "SolidPolygonLayer" frontend/vendor/deck.min.js   # expected >= 1
```
If either grep returns 0 or the in-browser check in Step 5 fails, re-download pinned fallback: `curl -sSL -o frontend/vendor/deck.min.js "https://unpkg.com/deck.gl@8.9.36/dist.min.js"` and note the version used.

- [ ] **Step 2: Write `frontend/replay_3d.html`** (complete file):

```html
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo 3D — Fixed-Time vs DQN (Hải Châu)</title>
<link rel="stylesheet" href="replay_3d.css">
</head>
<body>
<header>
  <h1>So sánh 3D: <span id="left-title">Cố định (Fixed-Time)</span> vs <span id="right-title">RL (DQN)</span> — mạng Hải Châu (53 nút đèn)</h1>
  <p class="note">Replay từ CityFlow thật (không phải suy luận trực tiếp) ·
     Thanh đứng tại vạch dừng = đèn theo từng làn (xanh/đỏ) ·
     <a href="replay_ab.html">Xem bản 2D</a></p>
</header>
<section class="controls">
  <label>Kịch bản <select id="scenario"></select></label>
  <button id="play">▶︎ Chạy</button>
  <input id="scrub" type="range" min="0" max="119" value="0">
  <span id="clock">t = 0s</span>
  <label>Tốc độ <select id="speed">
    <option value="100">1×</option><option value="50">2×</option><option value="25">4×</option>
  </select></label>
  <button id="reset-cam">Đặt lại camera</button>
</section>
<section class="panels">
  <div class="panel">
    <label>Trái: <select id="ctrl-left"></select></label>
    <div id="deck-left" class="deck-holder"></div>
  </div>
  <div class="panel">
    <label>Phải: <select id="ctrl-right"></select></label>
    <div id="deck-right" class="deck-holder"></div>
  </div>
</section>
<section id="scoreboard" class="scoreboard"></section>
<p class="note">Kéo chuột: xoay · Shift+kéo (hoặc chuột phải): trượt · Lăn: thu-phóng. Hai khung khoá cùng camera và cùng thời điểm.</p>
<script src="vendor/deck.min.js"></script>
<script src="replay_ab_core.js"></script>
<script src="replay_3d_core.js"></script>
<script src="replay_3d.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `frontend/replay_3d.css`** (complete file):

```css
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif;
       background: #14181c; color: #e8ebed; }
header, .controls, .scoreboard, p.note { padding: 8px 16px; }
h1 { font-size: 18px; margin: 6px 0; }
a { color: #7fd4ff; }
.note { color: #9fb0bb; margin: 2px 0; }
.controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.controls input[type="range"] { flex: 1 1 240px; }
button, select { background: #232a31; color: #e8ebed; border: 1px solid #3a444d;
                 border-radius: 6px; padding: 4px 10px; font: inherit; }
button:hover { background: #2d363f; cursor: pointer; }
.panels { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 0 16px; }
.panel label { display: block; padding: 4px 0; color: #cfd8de; }
.deck-holder { position: relative; height: 62vh; min-height: 340px;
               border: 1px solid #3a444d; border-radius: 8px; overflow: hidden;
               background: #1b2127; }
.deck-holder canvas { border-radius: 8px; }
.scoreboard { display: flex; gap: 16px; }
.score { background: #1b2127; border: 1px solid #3a444d; border-radius: 8px;
         padding: 10px 14px; display: flex; flex-direction: column; gap: 2px; }
.score b { font-size: 15px; }
.err { color: #ff8a80; padding: 8px 16px; }
@media (max-width: 900px) { .panels { grid-template-columns: 1fr; } }
```

- [ ] **Step 4: Write skeleton `frontend/replay_3d.js`** (complete file; Task 3 replaces it — keep the same helper names):

```js
(function () {
  "use strict";
  const RAB = window.ReplayAB, R3 = window.Replay3D;
  const DEFAULT_SCENARIO = "haichau_rush";
  const ROADNET = (sc) => `/data/danang/replay_roadnet_${sc}.json`;

  const decks = {};
  let viewState = null, fitState = null;

  function roadLayer(roadnet) {
    return new deck.PathLayer({
      id: "roads",
      data: roadnet.roads,
      getPath: (r) => r.points.map((p) => [p.x, p.y]),
      getWidth: (r) => r.nLanes * 3,
      widthUnits: "meters",
      widthMinPixels: 1,
      jointRounded: true,
      capRounded: true,
      getColor: [138, 160, 173],
    });
  }

  function applyViewState(vs) {
    viewState = vs;
    window.__viewState = vs; // test hook
    decks.left.setProps({ viewState: vs });
    decks.right.setProps({ viewState: vs });
  }

  function makeDeck(el) {
    return new deck.Deck({
      parent: el,
      views: new deck.OrbitView({ orbitAxis: "Z" }),
      controller: true,
      viewState: { target: [0, 0, 0], zoom: 0, rotationX: 45, rotationOrbit: 0 },
      onViewStateChange: (e) => applyViewState(e.viewState),
      layers: [],
    });
  }

  function showError(err) {
    const el = document.createElement("p");
    el.className = "err";
    el.textContent = "Lỗi tải dữ liệu: " + err.message;
    document.body.appendChild(el);
  }

  window.__decksReady = new Promise((resolve, reject) => {
    const holderL = document.getElementById("deck-left");
    const holderR = document.getElementById("deck-right");
    decks.left = makeDeck(holderL);
    decks.right = makeDeck(holderR);
    document.getElementById("reset-cam").addEventListener("click", () => {
      if (fitState) applyViewState(Object.assign({}, fitState));
    });
    fetch(ROADNET(DEFAULT_SCENARIO))
      .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then((data) => {
        const rn = RAB.parseRoadnet(data);
        fitState = R3.fitView(rn.bounds, holderL.clientWidth, holderL.clientHeight);
        applyViewState(Object.assign({}, fitState));
        decks.left.setProps({ layers: [roadLayer(rn)] });
        decks.right.setProps({ layers: [roadLayer(rn)] });
        resolve(true);
      })
      .catch((err) => { showError(err); reject(err); });
  });
})();
```

- [ ] **Step 5: Verify in a real browser (Playwright)**

Start server: `python3 scripts/serve_replay.py --no-browser --port 8080` (background).
With Playwright (MCP if free, else a `npx playwright` script), load `http://localhost:8080/frontend/replay_3d.html` and check: no console errors; `await window.__decksReady` resolves; two canvases exist; screenshot shows the road network in BOTH panels; after `window.__viewState` is programmatically replaced via a drag on the left panel, the right panel's camera visibly matches (take before/after screenshots).
If the deck.gl v9 bundle throws at load, apply the Step-1 fallback (v8.9.36) and re-verify.

- [ ] **Step 6: `scripts/serve_replay.py`** — after the existing "A/B replay" print line, add:

```python
    print("3D A/B replay (deck.gl):                       "
          "http://localhost:{}/frontend/replay_3d.html".format(args.port))
```

- [ ] **Step 7: Commit**

```bash
git add frontend/vendor/deck.min.js frontend/replay_3d.html frontend/replay_3d.css frontend/replay_3d.js scripts/serve_replay.py
git commit -m "feat(3d): vendor deck.gl + skeleton page — roads under camera-synced dual OrbitView"
```

---

### Task 3: Playback, vehicles, per-lane signal bars, A/B controls, scoreboard

**Files:**
- Modify: `frontend/replay_3d.js` (replace wholesale with the complete file below)

**Interfaces:**
- Consumes: DOM ids from Task 2; `Replay3D.carFootprint/laneBars/fitView` (Task 1); `ReplayAB.parseRoadnet/parseReplay/scoreboard`; layer classes `deck.PathLayer`, `deck.SolidPolygonLayer`, `deck.OrbitView`.
- Produces: test hook `window.__replay3d = { state: S, applyViewState }` for the Task 4 smoke test.

- [ ] **Step 1: Replace `frontend/replay_3d.js`** with (complete file):

```js
(function () {
  "use strict";
  const RAB = window.ReplayAB, R3 = window.Replay3D;

  const SCENARIOS = [
    ["haichau_rush", "Cao điểm thực (rush)"],
    ["danang_peak", "Đà Nẵng peak"],
    ["haichau_peak", "Cao điểm quá tải (peak)"],
    ["haichau", "Quá tải nặng (haichau)"],
  ];
  const DEFAULT_SCENARIO = "haichau_rush";
  const CTRLS = [["fixed_time", "Cố định (Fixed-Time)"], ["dqn", "RL (DQN)"],
                 ["max_pressure", "Max-Pressure"], ["random", "Ngẫu nhiên"]];
  const CTRL_TO_ROW = { dqn: "DQN", fixed_time: "FixedTime",
                        max_pressure: "MaxPressure", random: "Random" };
  const ROADNET = (sc) => `/data/danang/replay_roadnet_${sc}.json`;
  const REPLAY = (sc, c) => `/results/${sc}/demo/replay_${c}_demo.txt`;
  const COMPARISON = (sc) => `/results/${sc}/comparison.json`;
  const CAR_COLORS = [[242, 191, 215], [183, 235, 228], [219, 235, 183],
                      [245, 221, 181], [212, 181, 245]];
  const DT = 10; // seconds of sim time per replay frame (action interval)

  const S = {
    scenario: DEFAULT_SCENARIO,
    ctrls: { left: "fixed_time", right: "dqn" },
    roadnet: null, comparison: null,
    steps: { left: [], right: [] },
    T: 0, playing: false, timer: null, gen: 0,
  };
  const decks = {};
  let viewState = null, fitState = null;

  const $ = (id) => document.getElementById(id);
  function fetchText(u) {
    return fetch(u).then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status + " " + u);
      return r.text();
    });
  }
  function ctrlLabel(key) {
    for (const [k, label] of CTRLS) if (k === key) return label;
    return key;
  }

  // ---------- layers ----------
  function roadLayer(roadnet) {
    return new deck.PathLayer({
      id: "roads",
      data: roadnet.roads,
      getPath: (r) => r.points.map((p) => [p.x, p.y]),
      getWidth: (r) => r.nLanes * 3,
      widthUnits: "meters",
      widthMinPixels: 1,
      jointRounded: true,
      capRounded: true,
      getColor: [138, 160, 173],
    });
  }

  function carLayer(side, cars) {
    return new deck.SolidPolygonLayer({
      id: "cars-" + side,
      data: cars,
      extruded: true,
      getElevation: 1.6,
      getPolygon: (c) => R3.carFootprint(c.x, c.y, c.a, c.len, c.wid),
      getFillColor: (c, info) => CAR_COLORS[info.index % CAR_COLORS.length],
    });
  }

  function signalLayer(side, roadnet, tl) {
    const bars = [];
    for (const road of roadnet.roads) {
      const st = tl[road.id];
      if (!st) continue;
      const bs = R3.laneBars(road.points, road.nLanes, st, {});
      for (const b of bs) bars.push(b);
    }
    return new deck.SolidPolygonLayer({
      id: "signals-" + side,
      data: bars,
      extruded: true,
      getElevation: 2.5,
      getPolygon: (b) => b.polygon,
      getFillColor: (b) => (b.status === "g" ? [46, 204, 64] : [255, 65, 54]),
    });
  }

  // ---------- rendering ----------
  function render(side) {
    if (!S.roadnet) return;
    const step = S.steps[side][S.T];
    const layers = [roadLayer(S.roadnet)];
    if (step) {
      layers.push(carLayer(side, step.cars));
      layers.push(signalLayer(side, S.roadnet, step.tl));
    }
    decks[side].setProps({ layers });
  }
  function renderBoth() {
    render("left");
    render("right");
    $("clock").textContent = "t = " + S.T * DT + "s";
    $("scrub").value = String(S.T);
  }

  function renderScoreboard() {
    if (!S.comparison) return;
    const sb = RAB.scoreboard(S.comparison,
      CTRL_TO_ROW[S.ctrls.left], CTRL_TO_ROW[S.ctrls.right]);
    const cell = (e, name) => e
      ? '<div class="score"><b>' + name + "</b>" +
        "<span>" + e.vehH.toFixed(1) + " xe·giờ chờ (cả kịch bản)</span>" +
        "<span>" + (e.pctVsFixed >= 0 ? "▼ giảm " : "▲ tăng ") +
        Math.abs(e.pctVsFixed).toFixed(1) + "% so với Cố định</span></div>"
      : '<div class="score">—</div>';
    $("scoreboard").innerHTML =
      cell(sb.left, ctrlLabel(S.ctrls.left)) + cell(sb.right, ctrlLabel(S.ctrls.right));
  }

  // ---------- camera ----------
  function applyViewState(vs) {
    viewState = vs;
    window.__viewState = vs; // test hook
    decks.left.setProps({ viewState: vs });
    decks.right.setProps({ viewState: vs });
  }
  function refit() {
    const el = $("deck-left");
    fitState = R3.fitView(S.roadnet.bounds, el.clientWidth, el.clientHeight);
    applyViewState(Object.assign({}, fitState));
  }
  function makeDeck(el) {
    return new deck.Deck({
      parent: el,
      views: new deck.OrbitView({ orbitAxis: "Z" }),
      controller: true,
      viewState: { target: [0, 0, 0], zoom: 0, rotationX: 45, rotationOrbit: 0 },
      onViewStateChange: (e) => applyViewState(e.viewState),
      layers: [],
    });
  }

  // ---------- playback ----------
  function setPlaying(on) {
    S.playing = on;
    $("play").textContent = on ? "❚❚ Dừng" : "▶︎ Chạy";
    if (S.timer) { clearInterval(S.timer); S.timer = null; }
    if (on) {
      S.timer = setInterval(() => {
        const n = S.steps.left.length || 1;
        S.T = (S.T + 1) % n;
        renderBoth();
      }, parseInt($("speed").value, 10));
    }
  }

  // ---------- data loading (monotonic generation guards stale responses) ----------
  function loadAll(resetCamera) {
    const gen = ++S.gen;
    const sc = S.scenario;
    return Promise.all([
      fetchText(ROADNET(sc)),
      fetchText(REPLAY(sc, S.ctrls.left)),
      fetchText(REPLAY(sc, S.ctrls.right)),
      fetchText(COMPARISON(sc)),
    ]).then(([rnTxt, leftTxt, rightTxt, cmpTxt]) => {
      if (gen !== S.gen) return; // a newer request superseded this one
      S.roadnet = RAB.parseRoadnet(JSON.parse(rnTxt));
      S.steps.left = RAB.parseReplay(leftTxt);
      S.steps.right = RAB.parseReplay(rightTxt);
      S.comparison = JSON.parse(cmpTxt);
      const n = Math.min(S.steps.left.length, S.steps.right.length);
      $("scrub").max = String(Math.max(0, n - 1));
      if (S.T >= n) S.T = 0;
      if (resetCamera || !viewState) refit();
      renderBoth();
      renderScoreboard();
    }).catch((err) => {
      if (gen !== S.gen) return;
      const el = document.createElement("p");
      el.className = "err";
      el.textContent = "Lỗi tải dữ liệu: " + err.message;
      document.body.appendChild(el);
    });
  }

  // ---------- wiring ----------
  function fillSelect(el, pairs, value) {
    el.innerHTML = "";
    for (const [k, label] of pairs) {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = label;
      el.appendChild(o);
    }
    el.value = value;
  }

  function init() {
    decks.left = makeDeck($("deck-left"));
    decks.right = makeDeck($("deck-right"));
    fillSelect($("scenario"), SCENARIOS, S.scenario);
    fillSelect($("ctrl-left"), CTRLS, S.ctrls.left);
    fillSelect($("ctrl-right"), CTRLS, S.ctrls.right);
    $("scenario").addEventListener("change", (e) => {
      S.scenario = e.target.value;
      loadAll(true); // new bounds (networks differ) -> refit camera
    });
    $("ctrl-left").addEventListener("change", (e) => {
      S.ctrls.left = e.target.value;
      $("left-title").textContent = ctrlLabel(S.ctrls.left);
      loadAll(false);
    });
    $("ctrl-right").addEventListener("change", (e) => {
      S.ctrls.right = e.target.value;
      $("right-title").textContent = ctrlLabel(S.ctrls.right);
      loadAll(false);
    });
    $("play").addEventListener("click", () => setPlaying(!S.playing));
    $("speed").addEventListener("change", () => { if (S.playing) setPlaying(true); });
    $("scrub").addEventListener("input", (e) => {
      S.T = parseInt(e.target.value, 10) || 0;
      renderBoth();
    });
    $("reset-cam").addEventListener("click", () => {
      if (fitState) applyViewState(Object.assign({}, fitState));
    });
    window.__replay3d = { state: S, applyViewState }; // test hook
    window.__decksReady = loadAll(true);
  }

  init();
})();
```

- [ ] **Step 2: Node regression** (layers are browser-only; the pure pieces are already covered)

Run: `node --test tests/replay_3d/*.test.cjs tests/replay_ab/*.test.cjs`
Expected: all PASS.

- [ ] **Step 3: Browser verify (Playwright)** — with the server from Task 2 running:
  - Load page; `await window.__decksReady`; screenshot: roads + colored signal bars + vehicles visible in both panels.
  - Click `#play`, wait ~1s, confirm `window.__replay3d.state.T > 0` and clock text changed; screenshot differs.
  - Drag scrub to 60: both panels re-render (state.T === 60).
  - Switch right panel to Max-Pressure: scoreboard updates; no console errors; rapid double-switch scenario→controller shows no stale overwrite (state.gen increments; final render matches last selection).
  - Zoom in near an intersection: per-lane bars distinguishable (screenshot for the report).

- [ ] **Step 4: Commit**

```bash
git add frontend/replay_3d.js
git commit -m "feat(3d): playback + vehicles + per-lane signal bars + A/B controls + scoreboard"
```

---

### Task 4: Docs, cross-link from 2D page, full-suite smoke

**Files:**
- Create: `docs/demo_replay_3d.md`
- Modify: `frontend/replay_ab.html` (add a link to the 3D page in the header note; do not touch anything else)
- Modify: `docs/demo_replay_ab.md` (one line pointing to the 3D variant)

**Interfaces:**
- Consumes: everything shipped in Tasks 1–3.
- Produces: operator documentation; no code interfaces.

- [ ] **Step 1: `docs/demo_replay_3d.md`** (complete file; replace `<VERSION>` with the deck.gl version actually vendored in Task 2 — read the banner at the top of `frontend/vendor/deck.min.js`):

```markdown
# Demo 3D A/B: Fixed-Time vs DQN (deck.gl)

Trang: `frontend/replay_3d.html` — chạy cùng server với bản 2D:

    python3 scripts/serve_replay.py --no-browser
    # mở http://localhost:8080/frontend/replay_3d.html

## Trang này là gì

- Hai khung 3D **khoá cùng camera và cùng thời điểm**: trái mặc định Cố định
  (Fixed-Time), phải mặc định DQN; đổi được từng bên (Max-Pressure, Ngẫu nhiên).
- **Replay CityFlow thật** (120 khung × 10 s) trên mạng Hải Châu 53 nút đèn —
  không phải suy luận trực tiếp (live inference). Số liệu bảng điểm đọc từ
  `results/<kịch bản>/comparison.json` (số thật của Chương 4).
- **Đèn theo từng làn:** thanh đứng màu xanh/đỏ tại vạch dừng của mỗi làn
  (ký tự `g/r/i` per-lane trong replay; `i` = làn không có đèn — không vẽ).
  Đây là điểm bản 2D không thể hiện được (bản 2D gộp mỗi đường 1 chấm).
  Lưu ý trung thực: thứ tự thanh trong một đường theo thứ tự làn trong replay;
  danh tính trái/phải tuyệt đối của làn chưa đối chiếu với viewer gốc —
  thông điệp demo là "nhánh nào xanh", không phải "làn số mấy".
- Xe = hộp 3D dựng từ (x, y, góc, dài, rộng) trong replay.

## Điều khiển

Kéo chuột: xoay camera · Shift+kéo / chuột phải: trượt · lăn chuột: thu-phóng ·
"Đặt lại camera": về khung nhìn toàn mạng. Play/tua/tốc độ như bản 2D.
Đổi kịch bản giữa chừng được (haichau_rush → danang_peak → haichau_peak →
haichau) — câu chuyện bão hoà giữ nguyên như bản 2D.

## Kỹ thuật

- deck.gl <VERSION> vendor tại `frontend/vendor/deck.min.js` (offline hoàn toàn).
- Hình học thuần (footprint xe xoay, quad thanh đèn theo làn, fitView) ở
  `frontend/replay_3d_core.js`, test Node: `node --test tests/replay_3d/*.test.cjs`.
- Tiền lệ tài liệu: DTUMOS (deck.gl, digital twin đô thị, 2023); MARLens
  (IEEE TVCG 2024 — visual analytics cho RL điều khiển đèn); sumo3Dviz
  (arXiv:2604.19194 — 3D nhẹ cho SUMO, chỉ xuất video). Xem spec
  `docs/superpowers/specs/2026-07-19-replay-3d-demo-design.md`.
```

- [ ] **Step 2: Cross-link 2D → 3D.** In `frontend/replay_ab.html`, find the header note paragraph (the one carrying the honest-framing text) and append ` · <a href="replay_3d.html">Xem bản 3D</a>` inside the `<p>`. In `docs/demo_replay_ab.md`, add one line near the top: `Bản 3D (deck.gl, đèn theo từng làn): xem docs/demo_replay_3d.md.`

- [ ] **Step 3: Full-suite smoke**

Run and record output:
```bash
python3 -m pytest -q
node --test tests/replay_ab/*.test.cjs tests/replay_3d/*.test.cjs
```
Expected: pytest 82 passed / 1 deselected (unchanged); all Node tests pass.
Playwright: reload BOTH pages (`replay_ab.html`, `replay_3d.html`) — no console errors, cross-links work in both directions.

- [ ] **Step 4: Commit**

```bash
git add docs/demo_replay_3d.md docs/demo_replay_ab.md frontend/replay_ab.html
git commit -m "docs(3d): operator guide + 2D/3D cross-links"
```
