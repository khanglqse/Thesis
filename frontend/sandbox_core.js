// Pure logic for the sandbox demo: portable Net + Encoder (basic state).
// Loads in the browser (window.SandboxCore) and in Node (module.exports) so the
// exact same code path is unit-tested against the trained net's parity samples.
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SandboxCore = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function linear(x, W, b) {          // x:[in], W:[in][out], b:[out] -> [out]
    const out = b.slice();
    for (let i = 0; i < x.length; i++) {
      const xi = x[i];
      if (xi === 0) continue;
      const Wi = W[i];
      for (let j = 0; j < out.length; j++) out[j] += xi * Wi[j];
    }
    return out;
  }
  function reluInPlace(a) { for (let j = 0; j < a.length; j++) if (a[j] < 0) a[j] = 0; return a; }

  class Net {
    constructor(weights, dims) { this.w = weights; this.dims = dims; }
    forward(x) {
      const w = this.w;
      const a1 = reluInPlace(linear(x, w.W1, w.b1));
      const a2 = reluInPlace(linear(a1, w.W2, w.b2));
      let q;
      if (w.Wv) {                     // dueling recombination
        const v = linear(a2, w.Wv, w.bv);
        const adv = linear(a2, w.Wa, w.ba);
        let mean = 0; for (let j = 0; j < adv.length; j++) mean += adv[j]; mean /= adv.length;
        q = adv.map((a) => v[0] + (a - mean));
      } else {
        q = linear(a2, w.W3, w.b3);
      }
      return Float64Array.from(q);
    }
    maskedArgmax(q, numValid) {
      let best = -1, bestV = -Infinity;
      for (let j = 0; j < numValid; j++) if (q[j] > bestV) { bestV = q[j]; best = j; }
      return best;
    }
  }

  class Encoder {
    constructor(dims, intersection) {
      this.maxIn = dims.max_in; this.maxOut = dims.max_out;
      this.obsDim = dims.obs_dim; this.numGreens = intersection.num_greens;
      this.incoming = intersection.incoming_lanes;
      this.outgoing = intersection.outgoing_lanes;
      this.countNorm = null;          // set by caller from meta.count_norm
    }
    encode(inCounts, outCounts, greenIdx) {
      const v = new Float64Array(this.obsDim);
      const cn = this.countNorm;
      for (let k = 0; k < this.incoming.length; k++) v[k] = (inCounts[this.incoming[k]] || 0) / cn;
      for (let k = 0; k < this.outgoing.length; k++) v[this.maxIn + k] = (outCounts[this.outgoing[k]] || 0) / cn;
      if (greenIdx >= 0 && greenIdx < this.numGreens) v[this.maxIn + this.maxOut + greenIdx] = 1.0;
      return v;
    }
  }

  return { Net, Encoder };
});
