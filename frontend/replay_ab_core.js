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

  // Centre of the densest cell of vehicle positions, sampled every `every`-th
  // frame. Both demos aim their zoom button here: the network's *geometric*
  // centroid is an empty side street (measured on haichau_rush: 0 of 454
  // vehicles fell inside the centroid view), so zooming there shows bare roads.
  // Deterministic: highest count wins, ties broken by lowest cell (gx, gy).
  function busiestSpot(steps, opts) {
    opts = opts || {};
    const cell = opts.cell || 400, every = opts.every || 10;
    const cells = new Map();
    for (let i = 0; i < (steps || []).length; i += every) {
      const f = steps[i];
      if (!f || !f.cars) continue;
      for (const c of f.cars) {
        const gx = Math.floor(c.x / cell), gy = Math.floor(c.y / cell);
        const k = gx + ":" + gy;
        const e = cells.get(k);
        if (e) e.n++; else cells.set(k, { gx: gx, gy: gy, n: 1 });
      }
    }
    let best = null;
    for (const e of cells.values()) {
      if (!best || e.n > best.n ||
          (e.n === best.n && (e.gx < best.gx || (e.gx === best.gx && e.gy < best.gy)))) best = e;
    }
    if (!best) return null;
    return { x: best.gx * cell + cell / 2, y: best.gy * cell + cell / 2, n: best.n, cell: cell };
  }

  // Intersections that actually run a light in this frame: a road whose status
  // list contains g/r ends at a signalised node. Used to keep the demo camera on
  // a junction where there is a signal to look at.
  function signalizedInters(roadnet, tl) {
    const ids = new Set();
    for (const r of roadnet.roads) {
      if (r.end && roadSignal(tl && tl[r.id])) ids.add(r.end);
    }
    return roadnet.inters.filter((n) => ids.has(n.id));
  }

  // The junction with the most vehicles around it. A better camera target than
  // busiestSpot's grid cell: queues form at stop lines, so this frames a place
  // where the two controllers visibly differ, not just a busy stretch of road.
  // Deterministic: highest count wins, ties broken by the earlier intersection.
  function busiestJunction(steps, inters, opts) {
    opts = opts || {};
    const radius = opts.radius || 120, every = opts.every || 10;
    if (!inters || !inters.length) return null;
    const r2 = radius * radius;
    const counts = new Array(inters.length).fill(0);
    for (let i = 0; i < (steps || []).length; i += every) {
      const f = steps[i];
      if (!f || !f.cars) continue;
      for (const c of f.cars) {
        for (let j = 0; j < inters.length; j++) {
          const dx = c.x - inters[j].x, dy = c.y - inters[j].y;
          if (dx * dx + dy * dy <= r2) counts[j]++;
        }
      }
    }
    let best = 0;
    for (let j = 1; j < inters.length; j++) if (counts[j] > counts[best]) best = j;
    if (!counts[best]) return null;
    return { x: inters[best].x, y: inters[best].y, id: inters[best].id, n: counts[best] };
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

  return { parseRoadnet, parseReplay, roadSignal, makeTransform, busiestSpot,
           signalizedInters, busiestJunction, waitHours, scoreboard };
});
