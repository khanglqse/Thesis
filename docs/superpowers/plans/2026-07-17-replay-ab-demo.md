# A/B CityFlow Replay Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A single browser page showing the REAL trained DQN vs a baseline on the real 53-intersection Hải Châu network, side-by-side and frame-synchronized, replaying actual CityFlow runs — with per-intersection traffic-light phase highlighting, play/pause/scrub/speed, zoom-to-cluster, and a scoreboard of the real Chapter-4 waiting-time numbers (DQN −30.8% vs Fixed).

**Why (pivot):** the live in-browser DQN "sandbox" (prior plan) does NOT honestly showcase the DQN — the trained policy is tied to CityFlow's dynamics and does not transfer to a toy single-intersection model (verified: worse than Fixed by 60–140% at realistic asymmetric demand on the toy). This demo instead shows the DQN's REAL behavior on the REAL network from pre-computed CityFlow replays — honest and favorable. "Live" here = an interactive replay player (play/pause/scrub/speed/toggle/zoom), the reading the user accepted in brainstorming.

**Architecture:** Pure browser JS + HTML5 Canvas 2D, no build step, no Docker/container. A pure-logic module `frontend/replay_ab_core.js` (parse roadnet + replay `.txt`, world→screen transform, scoreboard math) is Node-unit-tested. `frontend/replay_ab.js` renders two synchronized top-down panels. Served by the existing `scripts/serve_replay.py`. All data already exists in the repo.

**Tech Stack:** Vanilla JS, Canvas 2D, Node `node --test`, Python (serve).

## Global Constraints
- **No Docker/CityFlow at demo time.** All inputs are pre-generated files already in the repo:
  - Replays: `results/haichau_rush/demo/replay_{dqn,fixed_time,max_pressure,random}_demo.txt` — **120 steps** each; each line = `carLogs;tlLogs`.
    - car = `x y angle id laneChange len wid` (space-separated); cars comma-separated.
    - tl = `roadId s0 s1 …` per lane-link status: `g`=green, `r`=red, `i`=off/uncontrolled; tls comma-separated.
  - Roadnet: `data/danang/replay_roadnet_haichau_rush.json` — CityFlow **replay-viewer static format**: `{static:{nodes:[{id, point:[x,y], virtual}], edges:[{id, from, to, points:[[x,y],…], nLane}]}}`. Edge `id`s match the tlLogs road ids (verified 1065/1066). (This is NOT the training-roadnet schema; `frontend/script.js` reads exactly this via `simulation.static.nodes/edges`.)
  - Metrics: `results/haichau_rush/comparison.json` — `table[{controller, queue_series:[…100 pts]}]`; controllers `DQN`, `FixedTime`, `MaxPressure`, `Random`.
- **Real numbers only** (from `comparison.json`, matching Chapter 4): DQN −30.8%, MaxPressure −40.1%, Random +9.5% waiting-time vs Fixed. veh-hours = `sum(queue * 10) / 3600`.
- **Honesty note on-screen (Vietnamese):** real CityFlow replay of the real network; numbers are the Chapter-4 results.
- **Node v25.2.1 quirk:** run tests as `node --test tests/replay_ab/*.test.cjs` (bare-dir arg is broken).
- Default A/B pairing: **left = Fixed-Time, right = DQN**; each panel has a `<select>` to switch among the 4 controllers.
- UI copy in Vietnamese (match `frontend/demo-presets.js`).

## File Structure
| File | New/changed | Responsibility |
|---|---|---|
| `frontend/replay_ab_core.js` | new (UMD dual CJS/global) | `parseRoadnet`, `parseReplay`, `roadSignal`, `makeTransform`, `waitHours`, `scoreboard` |
| `tests/replay_ab/core.test.cjs` | new (node --test) | parse real fixtures + transform + scoreboard math |
| `frontend/replay_ab.html` | new | page markup (two canvases + controls + scoreboard + note) |
| `frontend/replay_ab.css` | new | projector-legible styling |
| `frontend/replay_ab.js` | new | dual-panel render + sync loop + controls + zoom + scoreboard wiring |
| `scripts/serve_replay.py` | changed | also print the A/B demo URL |
| `docs/demo_replay_ab.md` | new | operator guide |

