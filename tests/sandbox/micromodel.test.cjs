const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { MicroModel, mulberry32 } = require("../../frontend/sandbox_core.js");

const MODEL = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../../frontend/sandbox_model.json"), "utf8"));

function fresh() { return new MicroModel(MODEL.intersection, MODEL.meta, mulberry32(7)); }

test("arrivals raise incoming lane counts", () => {
  const m = fresh();
  const rate = {};
  for (const ap of MODEL.intersection.geometry.approaches)
    if (ap.role === "in") rate[ap.road] = 0.5;
  for (let i = 0; i < 50; i++) m.arrivals(1.0, rate);
  assert.ok(m.totalQueue() > 0);
});

test("min_green blocks an immediate switch", () => {
  const m = fresh();
  const other = (m.greenIdx + 1) % MODEL.intersection.num_greens;
  const r = m.applyChoice(other);      // sinceSwitch=0 < min_green -> blocked
  assert.strictEqual(r.changed, false);
  assert.strictEqual(m.greenIdx, 0);
});

test("switch allowed after min_green, marks yellow", () => {
  const m = fresh();
  m.sinceSwitch = MODEL.meta.min_green;  // eligible
  const other = (m.greenIdx + 1) % MODEL.intersection.num_greens;
  const r = m.applyChoice(other);
  assert.strictEqual(r.changed, true);
  assert.strictEqual(r.newPhase, other);
  assert.ok(r.yellow >= MODEL.meta.yellow_time);
});

test("green discharges the served incoming lanes", () => {
  const m = fresh();
  const ph = MODEL.intersection.green_phases[m.greenIdx];
  for (const mv of ph.movements) for (const il of mv.in_lanes) m.inCounts[il] = 10;
  const before = m.totalQueue();
  for (let i = 0; i < 5; i++) m.dischargeAndDecay(1.0);
  assert.ok(m.totalQueue() < before);
});
