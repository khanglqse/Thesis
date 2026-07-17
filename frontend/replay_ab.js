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
    state.speed = +speed.value;
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
      const lv = sb.left ? sb.left.vehH : Infinity, rv = sb.right ? sb.right.vehH : Infinity;
      const leftWin = lv < rv, rightWin = rv < lv;
      document.getElementById("scoreboard").innerHTML =
        "<div><b>Thời gian chờ tích luỹ cả episode (số thật Chương 4):</b></div>" +
        '<div class="' + (leftWin ? "sb-win" : "") + '">TRÁI — ' + fmt(sb.left) + "</div>" +
        '<div class="' + (rightWin ? "sb-win" : "") + '">PHẢI — ' + fmt(sb.right) + "</div>" +
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