---

## Task 1: Core module — parse roadnet + replay, transform, scoreboard

**Files:** Create `frontend/replay_ab_core.js`; Test `tests/replay_ab/core.test.cjs`.

**Interfaces (produced; exact names):**
- `parseRoadnet(data) -> {roads:[{id,points,nLanes,start,end}], inters:[{id,x,y}], bounds:{minX,minY,maxX,maxY}}`
- `parseReplay(text) -> [{cars:[{x,y,a,len,wid}], tl:{roadId:[statusChar]}}]`
- `roadSignal(statuses) -> 'green'|'red'|null`
- `makeTransform(bounds, W, H, pad) -> {scale, sx(x), sy(y)}`
- `waitHours(queue_series, dt=10) -> number`
- `scoreboard(comparison, leftKey, rightKey) -> {left:{key,vehH,pctVsFixed}|null, right:…, fixedVehH}`

- [ ] **Step 1: Write the failing test** — `tests/replay_ab/core.test.cjs`

```js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const R = require("../../frontend/replay_ab_core.js");

const ROOT = path.join(__dirname, "../..");
const roadnet = JSON.parse(fs.readFileSync(path.join(ROOT, "data/danang/replay_roadnet_haichau_rush.json"), "utf8"));
const replayTxt = fs.readFileSync(path.join(ROOT, "results/haichau_rush/demo/replay_dqn_demo.txt"), "utf8");
const comparison = JSON.parse(fs.readFileSync(path.join(ROOT, "results/haichau_rush/comparison.json"), "utf8"));

test("parseRoadnet returns roads/inters/bounds", () => {
  const rn = R.parseRoadnet(roadnet);
  assert.ok(rn.roads.length > 100);
  assert.ok(rn.inters.length >= 1);
  assert.ok(rn.bounds.maxX > rn.bounds.minX && rn.bounds.maxY > rn.bounds.minY);
  const r0 = rn.roads.find((r) => r.points && r.points.length >= 2);
  assert.ok(r0 && typeof r0.nLanes === "number" && r0.end);
});

test("parseReplay yields 120 steps with cars + tl", () => {
  const steps = R.parseReplay(replayTxt);
  assert.strictEqual(steps.length, 120);
  const s = steps[0];
  assert.ok(s.cars.length > 0 && typeof s.cars[0].x === "number");
  assert.ok(Object.keys(s.tl).length > 0);
});

test("roadSignal classifies green/red/off", () => {
  assert.strictEqual(R.roadSignal(["i", "g", "i"]), "green");
  assert.strictEqual(R.roadSignal(["r", "i"]), "red");
  assert.strictEqual(R.roadSignal(["i", "i"]), null);
  assert.strictEqual(R.roadSignal(undefined), null);
});

test("makeTransform maps bounds inside canvas, y flipped", () => {
  const t = R.makeTransform({ minX: 0, minY: 0, maxX: 100, maxY: 50 }, 200, 200, 10);
  assert.ok(t.sx(0) >= 10 - 1e-9 && t.sx(100) <= 190 + 1e-9);
  assert.ok(t.sy(0) > t.sy(50)); // world y up => larger world y is higher on screen (smaller sy)
});

test("scoreboard returns real veh-h and pct vs Fixed", () => {
  const sb = R.scoreboard(comparison, "FixedTime", "DQN");
  assert.ok(sb.right.key === "DQN" && sb.right.vehH > 0);
  assert.ok(Math.abs(sb.right.pctVsFixed - 30.8) < 1.0); // DQN -30.8% vs Fixed
  assert.ok(Math.abs(sb.left.pctVsFixed) < 1e-6);        // Fixed vs itself = 0
});
```

- [ ] **Step 2: Run — expect FAIL** — `node --test tests/replay_ab/core.test.cjs` → cannot find module.

- [ ] **Step 3: Implement** — `frontend/replay_ab_core.js`

