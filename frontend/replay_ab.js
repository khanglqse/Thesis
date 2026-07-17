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
