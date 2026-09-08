(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.HaiChauNetworkDemo = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }
  function hex(rgb) {
    return "#" + rgb.map(value => Math.round(value).toString(16).padStart(2, "0")).join("");
  }
  function mix(left, right, amount) {
    return hex(left.map((value, index) => value + (right[index] - value) * amount));
  }
  function queueColor(queue, maximum) {
    const ratio = clamp(Number(queue) / Math.max(Number(maximum) || 1, 1), 0, 1);
    const green = [85, 185, 133], amber = [233, 180, 76], red = [224, 93, 68];
    return ratio <= 0.5
      ? mix(green, amber, ratio * 2)
      : mix(amber, red, (ratio - 0.5) * 2);
  }
  function frameIndexAt(frames, seconds) {
    if (!frames || !frames.length) return 0;
    let low = 0, high = frames.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (Number(frames[middle].t) <= Number(seconds)) low = middle;
      else high = middle - 1;
    }
    return low;
  }
  function networkTransform(nodes, width, height, padding) {
    if (!nodes || !nodes.length) throw new Error("network has no nodes");
    padding = Number(padding) || 0;
    const xs = nodes.map(node => Number(node.x));
    const ys = nodes.map(node => Number(node.y));
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const rangeX = Math.max(maxX - minX, 1);
    const rangeY = Math.max(maxY - minY, 1);
    const scale = Math.min(
      (width - 2 * padding) / rangeX,
      (height - 2 * padding) / rangeY,
    );
    const offsetX = (width - rangeX * scale) / 2;
    const offsetY = (height - rangeY * scale) / 2;
    return {
      scale,
      x: value => offsetX + (Number(value) - minX) * scale,
      y: value => height - offsetY - (Number(value) - minY) * scale,
    };
  }
  function nearestNode(nodes, x, y, radius) {
    let selected = null, distance = Number(radius) ** 2;
    for (const node of nodes || []) {
      const candidate = (Number(node.x) - x) ** 2 + (Number(node.y) - y) ** 2;
      if (candidate <= distance) {
        selected = node;
        distance = candidate;
      }
    }
    return selected;
  }
  function pairedReplays(entries) {
    const fixed = entries.filter(entry => entry.controller_id === "tuned_fixed");
    const learned = entries.filter(entry => entry.controller_id === "neighbor_phase_ddqn");
    if (fixed.length !== 1 || learned.length !== 1 ||
        fixed[0].case_id !== learned[0].case_id) {
      throw new Error("replay comparison requires one matched case");
    }
    return { fixed: fixed[0], learned: learned[0] };
  }
  return {
    queueColor,
    frameIndexAt,
    networkTransform,
    nearestNode,
    pairedReplays,
  };
});