```js
// Pure logic for the A/B replay demo. Loads in browser (window.ReplayAB) and Node (module.exports).
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReplayAB = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function parseRoadnet(data) {
    // CityFlow replay-viewer static format: {static:{nodes, edges}}.
    // Normalize point [x,y] arrays -> {x,y} so the renderer code stays uniform.
    const st = data.static || data;
    const roads = (st.edges || []).map((e) => ({
      id: e.id,
      points: (e.points || []).map((p) => (Array.isArray(p) ? { x: p[0], y: p[1] } : p)),
      nLanes: e.nLane || (e.lanes ? e.lanes.length : 1),
      start: e.from, end: e.to,
    }));
    const inters = (st.nodes || [])
      .filter((n) => !n.virtual && n.point)
      .map((n) => ({
        id: n.id,
        x: Array.isArray(n.point) ? n.point[0] : n.point.x,
        y: Array.isArray(n.point) ? n.point[1] : n.point.y,
      }));
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const r of roads) for (const p of r.points) {
      if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
    }
    return { roads, inters, bounds: { minX, minY, maxX, maxY } };
  }

  function parseReplay(text) {
    const out = [];
    const lines = text.split("\n");
    for (const line of lines) {
      if (!line) continue;
      const semi = line.indexOf(";");
      const carPart = semi >= 0 ? line.slice(0, semi) : line;
      const tlPart = semi >= 0 ? line.slice(semi + 1) : "";
      const cars = [];
      if (carPart) for (const c of carPart.split(",")) {
        if (!c) continue;
        const f = c.split(" ");
        if (f.length < 3) continue;
        cars.push({ x: +f[0], y: +f[1], a: +f[2], len: +(f[5] || 4), wid: +(f[6] || 2) });
      }
      const tl = {};
      if (tlPart) for (const t of tlPart.split(",")) {
        if (!t) continue;
        const f = t.split(" ");
        tl[f[0]] = f.slice(1);
      }
      out.push({ cars, tl });
    }
    return out;
  }

  function roadSignal(statuses) {
    if (!statuses) return null;
    let hasG = false, hasR = false;
    for (const s of statuses) { if (s === "g") hasG = true; else if (s === "r") hasR = true; }
    return hasG ? "green" : (hasR ? "red" : null);
  }

  function makeTransform(bounds, W, H, pad) {
    pad = pad || 20;
    const bw = (bounds.maxX - bounds.minX) || 1, bh = (bounds.maxY - bounds.minY) || 1;
    const s = Math.min((W - 2 * pad) / bw, (H - 2 * pad) / bh);
    return {
      scale: s,
      sx: (x) => pad + (x - bounds.minX) * s,
      sy: (y) => H - (pad + (y - bounds.minY) * s),
    };
  }

  function waitHours(queue_series, dt) {
    dt = dt || 10;
    let s = 0; for (const q of queue_series) s += q * dt / 3600.0; return s;
  }

  function scoreboard(comparison, leftKey, rightKey) {
    const by = {}; for (const r of (comparison.table || [])) by[r.controller] = r;
    const fixed = by["FixedTime"];
    const fw = fixed && fixed.queue_series ? waitHours(fixed.queue_series) : 0;
    const entry = (k) => {
      const r = by[k];
      if (!r || !r.queue_series) return null;
      const w = waitHours(r.queue_series);
      return { key: k, vehH: w, pctVsFixed: fw ? 100 * (fw - w) / fw : 0 };
    };
    return { left: entry(leftKey), right: entry(rightKey), fixedVehH: fw };
  }

  return { parseRoadnet, parseReplay, roadSignal, makeTransform, waitHours, scoreboard };
});
```

- [ ] **Step 4: Run — expect PASS** — `node --test tests/replay_ab/core.test.cjs` (5 tests).
- [ ] **Step 5: Commit** — `git add frontend/replay_ab_core.js tests/replay_ab/core.test.cjs && git commit -m "feat(replay-ab): core parser + transform + scoreboard"`

---

## Task 2: Single-panel renderer (roads + cars + phase highlight)

**Files:** Create `frontend/replay_ab.html`, `frontend/replay_ab.css`, `frontend/replay_ab.js`.

**Interfaces (produced):** `window.ReplayABApp` with `drawPanel(ctx, view, roadnet, step, transform, opts)` and a `loadAll()` bootstrap. Exposes `window.__replayAB` state for Task 3.

