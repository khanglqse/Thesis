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

  // ---- vehicle meshes ------------------------------------------------------
  // Low-poly, boxes only, authored in METRES with +x = forward, +z = up and the
  // origin at the vehicle centre on the ground. Sizes are the CityFlow vehicle
  // templates carried in the replay itself — 2.0 x 1.0 (motorbike, ~90% of
  // vehicles on this network) and 5.0 x 2.0 (car, ~10%) — so the two shapes on
  // screen are read from the data, not assigned for decoration.

  function boxInto(m, x0, x1, y0, y1, z0, z1) {
    const faces = [
      [[1, 0, 0], [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]],
      [[-1, 0, 0], [[x0, y1, z0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1]]],
      [[0, 1, 0], [[x1, y1, z0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1]]],
      [[0, -1, 0], [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]],
      [[0, 0, 1], [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]],
      [[0, 0, -1], [[x0, y1, z0], [x1, y1, z0], [x1, y0, z0], [x0, y0, z0]]],
    ];
    for (const face of faces) {
      const n = face[0], corners = face[1];
      const base = m.positions.length / 3;
      for (const c of corners) {
        m.positions.push(c[0], c[1], c[2]);
        m.normals.push(n[0], n[1], n[2]);
      }
      m.indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }

  function finishMesh(m, dims) {
    return {
      positions: new Float32Array(m.positions),
      normals: new Float32Array(m.normals),
      indices: new Uint16Array(m.indices),
      dims: dims,
    };
  }

  // kind: "car" -> 5.0 x 2.0 template; anything else -> 2.0 x 1.0 motorbike.
  function vehicleMesh(kind) {
    const m = { positions: [], normals: [], indices: [] };
    if (kind === "car") {
      boxInto(m, -2.5, 2.5, -1.0, 1.0, 0.35, 1.0);      // body
      boxInto(m, -1.3, 0.9, -0.85, 0.85, 1.0, 1.55);    // cabin
      boxInto(m, 1.2, 1.9, -1.0, -0.78, 0, 0.35);       // wheels
      boxInto(m, 1.2, 1.9, 0.78, 1.0, 0, 0.35);
      boxInto(m, -1.9, -1.2, -1.0, -0.78, 0, 0.35);
      boxInto(m, -1.9, -1.2, 0.78, 1.0, 0, 0.35);
      return finishMesh(m, { len: 5.0, wid: 2.0, height: 1.55 });
    }
    // Seen from directly above (the angle the demo is most often read at) the
    // silhouette has to say "motorbike", so the body is a solid mass along the
    // long axis with the handlebar as a thin T at the very front — an earlier
    // version put a full-width bar mid-body and every vehicle read as a "+".
    boxInto(m, -1.0, 0.55, -0.2, 0.2, 0.35, 0.75);      // frame + seat
    boxInto(m, -0.5, 0.2, -0.29, 0.29, 0.75, 1.5);      // rider
    boxInto(m, 0.58, 0.68, -0.5, 0.5, 0.78, 0.9);       // handlebar: sets full width
    boxInto(m, 0.55, 1.0, -0.1, 0.1, 0, 0.55);          // front wheel
    boxInto(m, -0.98, -0.5, -0.1, 0.1, 0, 0.55);        // rear wheel
    boxInto(m, 0.3, 0.62, -0.16, 0.16, 0.55, 0.95);     // front cowl
    return finishMesh(m, { len: 2.0, wid: 1.0, height: 1.5 });
  }

  function meshBounds(mesh) {
    const p = mesh.positions;
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < p.length; i += 3)
      for (let k = 0; k < 3; k++) {
        if (p[i + k] < lo[k]) lo[k] = p[i + k];
        if (p[i + k] > hi[k]) hi[k] = p[i + k];
      }
    return { min: lo, max: hi };
  }

  // OrbitView zoom that fits `span` metres across a W-pixel panel. At the
  // whole-network fit zoom a 2 m vehicle is ~0.1 px (invisible), so the demo
  // needs a "zoom to traffic" view: span ~300 m puts a vehicle at ~5 px.
  function zoomForSpan(W, span) {
    return Math.log2(Math.max(1, W) / Math.max(1, span));
  }

  return { carFootprint, laneBars, fitView, zoomForSpan, vehicleMesh, meshBounds };
});
