// Browser glue: load model, run the sim loop, draw the intersection + signals.
(function () {
  "use strict";
  const C = window.SandboxCore;

  fetch("sandbox_model.json").then((r) => r.json()).then((model) => start(model));

  function start(model) {
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const it = model.intersection;

    // world -> screen transform (fit the approaches' far points into the canvas)
    const cx = it.geometry.center[0], cy = it.geometry.center[1];
    let maxR = 1;
    for (const ap of it.geometry.approaches) maxR = Math.max(maxR, 120);
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
      ctx.fillText(String(Math.round(q)), sx(d.x * 150) - 6, sy(d.y * 150));
    }
    if (s.flash > 0) s.flash -= 1;
  }

  function servedInLanes(it, greenIdx) {
    const set = new Set();
    const ph = it.green_phases[greenIdx];
    for (const mv of ph.movements) for (const il of mv.in_lanes) set.add(il);
    return set;
  }

  window.__sandboxDraw = drawFrame;         // Task 7 calls this each tick
  window.__sandboxServed = servedInLanes;
})();
