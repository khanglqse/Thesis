const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../../frontend/haichau_network_demo_core.js");

test("node color changes monotonically from low to high queue", () => {
  assert.notEqual(core.queueColor(0, 50), core.queueColor(25, 50));
  assert.notEqual(core.queueColor(25, 50), core.queueColor(50, 50));
  assert.equal(core.queueColor(-2, 50), core.queueColor(0, 50));
  assert.equal(core.queueColor(500, 50), core.queueColor(50, 50));
});

test("frame lookup is synchronized at requested time", () => {
  const frames = [{ t: 5 }, { t: 10 }, { t: 15 }];
  assert.equal(core.frameIndexAt(frames, 4), 0);
  assert.equal(core.frameIndexAt(frames, 9), 0);
  assert.equal(core.frameIndexAt(frames, 10), 1);
  assert.equal(core.frameIndexAt(frames, 99), 2);
});

test("network transform fits coordinates and nearest node selection", () => {
  const tx = core.networkTransform([
    { id: "A", x: 0, y: 0, neighbors: [] },
    { id: "B", x: 100, y: 50, neighbors: [] },
  ], 220, 120, 10);
  assert.equal(tx.x(0), 10);
  assert.equal(tx.y(0), 110);
  assert.equal(tx.x(100), 210);
  assert.equal(tx.y(50), 10);
  assert.equal(core.nearestNode([{ id: "A", x: 0, y: 0 }], 2, 1, 5).id, "A");
  assert.equal(core.nearestNode([{ id: "A", x: 0, y: 0 }], 20, 20, 5), null);
});

test("viewer rejects invalid geometry and unknown neighbors", () => {
  const valid = [
    { id: "A", x: 0, y: 0, neighbors: ["B"] },
    { id: "B", x: 1, y: 1, neighbors: [] },
  ];
  assert.equal(core.validateNetwork(valid), true);
  assert.throws(() => core.validateNetwork([
    { id: "A", x: Number.NaN, y: 0, neighbors: [] },
  ]), /finite coordinates/);
  assert.throws(() => core.validateNetwork([
    { id: "A", x: 0, y: 0, neighbors: ["missing"] },
  ]), /unknown neighbor/);
});

test("paired replay selection requires one matched case", () => {
  const entries = [
    { controller_id: "tuned_fixed", case_id: "c1", path: "a.json" },
    { controller_id: "neighbor_phase_ddqn", case_id: "c1", path: "b.json" },
  ];
  assert.deepEqual(core.pairedReplays(entries), { fixed: entries[0], learned: entries[1] });
  assert.throws(() => core.pairedReplays([
    entries[0], { ...entries[1], case_id: "c2" },
  ]), /matched case/);
});

test("provenance rows use only supplied evidence and mark missing fields N/A", () => {
  const supplied = core.provenanceRows({
    run_id: "run-12", case_id: "test-normal-101",
    controller_id: "neighbor_phase_ddqn", learning_seed: 12,
    checkpoint_sha256: "checkpoint-digest",
    checkpoint_contract_sha256: "contract-digest",
    metrics: { pending: 7, pending_integral_vehicle_seconds: 42.5 },
  }, { accepted: true });
  assert.deepEqual(supplied, {
    run_id: "run-12", case_id: "test-normal-101",
    controller: "neighbor_phase_ddqn", checkpoint: "checkpoint-digest",
    checkpoint_contract: "contract-digest", learning_seed: "12",
    terminal_pending: "7", pending_integral: "42.5",
    acceptance: "Accepted",
  });

  const absent = core.provenanceRows({ metrics: {} }, {});
  assert.deepEqual(absent, {
    run_id: "N/A", case_id: "N/A", controller: "N/A", checkpoint: "N/A",
    checkpoint_contract: "N/A", learning_seed: "N/A", terminal_pending: "N/A",
    pending_integral: "N/A", acceptance: "N/A",
  });
});
