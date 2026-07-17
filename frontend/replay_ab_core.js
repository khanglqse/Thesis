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
