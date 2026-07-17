(function () {
  "use strict";
  const R = window.ReplayAB;
  const ROOT = ""; // served from repo root; paths are absolute from site root
  const SCENARIOS = [
    ["haichau_rush", "Cao điểm thực (rush)"],
    ["danang_peak", "Đà Nẵng peak"],
    ["haichau_peak", "Cao điểm quá tải (peak)"],
    ["haichau", "Quá tải nặng (haichau)"],
  ];
  const DEFAULT_SCENARIO = "haichau_rush";
  const ROADNET = (sc) => `/data/danang/replay_roadnet_${sc}.json`;
  const REPLAY = (sc, ctrl) => `/results/${sc}/demo/replay_${ctrl}_demo.txt`;
  const COMPARISON = (sc) => `/results/${sc}/comparison.json`;
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

  // Fetch roadnet + both panels' replays + comparison for one scenario. Used both
  // for the initial load and for the scenario-select reload (Task 3 IIFE below).
  function loadScenario(sc, leftCtrl, rightCtrl) {
    return Promise.all([fetchText(ROADNET(sc)), fetchText(REPLAY(sc, leftCtrl)),
                        fetchText(REPLAY(sc, rightCtrl)), fetchText(COMPARISON(sc))])
      .then(([rnTxt, leftTxt, rightTxt, cmpTxt]) => ({
        roadnet: R.parseRoadnet(JSON.parse(rnTxt)),
        comparison: JSON.parse(cmpTxt),
        leftSteps: R.parseReplay(leftTxt),
        rightSteps: R.parseReplay(rightTxt),
      }));
  }

  function loadAll() {
    const leftCtrl = "fixed_time", rightCtrl = "dqn";
    return loadScenario(DEFAULT_SCENARIO, leftCtrl, rightCtrl).then((d) => {
      const W = document.getElementById("canvas-left").width;
      const H = document.getElementById("canvas-left").height;
      const T = R.makeTransform(d.roadnet.bounds, W, H, 16);
      const state = {
        roadnet: d.roadnet, T, comparison: d.comparison,
        panels: { left: { ctrl: leftCtrl, steps: d.leftSteps },
                  right: { ctrl: rightCtrl, steps: d.rightSteps } },
        step: 0, playing: false, speed: 4, fetchText, REPLAY, loadGen: 0,
        CTRL_TO_ROW, CTRLS, drawPanel, scenario: DEFAULT_SCENARIO, SCENARIOS, loadScenario,
      };
      window.__replayAB = state;
      // initial static frame
      drawPanel(document.getElementById("canvas-left").getContext("2d"), d.roadnet, d.leftSteps[0], T);
      drawPanel(document.getElementById("canvas-right").getContext("2d"), d.roadnet, d.rightSteps[0], T);
      return state;
    });
  }

  window.ReplayABApp = { drawPanel, loadAll, loadScenario };
  loadAll().catch((e) => { console.error("replay_ab load failed:", e); });
})();

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
    const cvL = document.getElementById("canvas-left"), cvR = document.getElementById("canvas-right");
    const ctxL = cvL.getContext("2d"), ctxR = cvR.getContext("2d");
    state.zoom = false;

    // nSteps/T(full)/clusterT depend on the current scenario's roadnet + replay
    // lengths, so they live on `state` and get recomputed here — never frozen
    // in this closure — on scenario switch (and, defensively, controller switch).
    function recomputeDerived() {
      state.nSteps = Math.min(state.panels.left.steps.length, state.panels.right.steps.length);
      state.T = R.makeTransform(state.roadnet.bounds, cvL.width, cvL.height, 16);
      state.clusterT = makeClusterTransform(state.roadnet, cvL.width, cvL.height);
    }
    recomputeDerived();
    const curT = () => (state.zoom ? state.clusterT : state.T);

    const selL = document.getElementById("ctrl-left"), selR = document.getElementById("ctrl-right");
    const fill = (sel, cur) => { sel.innerHTML = state.CTRLS.map(([v, t]) => '<option value="' + v + '"' + (v === cur ? " selected" : "") + '>' + t + "</option>").join(""); };
    fill(selL, state.panels.left.ctrl); fill(selR, state.panels.right.ctrl);
    const onSelect = (side, sel) => { sel.onchange = () => {
      state.panels[side].ctrl = sel.value;
      // Stamp this request with the current generation and only apply it if it's
      // still the newest in-flight load when it resolves — otherwise a stale
      // scenario/controller switch could resolve last and desync this panel's
      // steps from state.roadnet/state.comparison.
      const myGen = ++state.loadGen;
      state.fetchText(state.REPLAY(state.scenario, sel.value)).then((txt) => {
        if (myGen !== state.loadGen) return; // superseded by a newer switch; drop
        state.panels[side].steps = R.parseReplay(txt);
        recomputeDerived();
        state.step = Math.min(state.step, state.nSteps - 1);
        scrub.max = state.nSteps - 1; scrub.value = state.step;
        redraw(); updateScore();
      }).catch((e) => console.error("switch controller failed:", e));
    }; };
    onSelect("left", selL); onSelect("right", selR);

    const scenarioSel = document.getElementById("scenario");
    scenarioSel.innerHTML = state.SCENARIOS.map(([v, t]) => '<option value="' + v + '"' + (v === state.scenario ? " selected" : "") + '>' + t + "</option>").join("");
    scenarioSel.onchange = () => {
      const sc = scenarioSel.value;
      if (sc === state.scenario) return;
      const leftCtrl = state.panels.left.ctrl, rightCtrl = state.panels.right.ctrl;
      state.playing = false; playBtn.textContent = "▶ Chạy";
      scenarioSel.disabled = true;
      // Same request-generation guard as onSelect above: only the newest
      // scenario/controller switch in flight is allowed to write into `state`.
      const myGen = ++state.loadGen;
      state.loadScenario(sc, leftCtrl, rightCtrl).then((d) => {
        scenarioSel.disabled = false;
        if (myGen !== state.loadGen) return; // superseded by a newer switch; drop
        state.scenario = sc;
        state.roadnet = d.roadnet;
        state.comparison = d.comparison;
        state.panels.left.steps = d.leftSteps;
        state.panels.right.steps = d.rightSteps;
        state.step = 0;
        recomputeDerived();
        scrub.max = state.nSteps - 1; scrub.value = 0;
        redraw(); updateScore();
      }).catch((e) => {
        console.error("switch scenario failed:", e);
        scenarioSel.disabled = false;
        if (myGen !== state.loadGen) return; // a newer switch superseded this failed one; don't revert its value
        scenarioSel.value = state.scenario; // revert the select to the still-loaded scenario
      });
    };

    document.getElementById("controls").innerHTML =
      '<button id="play">▶ Chạy</button>' +
      '<label>Bước: <input id="scrub" type="range" min="0" max="' + (state.nSteps - 1) + '" value="0"></label>' +
      '<span id="steplabel">0 / ' + (state.nSteps - 1) + '</span>' +
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
      state.drawPanel(ctxL, state.roadnet, state.panels.left.steps[state.step], t);
      state.drawPanel(ctxR, state.roadnet, state.panels.right.steps[state.step], t);
      scrub.value = state.step; stepLabel.textContent = state.step + " / " + (state.nSteps - 1);
    }
    function updateScore() {
      const sb = R.scoreboard(state.comparison, state.CTRL_TO_ROW[state.panels.left.ctrl], state.CTRL_TO_ROW[state.panels.right.ctrl]);
      const fmt = (e) => e ? (e.key + ": " + e.vehH.toFixed(0) + " veh-h (" + (e.pctVsFixed >= 0 ? "▼ " : "▲ ") + Math.abs(e.pctVsFixed).toFixed(1) + "% vs Fixed)") : "—";
      const lv = sb.left ? sb.left.vehH : Infinity, rv = sb.right ? sb.right.vehH : Infinity;
      const leftWin = lv < rv, rightWin = rv < lv;
      const scName = (state.SCENARIOS.find((s) => s[0] === state.scenario) || [state.scenario, state.scenario])[1];
      document.getElementById("scoreboard").innerHTML =
        "<div><b>Thời gian chờ tích luỹ cả episode (số thật Chương 4) — kịch bản: " + scName + ":</b></div>" +
        '<div class="' + (leftWin ? "sb-win" : "") + '">TRÁI — ' + fmt(sb.left) + "</div>" +
        '<div class="' + (rightWin ? "sb-win" : "") + '">PHẢI — ' + fmt(sb.right) + "</div>" +
        '<div class="note">Cùng kịch bản/seed; veh-h thấp hơn = tốt hơn.</div>';
    }

    let acc = 0, last = null;
    function loop(ts) {
      if (last == null) last = ts;
      const dtSec = Math.min(0.1, (ts - last) / 1000); last = ts;
      if (state.playing) { acc += dtSec * state.speed; while (acc >= 1) { acc -= 1; state.step = (state.step + 1) % state.nSteps; } redraw(); }
      requestAnimationFrame(loop);
    }
    redraw(); updateScore(); requestAnimationFrame(loop);
  }

  // Task 2's loadAll() sets window.__replayAB asynchronously; wait for it, then wire the UI.
  const BOOT_MAX_ATTEMPTS = 150; // ~150 * 30ms ≈ 4.5s
  let bootAttempts = 0;
  const boot = setInterval(() => {
    if (window.__replayAB && window.__replayAB.panels) { clearInterval(boot); runUI(window.__replayAB); return; }
    bootAttempts++;
    if (bootAttempts >= BOOT_MAX_ATTEMPTS) {
      clearInterval(boot);
      console.error("replay_ab: timed out waiting for window.__replayAB (loadAll() likely failed — see earlier console error).");
      const sb = document.getElementById("scoreboard");
      if (sb) sb.innerHTML = '<div class="note">Không tải được dữ liệu replay — kiểm tra server.</div>';
    }
  }, 30);
})();
