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
