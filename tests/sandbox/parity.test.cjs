const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { Net, Encoder } = require("../../frontend/sandbox_core.js");

const MODEL = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../../frontend/sandbox_model.json"), "utf8"));

test("Net.forward reproduces exported parity q within 1e-3", () => {
  const net = new Net(MODEL.weights, MODEL.dims);
  for (const s of MODEL.parity) {
    const q = net.forward(Float32Array.from(s.obs));
    assert.strictEqual(q.length, s.q.length);
    for (let j = 0; j < q.length; j++) {
      assert.ok(Math.abs(q[j] - s.q[j]) < 1e-3, `q[${j}]=${q[j]} vs ${s.q[j]}`);
    }
    assert.strictEqual(net.maskedArgmax(q, MODEL.dims.n_actions), s.greedy);
  }
});

test("Encoder.encode reproduces exported encoder_parity obs within 1e-6 (guards count_norm + lane ordering)", () => {
  const enc = new Encoder(MODEL.dims, MODEL.intersection);
  enc.countNorm = MODEL.meta.count_norm;
  assert.ok(MODEL.encoder_parity && MODEL.encoder_parity.length > 0, "fixture missing encoder_parity");
  for (const s of MODEL.encoder_parity) {
    const obs = enc.encode(s.inCounts, s.outCounts, s.greenIdx);
    assert.strictEqual(obs.length, s.obs.length);
    for (let j = 0; j < obs.length; j++) {
      assert.ok(Math.abs(obs[j] - s.obs[j]) < 1e-6, `obs[${j}]=${obs[j]} vs ${s.obs[j]}`);
    }
  }
});