- [ ] **Step 1: Markup** — `frontend/replay_ab.html`
```html
<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8" />
<title>DQN vs Baseline — Replay CityFlow (Hải Châu)</title>
<link rel="stylesheet" href="replay_ab.css" /></head>
<body>
  <header>
    <h1>RL (DQN) điều khiển đèn — so sánh trực tiếp trên mạng thật (Hải Châu, 53 nút)</h1>
    <p class="note">Replay CityFlow THẬT của các controller trên cùng kịch bản/seed (haichau_rush).
      Số liệu là kết quả Chương 4.</p>
  </header>
  <div id="panels">
    <figure><figcaption><select id="ctrl-left"></select> <span class="side-tag">TRÁI</span></figcaption>
      <canvas id="canvas-left" width="560" height="560"></canvas></figure>
    <figure><figcaption><select id="ctrl-right"></select> <span class="side-tag">PHẢI</span></figcaption>
      <canvas id="canvas-right" width="560" height="560"></canvas></figure>
  </div>
  <div id="controls"></div>
  <div id="scoreboard"></div>
  <script src="replay_ab_core.js"></script>
  <script src="replay_ab.js"></script>
</body></html>
```

- [ ] **Step 2: Styling** — `frontend/replay_ab.css`
```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, Arial, sans-serif; background: #0f1720; color: #e8ebed; }
header { padding: 10px 18px; } header h1 { font-size: 18px; margin: 0 0 4px; }
.note { font-size: 12px; color: #9fb2bf; margin: 0; }
#panels { display: flex; gap: 12px; padding: 0 18px; flex-wrap: wrap; }
figure { margin: 0; } figcaption { font-size: 14px; padding: 4px 0; }
canvas { background: #e8ebed; border-radius: 8px; width: 100%; max-width: 560px; height: auto; }
.side-tag { color: #9fb2bf; font-size: 11px; }
#controls, #scoreboard { padding: 10px 18px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
#scoreboard { font-size: 14px; }
.sb-win { color: #85ee00; font-weight: 700; }
button, select, input { font-size: 14px; }
```

