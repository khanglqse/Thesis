const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const R3 = require("../../frontend/replay_3d_core.js");
const RAB = require("../../frontend/replay_ab_core.js");

test("carFootprint axis-aligned at angle 0, centered", () => {
  const p = R3.carFootprint(10, 20, 0, 4, 2);
  assert.equal(p.length, 4);
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...xs) - Math.min(...xs) - 4) < 1e-9);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 2) < 1e-9);
  assert.ok(Math.abs(xs.reduce((a, b) => a + b, 0) / 4 - 10) < 1e-9);
  assert.ok(Math.abs(ys.reduce((a, b) => a + b, 0) / 4 - 20) < 1e-9);
});

test("carFootprint rotated pi/2 swaps extents", () => {
  const p = R3.carFootprint(0, 0, Math.PI / 2, 4, 2);
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...xs) - Math.min(...xs) - 2) < 1e-9);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 4) < 1e-9);
});

test("laneBars: g/r bars, i skipped, set back from endpoint, distinct lanes", () => {
  const points = [{ x: 0, y: 0 }, { x: 100, y: 0 }]; // travel +x
  const bars = R3.laneBars(points, 3, ["g", "i", "r"],
    { laneWidth: 3, barLen: 1.5, setback: 4 });
  assert.equal(bars.length, 2);
  assert.deepEqual(bars.map((b) => b.status), ["g", "r"]);
  for (const b of bars)
    for (const [x] of b.polygon) assert.ok(x > 95 && x < 97.1, "setback ~4m, got x=" + x);
  const mean = (b) => b.polygon.map((q) => q[1]).reduce((a, c) => a + c, 0) / 4;
  assert.ok(Math.abs(mean(bars[0]) - mean(bars[1])) >= 3, "bars in distinct lane slots");
  const ys = bars[0].polygon.map((q) => q[1]);
  assert.ok(Math.abs(Math.max(...ys) - Math.min(...ys) - 3) < 1e-9, "bar spans one laneWidth");
});

test("laneBars: degenerate inputs give []", () => {
  assert.deepEqual(R3.laneBars([{ x: 0, y: 0 }], 2, ["g"], {}), []);
  assert.deepEqual(R3.laneBars([{ x: 0, y: 0 }, { x: 1, y: 0 }], 2, null, {}), []);
});

test("fitView: centered target, finite zoom, wider bounds -> smaller zoom", () => {
  const v = R3.fitView({ minX: 0, maxX: 1000, minY: 0, maxY: 500 }, 640, 480);
  assert.deepEqual(v.target, [500, 250, 0]);
  assert.ok(Number.isFinite(v.zoom));
  assert.equal(v.rotationX, 45);
  const v2 = R3.fitView({ minX: 0, maxX: 2000, minY: 0, maxY: 500 }, 640, 480);
  assert.ok(v2.zoom < v.zoom);
});

test("laneBars on real haichau_rush frame 0 produces >0 bars", () => {
  const root = path.join(__dirname, "..", "..");
  const rn = RAB.parseRoadnet(JSON.parse(fs.readFileSync(
    path.join(root, "data/danang/replay_roadnet_haichau_rush.json"), "utf8")));
  const line0 = fs.readFileSync(
    path.join(root, "results/haichau_rush/demo/replay_dqn_demo.txt"), "utf8").split("\n")[0];
  const step = RAB.parseReplay(line0)[0];
  let total = 0;
  for (const road of rn.roads) {
    const st = step.tl[road.id];
    if (st) total += R3.laneBars(road.points, road.nLanes, st, {}).length;
  }
  assert.ok(total > 0, "expected some g/r bars in frame 0, got " + total);
});

test("zoomForSpan makes vehicles visible; whole-network fit does not", () => {
  const W = 780;
  // 300 m across a 780 px panel -> 2.6 px per metre -> a 2 m vehicle ~5 px
  const z = R3.zoomForSpan(W, 300);
  assert.ok(Math.abs(z - Math.log2(780 / 300)) < 1e-9);
  assert.ok(2 * Math.pow(2, z) > 4, "a 2 m vehicle must exceed 4 px");
  // the Hải Châu network is ~7 km x 10 km: fitting it all leaves vehicles sub-pixel
  const fit = R3.fitView({ minX: 0, minY: 0, maxX: 6864, maxY: 9933 }, W, W);
  assert.ok(2 * Math.pow(2, fit.zoom) < 1, "sanity: whole-network fit hides vehicles");
  assert.ok(z > fit.zoom);
});
