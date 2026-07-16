// Browser glue: load model, run the sim loop, draw the intersection + signals.
(function () {
  "use strict";
  const C = window.SandboxCore;

  fetch("sandbox_model.json").then((r) => r.json()).then((model) => start(model))
    .catch(function (e) { console.error("sandbox_model.json load/render failed:", e); });

  function start(model) {
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const it = model.intersection;

    // world -> screen transform: fit the outermost drawn radius into the canvas.
    // queue ticks reach 58 + 7*19 = 191 (see drawFrame); labels/spokes sit inside that.
    const maxR = 195;
    const scale = (Math.min(W, H) * 0.42) / maxR;
    function sx(dx) { return W / 2 + dx * scale; }
    function sy(dy) { return H / 2 - dy * scale; }   // y up

    const micro = new C.MicroModel(it, model.meta, C.mulberry32(42));
    const state = { model, micro, ctx, W, H, sx, sy, greenIdx: 0, flash: 0 };
    window.__sandbox = state;    // Task 7 attaches controllers/loop; expose for wiring

    drawFrame(state);
  }

  function approachDir(ap) {   // unit vector from center toward the approach's far side
    const a = ap.angle_deg * Math.PI / 180;
    return { x: Math.cos(a), y: Math.sin(a) };
  }

  function drawFrame(s) {
    const { ctx, W, H, sx, sy, model } = s;
    const it = model.intersection;
    ctx.clearRect(0, 0, W, H);
    // roads as thick spokes
    for (const ap of it.geometry.approaches) {
      const d = approachDir(ap);
      ctx.strokeStyle = "#88a"; ctx.lineWidth = 22;
      ctx.beginPath(); ctx.moveTo(sx(0), sy(0)); ctx.lineTo(sx(d.x * 120), sy(d.y * 120)); ctx.stroke();
    }
    // hub
    ctx.fillStyle = s.flash > 0 ? "#fff8b0" : "#c8d4dc";
    ctx.beginPath(); ctx.arc(sx(0), sy(0), 26, 0, Math.PI * 2); ctx.fill();
    // queues + signal heads per incoming approach
    const greenLanes = servedInLanes(it, s.greenIdx);
    for (const ap of it.geometry.approaches) {
      if (ap.role !== "in") continue;
      const d = approachDir(ap);
      const anyGreen = ap.lanes.some((l) => greenLanes.has(l));
      // signal head near the hub
      ctx.fillStyle = anyGreen ? "#85ee00" : "#db635e";
      ctx.beginPath(); ctx.arc(sx(d.x * 42), sy(d.y * 42), 8, 0, Math.PI * 2); ctx.fill();
      // queued cars as stacked ticks going outward
      let q = 0; for (const l of ap.lanes) q += s.micro.inCounts[l] || 0;
      ctx.fillStyle = "#37506a";
      for (let i = 0; i < Math.min(Math.round(q), 20); i++) {
        const rr = 58 + i * 7;
        ctx.fillRect(sx(d.x * rr) - 3, sy(d.y * rr) - 3, 6, 6);
      }
      // count label
      ctx.fillStyle = "#0b1118"; ctx.font = "13px sans-serif";
      ctx.fillText(String(Math.round(q)), sx(d.x * 135) - 6, sy(d.y * 135));
    }
    if (s.flash > 0) s.flash -= 1;
  }

  function servedInLanes(it, greenIdx) {
    const set = new Set();
    const ph = it.green_phases[greenIdx];
    for (const mv of ph.movements) for (const il of mv.in_lanes) set.add(il);
    return set;
  }

  window.__sandboxDraw = drawFrame;
  window.__sandboxServed = servedInLanes;

  function buildControls(s, onChange) {
    const it = s.model.intersection;
    const el = document.getElementById("controls");
    const ctrlOpts = [["dqn", "RL (DQN)"], ["fixed_time", "Cố định"], ["max_pressure", "Max-Pressure"], ["random", "Ngẫu nhiên"]]
      .map(([v, t]) => `<option value="${v}">${t}</option>`).join("");
    el.innerHTML =
      `<label>Bộ điều khiển: <select id="ctrl">${ctrlOpts}</select></label>` +
      `<label>Lưu lượng: <input id="demand" type="range" min="0" max="0.6" step="0.02" value="0.35"></label>` +
      `<label>Tốc độ: <input id="speed" type="range" min="1" max="20" step="1" value="6"></label>` +
      `<button id="play">Tạm dừng</button> <button id="reset">Đặt lại</button>`;
    document.getElementById("ctrl").onchange = (e) => onChange.ctrl(e.target.value);
    document.getElementById("demand").oninput = (e) => onChange.demand(parseFloat(e.target.value));
    document.getElementById("speed").oninput = (e) => onChange.speed(parseInt(e.target.value, 10));
    document.getElementById("play").onclick = () => onChange.togglePlay();
    document.getElementById("reset").onclick = () => onChange.reset();
  }

  function approachesViForPhase(it, greenIdx) {
    return it.green_phases[greenIdx].approaches_vi || [];
  }

  function runLoop(s) {
    const C = window.SandboxCore, it = s.model.intersection, meta = s.model.meta;
    let ctrlKey = "dqn", demand = 0.35, speed = 6, playing = true;
    let visible = s.micro;
    let shadow = new C.MicroModel(it, meta, C.mulberry32(42));   // same seed => same arrivals
    let visCtrl = C.CONTROLLERS[ctrlKey](s.model);
    let fixedCtrl = C.CONTROLLERS.fixed_time(s.model);
    const rng = C.mulberry32(99);
    let sb = new C.Scoreboard();
    let sinceDecision = 0;
    const rate = () => {
      const r = {}; for (const ap of it.geometry.approaches) if (ap.role === "in") r[ap.road] = demand; return r;
    };

    function decide(micro, ctrl, label, isRL) {
      const { choice, q } = ctrl.decide(micro, { tSinceCycle: micro.t, rng });
      const res = micro.applyChoice(choice);
      s.greenIdx = visible.greenIdx;
      if (micro === visible) {
        s.flash = 6;
        updateQBars(s, q);
        updatePhaseBanner(s);
        const appr = approachesViForPhase(it, micro.greenIdx);
        let reason = "";
        if (q) { let mx = -Infinity, mi = 0; for (let j = 0; j < it.num_greens; j++) if (q[j] > mx) { mx = q[j]; mi = j; } reason = "Q lớn nhất ở pha " + mi; }
        logLine(s, C.formatDecision({ t: micro.t, ctrlLabel: label, changed: res.changed,
          oldPhase: res.oldPhase, newPhase: res.newPhase, approachesVi: appr, reason,
          qWin: q ? Math.max.apply(null, Array.from(q).slice(0, it.num_greens)) : null }), isRL);
      }
    }

    function tick() {
      if (playing) {
        const dt = 1.0;
        for (let sub = 0; sub < speed; sub++) {
          visible.arrivals(dt, rate()); shadow.arrivals(dt, rate());
          visible.dischargeAndDecay(dt); shadow.dischargeAndDecay(dt);
          sb.accumulate(visCtrl.name, visible.totalQueue(), dt);
          sb.accumulate("Fixed-Time", shadow.totalQueue(), dt);
          sinceDecision += dt;
          if (sinceDecision >= meta.action_interval) {
            sinceDecision = 0;
            decide(visible, visCtrl, visCtrl.labelVi, visCtrl.isRL);
            decide(shadow, fixedCtrl, "Fixed-Time(bóng)", false);
          }
        }
        updateScoreboard(s, sb);
      }
      window.__sandboxDraw(s);
      requestAnimationFrame(tick);
    }

    buildControls(s, {
      ctrl: (v) => {
        ctrlKey = v; visCtrl = C.CONTROLLERS[v](s.model);
        sb = new C.Scoreboard();
        document.getElementById("scoreboard").innerHTML = "";
        sinceDecision = 0;
      },
      demand: (v) => { demand = v; },
      speed: (v) => { speed = v; },
      togglePlay: () => { playing = !playing; document.getElementById("play").textContent = playing ? "Tạm dừng" : "Tiếp tục"; },
      reset: () => {
        visible = s.micro = new C.MicroModel(it, meta, C.mulberry32(42));
        shadow = new C.MicroModel(it, meta, C.mulberry32(42));
        sb.acc = {}; document.getElementById("log").innerHTML = ""; s.greenIdx = 0;
        sinceDecision = 0;
      },
    });
    tick();
  }

  function updatePhaseBanner(s) {
    const it = s.model.intersection;
    document.getElementById("phase-label").textContent =
      "#" + s.greenIdx + " (" + (it.green_phases[s.greenIdx].approaches_vi || []).join("–") + ")";
  }
  function updateQBars(s, q) {
    const it = s.model.intersection, host = document.getElementById("qbars");
    if (!q) { host.innerHTML = "<div class='note'>Baseline không dùng Q-value.</div>"; return; }
    let mx = -Infinity, mi = 0; for (let j = 0; j < it.num_greens; j++) if (q[j] > mx) { mx = q[j]; mi = j; }
    let mn = Infinity; for (let j = 0; j < it.num_greens; j++) mn = Math.min(mn, q[j]);
    let html = "<div class='note'>Q-value mỗi pha (DQN):</div>";
    for (let j = 0; j < it.num_greens; j++) {
      const w = Math.round(100 * (q[j] - mn) / (mx - mn + 1e-6));
      html += `<div class="qbar ${j === mi ? "win" : ""}"><i style="width:${w}%"></i><span>pha ${j}: ${q[j].toFixed(2)}</span></div>`;
    }
    host.innerHTML = html;
  }
  function updateScoreboard(s, sb) {
    const sum = sb.summary(), host = document.getElementById("scoreboard");
    const cur = sum.curKey ? sum.visited[sum.curKey] : 0, fixed = sum.visited["Fixed-Time"] || 0;
    const arrow = sum.deltaPctVsFixed >= 0 ? "▼" : "▲";
    host.innerHTML = `<div><b>Thời gian chờ tích luỹ (trong sandbox)</b></div>` +
      `<div>${sum.curKey || "—"}: ${cur.toFixed(2)} veh-h</div>` +
      `<div>Fixed-Time (bóng): ${fixed.toFixed(2)} veh-h</div>` +
      `<div>${arrow} ${Math.abs(sum.deltaPctVsFixed).toFixed(1)}% so với Fixed-Time</div>`;
  }
  function logLine(s, text, isRL) {
    const host = document.getElementById("log");
    const div = document.createElement("div");
    div.className = "log-line " + (isRL ? "rl" : "base");
    div.textContent = text;
    host.insertBefore(div, host.firstChild);
    while (host.childNodes.length > 200) host.removeChild(host.lastChild);
  }

  // kick off once the model+state are ready (start() sets window.__sandbox)
  const _boot = setInterval(() => {
    if (window.__sandbox) { clearInterval(_boot); runLoop(window.__sandbox); }
  }, 30);
})();