- [ ] **Step 3: Renderer** — `frontend/replay_ab.js` (render core; controls come in Task 3)
```js
(function () {
  "use strict";
  const R = window.ReplayAB;
  const ROOT = ""; // served from repo root; paths are absolute from site root
  const REPLAY = (ctrl) => `/results/haichau_rush/demo/replay_${ctrl}_demo.txt`;
  const ROADNET_URL = "/data/danang/replay_roadnet_haichau_rush.json";
  const COMPARISON_URL = "/results/haichau_rush/comparison.json";
  const CTRLS = [["fixed_time", "Cố định (Fixed-Time)"], ["dqn", "RL (DQN)"],
                 ["max_pressure", "Max-Pressure"], ["random", "Ngẫu nhiên"]];
  const CTRL_TO_ROW = { dqn: "DQN", fixed_time: "FixedTime", max_pressure: "MaxPressure", random: "Random" };

  const CAR_COLORS = ["#f2bfd7", "#b7ebe4", "#dbebb7", "#f5ddb5", "#d4b5f5"];

  function fetchText(u) { return fetch(u).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status + " " + u); return r.text(); }); }

  function drawRoads(ctx, roadnet, T) {
    ctx.strokeStyle = "#8aa0ad"; ctx.lineJoin = "round";
    for (const road of roadnet.roads) {
      if (road.points.length < 2) continue;
      ctx.lineWidth = Math.max(1.5, road.nLanes * 1.4 * (T.scale > 0.02 ? 1 : 1));
      ctx.beginPath();
      ctx.moveTo(T.sx(road.points[0].x), T.sy(road.points[0].y));
      for (let k = 1; k < road.points.length; k++) ctx.lineTo(T.sx(road.points[k].x), T.sy(road.points[k].y));
      ctx.stroke();
    }
  }

  function drawSignals(ctx, roadnet, tl, T) {
    for (const road of roadnet.roads) {
      const sig = R.roadSignal(tl[road.id]);
      if (!sig || road.points.length < 1) continue;               // only controlled approaches
      const p = road.points[road.points.length - 1];              // near the end intersection
      ctx.fillStyle = sig === "green" ? "#85ee00" : "#db635e";
      const r = Math.max(2.5, 4);
      ctx.beginPath(); ctx.arc(T.sx(p.x), T.sy(p.y), r, 0, Math.PI * 2); ctx.fill();
    }
  }

  function drawCars(ctx, cars, T) {
    for (let i = 0; i < cars.length; i++) {
      const c = cars[i];
      ctx.fillStyle = CAR_COLORS[i % CAR_COLORS.length];
      const s = Math.max(1.6, 2.2);
      ctx.fillRect(T.sx(c.x) - s / 2, T.sy(c.y) - s / 2, s, s);
    }
  }

  function drawPanel(ctx, roadnet, stepData, T) {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.fillStyle = "#e8ebed"; ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    drawRoads(ctx, roadnet, T);
    if (stepData) { drawCars(ctx, stepData.cars, T); drawSignals(ctx, roadnet, stepData.tl, T); }
  }

  function loadAll() {
    return Promise.all([fetchText(ROADNET_URL), fetchText(REPLAY("fixed_time")),
                        fetchText(REPLAY("dqn")), fetchText(COMPARISON_URL)])
      .then(([rnTxt, leftTxt, rightTxt, cmpTxt]) => {
        const roadnet = R.parseRoadnet(JSON.parse(rnTxt));
        const W = document.getElementById("canvas-left").width;
        const H = document.getElementById("canvas-left").height;
        const T = R.makeTransform(roadnet.bounds, W, H, 16);
        const state = {
          roadnet, T, comparison: JSON.parse(cmpTxt),
          panels: { left: { ctrl: "fixed_time", steps: R.parseReplay(leftTxt) },
                    right: { ctrl: "dqn", steps: R.parseReplay(rightTxt) } },
          step: 0, playing: false, speed: 4, fetchText, REPLAY, CTRL_TO_ROW, CTRLS, drawPanel,
        };
        window.__replayAB = state;
        // initial static frame
        drawPanel(document.getElementById("canvas-left").getContext("2d"), roadnet, state.panels.left.steps[0], T);
        drawPanel(document.getElementById("canvas-right").getContext("2d"), roadnet, state.panels.right.steps[0], T);
        return state;
      });
  }

  window.ReplayABApp = { drawPanel, loadAll };
  loadAll().catch((e) => { console.error("replay_ab load failed:", e); });
})();
```

- [ ] **Step 4: Verify (Playwright/headless)** — serve `python scripts/serve_replay.py --no-browser`, open `http://localhost:8080/frontend/replay_ab.html`. Confirm both canvases draw the road network + cars + green/red signal dots at intersections; console error-free. (Playwright MCP may be profile-locked → self-host Playwright/headless Chrome as prior work did.) Screenshot in report.
- [ ] **Step 5: Commit** — `git add frontend/replay_ab.html frontend/replay_ab.css frontend/replay_ab.js && git commit -m "feat(replay-ab): dual-canvas static render (roads+cars+signals)"`

---

## Task 3: Sync loop + controls + scoreboard + zoom

**Files:** Modify `frontend/replay_ab.js` (add the control/loop layer; do not disturb the Task-2 render functions).

**Interfaces (consumed):** `window.__replayAB` (state, with `drawPanel, fetchText, REPLAY, CTRLS, CTRL_TO_ROW` on it), `ReplayAB.scoreboard`, `ReplayAB.makeTransform`, `ReplayAB.parseReplay`. **Task-2's real `drawPanel` signature is `drawPanel(ctx, roadnet, stepData, T)`** (pre-resolved step data, NOT a raw step index) — use exactly this.

- [ ] **Step 1: Add controls + loop** — APPEND to `frontend/replay_ab.js` (after the Task-2 IIFE closes; this is a new top-level block that reads the globals Task 2 exposed). Verbatim:

