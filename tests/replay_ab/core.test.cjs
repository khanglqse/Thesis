const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const R = require("../../frontend/replay_ab_core.js");

const ROOT = path.join(__dirname, "../..");
const roadnet = JSON.parse(fs.readFileSync(path.join(ROOT, "data/danang/replay_roadnet_haichau_rush.json"), "utf8"));
const replayTxt = fs.readFileSync(path.join(ROOT, "results/haichau_rush/demo/replay_dqn_demo.txt"), "utf8");
const comparison = JSON.parse(fs.readFileSync(path.join(ROOT, "results/haichau_rush/comparison.json"), "utf8"));

test("parseRoadnet returns roads/inters/bounds", () => {
  const rn = R.parseRoadnet(roadnet);
  assert.ok(rn.roads.length > 100);
  assert.ok(rn.inters.length >= 1);
  assert.ok(rn.bounds.maxX > rn.bounds.minX && rn.bounds.maxY > rn.bounds.minY);
  const r0 = rn.roads.find((r) => r.points && r.points.length >= 2);
  assert.ok(r0 && typeof r0.nLanes === "number" && r0.end);
});

test("parseReplay yields 120 steps with cars + tl", () => {
  const steps = R.parseReplay(replayTxt);
  assert.strictEqual(steps.length, 120);
  const s = steps[0];
  assert.ok(s.cars.length > 0 && typeof s.cars[0].x === "number");
  assert.ok(Object.keys(s.tl).length > 0);
});

test("roadSignal classifies green/red/off", () => {
  assert.strictEqual(R.roadSignal(["i", "g", "i"]), "green");
  assert.strictEqual(R.roadSignal(["r", "i"]), "red");
  assert.strictEqual(R.roadSignal(["i", "i"]), null);
  assert.strictEqual(R.roadSignal(undefined), null);
});

test("makeTransform maps bounds inside canvas, y flipped", () => {
  const t = R.makeTransform({ minX: 0, minY: 0, maxX: 100, maxY: 50 }, 200, 200, 10);
  assert.ok(t.sx(0) >= 10 - 1e-9 && t.sx(100) <= 190 + 1e-9);
  assert.ok(t.sy(0) > t.sy(50)); // world y up => larger world y is higher on screen (smaller sy)
});

test("scoreboard returns real veh-h and pct vs Fixed", () => {
  const sb = R.scoreboard(comparison, "FixedTime", "DQN");
  assert.ok(sb.right.key === "DQN" && sb.right.vehH > 0);
  assert.ok(Math.abs(sb.right.pctVsFixed - 30.8) < 1.0); // DQN -30.8% vs Fixed
  assert.ok(Math.abs(sb.left.pctVsFixed) < 1e-6);        // Fixed vs itself = 0
});

test("busiestSpot lands on real traffic, not the empty geometric centroid", () => {
  const rn = R.parseRoadnet(roadnet);
  const steps = R.parseReplay(replayTxt);
  const spot = R.busiestSpot(steps, { cell: 400, every: 10 });
  assert.ok(spot && spot.n > 0, "expected a busiest cell");

  // Count vehicles inside a 1200 m box around the busiest spot vs the same box
  // around the network's geometric centroid (the pre-fix zoom target).
  const cx = (rn.bounds.minX + rn.bounds.maxX) / 2;
  const cy = (rn.bounds.minY + rn.bounds.maxY) / 2;
  const half = 600;
  const countIn = (x0, y0) => {
    let n = 0;
    for (let i = 0; i < steps.length; i += 10)
      for (const c of steps[i].cars)
        if (Math.abs(c.x - x0) <= half && Math.abs(c.y - y0) <= half) n++;
    return n;
  };
  const atSpot = countIn(spot.x, spot.y), atCentroid = countIn(cx, cy);
  assert.ok(atSpot > atCentroid,
    "busiest view should hold more vehicles than the centroid view, got " +
    atSpot + " vs " + atCentroid);
});

test("busiestSpot is deterministic and breaks ties by lowest cell", () => {
  const mk = (pts) => [{ cars: pts.map(([x, y]) => ({ x, y })), tl: {} }];
  // two cells with one car each -> lowest (gx, gy) wins, repeatably
  const steps = mk([[10, 10], [810, 810]]);
  const a = R.busiestSpot(steps, { cell: 400, every: 1 });
  const b = R.busiestSpot(steps, { cell: 400, every: 1 });
  assert.deepStrictEqual(a, b);
  assert.strictEqual(a.x, 200);
  assert.strictEqual(a.y, 200);
  // a genuinely denser cell wins regardless of position
  const steps2 = mk([[10, 10], [810, 810], [820, 820], [830, 830]]);
  const c = R.busiestSpot(steps2, { cell: 400, every: 1 });
  assert.strictEqual(c.n, 3);
  assert.strictEqual(c.x, 1000);
  assert.strictEqual(R.busiestSpot([], {}), null);
});
