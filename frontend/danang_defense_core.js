(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DanangDefense = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  function frameIndexAt(frames, seconds) {
    if (!frames || !frames.length) return 0;
    let lo = 0, hi = frames.length - 1;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (frames[mid].t <= seconds) lo = mid; else hi = mid - 1;
    }
    return lo;
  }
  function transform(bounds, width, height, padding) {
    padding = padding || 26;
    const [minX, minY, maxX, maxY] = bounds;
    const scale = Math.min((width - 2 * padding) / (maxX - minX),
                           (height - 2 * padding) / (maxY - minY));
    return { scale,
      x: value => padding + (value - minX) * scale,
      y: value => height - padding - (value - minY) * scale };
  }
  function phaseLabel(index) {
    return ["NW–SE green", "clearance", "NE–SW green", "clearance",
            "turn movements green", "clearance"][index] || "unknown";
  }
  function representativeChange(fixed, learned) {
    return 100 * (learned - fixed) / fixed;
  }
  return { frameIndexAt, transform, phaseLabel, representativeChange };
});