```js
(function () {
  "use strict";
  const R = window.ReplayAB;

  function makeClusterTransform(roadnet, W, H) {
    // bbox of the 8 intersections nearest the network centroid (zoom target)
    const inters = roadnet.inters;
    if (!inters.length) return R.makeTransform(roadnet.bounds, W, H, 8);
    let cx = 0, cy = 0; for (const n of inters) { cx += n.x; cy += n.y; } cx /= inters.length; cy /= inters.length;
    const near = inters.slice().sort((a, b) =>
      ((a.x - cx) ** 2 + (a.y - cy) ** 2) - ((b.x - cx) ** 2 + (b.y - cy) ** 2)).slice(0, 8);
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of near) { if (n.x < minX) minX = n.x; if (n.x > maxX) maxX = n.x; if (n.y < minY) minY = n.y; if (n.y > maxY) maxY = n.y; }
    const px = (maxX - minX) * 0.15 || 50, py = (maxY - minY) * 0.15 || 50;
    return R.makeTransform({ minX: minX - px, minY: minY - py, maxX: maxX + px, maxY: maxY + py }, W, H, 8);
  }

  function runUI(state) {
    const roadnet = state.roadnet, comparison = state.comparison;
    const cvL = document.getElementById("canvas-left"), cvR = document.getElementById("canvas-right");
    const ctxL = cvL.getContext("2d"), ctxR = cvR.getContext("2d");
    const nSteps = Math.min(state.panels.left.steps.length, state.panels.right.steps.length);
    const fullT = state.T, clusterT = makeClusterTransform(roadnet, cvL.width, cvL.height);
    state.zoom = false;
    const curT = () => (state.zoom ? clusterT : fullT);

    const selL = document.getElementById("ctrl-left"), selR = document.getElementById("ctrl-right");
    const fill = (sel, cur) => { sel.innerHTML = state.CTRLS.map(([v, t]) => '<option value="' + v + '"' + (v === cur ? " selected" : "") + '>' + t + "</option>").join(""); };
    fill(selL, state.panels.left.ctrl); fill(selR, state.panels.right.ctrl);
    const onSelect = (side, sel) => { sel.onchange = () => {
      state.panels[side].ctrl = sel.value;
      state.fetchText(state.REPLAY(sel.value)).then((txt) => {
        state.panels[side].steps = R.parseReplay(txt);
        state.step = Math.min(state.step, state.panels[side].steps.length - 1);
        redraw(); updateScore();
      }).catch((e) => console.error("switch controller failed:", e));
    }; };
    onSelect("left", selL); onSelect("right", selR);

    document.getElementById("controls").innerHTML =
      '<button id="play">▶ Chạy</button>' +
      '<label>Bước: <input id="scrub" type="range" min="0" max="' + (nSteps - 1) + '" value="0"></label>' +
      '<span id="steplabel">0 / ' + (nSteps - 1) + '</span>' +
      '<label>Tốc độ: <input id="speed" type="range" min="1" max="30" value="6"></label>' +
      '<button id="zoom">🔍 Zoom cụm nút</button>';
    const playBtn = document.getElementById("play"), scrub = document.getElementById("scrub"),
      speed = document.getElementById("speed"), stepLabel = document.getElementById("steplabel"),
      zoomBtn = document.getElementById("zoom");
    playBtn.onclick = () => { state.playing = !state.playing; playBtn.textContent = state.playing ? "⏸ Dừng" : "▶ Chạy"; };
    scrub.oninput = () => { state.step = +scrub.value; redraw(); };
    speed.oninput = () => { state.speed = +speed.value; };
    zoomBtn.onclick = () => { state.zoom = !state.zoom; zoomBtn.classList.toggle("on", state.zoom); redraw(); };

    function redraw() {
      const t = curT();
      state.drawPanel(ctxL, roadnet, state.panels.left.steps[state.step], t);
      state.drawPanel(ctxR, roadnet, state.panels.right.steps[state.step], t);
      scrub.value = state.step; stepLabel.textContent = state.step + " / " + (nSteps - 1);
    }
    function updateScore() {
      const sb = R.scoreboard(comparison, state.CTRL_TO_ROW[state.panels.left.ctrl], state.CTRL_TO_ROW[state.panels.right.ctrl]);
      const fmt = (e) => e ? (e.key + ": " + e.vehH.toFixed(0) + " veh-h (" + (e.pctVsFixed >= 0 ? "▼ " : "▲ ") + Math.abs(e.pctVsFixed).toFixed(1) + "% vs Fixed)") : "—";
      const rightWins = sb.right && sb.right.pctVsFixed > 0;
      document.getElementById("scoreboard").innerHTML =
        "<div><b>Thời gian chờ tích luỹ cả episode (số thật Chương 4):</b></div>" +
        "<div>TRÁI — " + fmt(sb.left) + "</div>" +
        '<div class="' + (rightWins ? "sb-win" : "") + '">PHẢI — ' + fmt(sb.right) + "</div>" +
        '<div class="note">Cùng kịch bản/seed; veh-h thấp hơn = tốt hơn.</div>';
    }

    let acc = 0, last = null;
    function loop(ts) {
      if (last == null) last = ts;
      const dtSec = Math.min(0.1, (ts - last) / 1000); last = ts;
      if (state.playing) { acc += dtSec * state.speed; while (acc >= 1) { acc -= 1; state.step = (state.step + 1) % nSteps; } redraw(); }
      requestAnimationFrame(loop);
    }
    redraw(); updateScore(); requestAnimationFrame(loop);
  }

  // Task 2's loadAll() sets window.__replayAB asynchronously; wait for it, then wire the UI.
  const boot = setInterval(() => {
    if (window.__replayAB && window.__replayAB.panels) { clearInterval(boot); runUI(window.__replayAB); }
  }, 30);
})();
```
- [ ] **Step 2: Verify (Playwright/headless)** — both panels play in lockstep (same step index); scrubbing moves both; the DQN panel visibly clears queues faster and its signal-phase pattern differs from Fixed at the same moment; zoom makes signals legible; scoreboard reads DQN ≈ **−30.8%** vs Fixed; switching a panel's controller updates its replay + the scoreboard; console clean. Screenshot(s) in report.
- [ ] **Step 3: Regression** — `node --test tests/replay_ab/*.test.cjs` still passes (core untouched).
- [ ] **Step 4: Commit** — `git add frontend/replay_ab.js && git commit -m "feat(replay-ab): sync loop, controls, zoom, scoreboard"`

