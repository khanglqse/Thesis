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
  function validateNetwork(nodes) {
    if (!Array.isArray(nodes) || !nodes.length) throw new Error("network has no nodes");
    const ids = new Set(nodes.map(node => node && node.id));
    if (ids.has(undefined) || ids.size !== nodes.length)
      throw new Error("network node IDs must be present and unique");
    for (const node of nodes) {
      if (!Number.isFinite(Number(node.x)) || !Number.isFinite(Number(node.y)))
        throw new Error("network nodes require finite coordinates");
      const neighbors = node.neighbors;
      if (!Array.isArray(neighbors)) throw new Error("network neighbors must be a list");
      if (neighbors.some(id => !ids.has(id)))
        throw new Error("network node references an unknown neighbor");
    }
    return true;
  }
  function networkTransform(nodes, width, height, padding) {
    validateNetwork(nodes);
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
  function geometryPoints(network) {
    const roads = network && network.geometry && network.geometry.roads;
    if (!Array.isArray(roads)) return [];
    return roads.flatMap(road => Array.isArray(road.points) ? road.points : [])
      .filter(point => Array.isArray(point) && point.length >= 2)
      .map(point => ({ x: Number(point[0]), y: Number(point[1]) }))
      .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
  }
  function viewTransform(points, width, height, padding) {
    if (!Array.isArray(points) || !points.length) throw new Error("view has no geometry");
    padding = Number(padding) || 0;
    const xs = points.map(point => Number(point.x));
    const ys = points.map(point => Number(point.y));
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const rangeX = Math.max(maxX - minX, 1), rangeY = Math.max(maxY - minY, 1);
    const scale = Math.min((width - 2 * padding) / rangeX, (height - 2 * padding) / rangeY);
    const offsetX = (width - rangeX * scale) / 2;
    const offsetY = (height - rangeY * scale) / 2;
    return { scale, x: value => offsetX + (Number(value) - minX) * scale,
      y: value => height - offsetY - (Number(value) - minY) * scale };
  }
  function countVehicles(frame) {
    if (frame && frame.counts) return frame.counts;
    const vehicles = frame && Array.isArray(frame.vehicles) ? frame.vehicles : [];
    if (!vehicles.length) return null;
    const count = kind => vehicles.filter(vehicle => vehicle.class === kind).length;
    return { active_total: vehicles.length, rendered: vehicles.length,
      motorbike: count("motorbike"), car: count("car"),
      unknown: vehicles.length - count("motorbike") - count("car") };
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
  function evidenceValue(value) {
    if (value === null || value === undefined || value === "") return "N/A";
    return String(value);
  }
  function provenanceRows(replay, acceptance) {
    replay = replay || {};
    const metrics = replay.metrics || {};
    const accepted = acceptance && acceptance.accepted;
    return {
      run_id: evidenceValue(replay.run_id),
      case_id: evidenceValue(replay.case_id),
      controller: evidenceValue(replay.controller_id),
      checkpoint: evidenceValue(replay.checkpoint_sha256),
      checkpoint_contract: evidenceValue(replay.checkpoint_contract_sha256),
      learning_seed: evidenceValue(replay.learning_seed),
      terminal_pending: evidenceValue(metrics.pending),
      pending_integral: evidenceValue(metrics.pending_integral_vehicle_seconds),
      acceptance: accepted === true ? "Accepted" : accepted === false ? "Not accepted" : "N/A",
    };
  }
  return {
    queueColor,
    frameIndexAt,
    validateNetwork,
    networkTransform,
    nearestNode,
    geometryPoints,
    viewTransform,
    countVehicles,
    pairedReplays,
    provenanceRows,
  };
});
