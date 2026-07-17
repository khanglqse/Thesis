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