---

## Task 4: Serve URL + operator doc + regression

**Files:** Modify `scripts/serve_replay.py`; Create `docs/demo_replay_ab.md`.

- [ ] **Step 1** — in `scripts/serve_replay.py`, after the existing sandbox URL print, add:
```python
    print("A/B replay (DQN vs baseline, real network): "
          "http://localhost:{}/frontend/replay_ab.html".format(args.port))
```
- [ ] **Step 2** — `docs/demo_replay_ab.md`: what it shows (real DQN vs Fixed on the 53-node net, Ch.4 numbers), how to run (`python scripts/serve_replay.py --no-browser` → open the URL), controls, and a note that this is the honest DQN demo (the toy sandbox `demo_sandbox.md` is a concept illustration only, not a DQN result).
- [ ] **Step 3: Regression** — `PYTHONPATH=src:. python -m pytest tests/ -q` and `node --test tests/replay_ab/*.test.cjs` and `node --test tests/sandbox/*.test.cjs` all pass.
- [ ] **Step 4: Commit** — `git add scripts/serve_replay.py docs/demo_replay_ab.md && git commit -m "docs(replay-ab): serve URL + operator guide"`

---

## Self-Review
- Real DQN behavior + real Ch.4 numbers (−30.8%) → Tasks 1,3. ✔
- Frame-synchronized A/B on the real network → Task 3. ✔
- Per-intersection phase highlighting from real tlLogs → Task 2 (`drawSignals` + `roadSignal`). ✔
- Play/pause/scrub/speed/zoom → Task 3. ✔
- Honesty note + distinction from the toy sandbox → Tasks 2,4. ✔
- No Docker/container; reuses existing replays/roadnet/comparison → Global Constraints. ✔
- Placeholder scan: Task 2 CSS block has a stray `</style>` called out to remove; Task 3 loop code is specified but the full block lives in the brief. Type names (`parseRoadnet`,`parseReplay`,`roadSignal`,`makeTransform`,`waitHours`,`scoreboard`,`drawPanel`) consistent across tasks. ✔
