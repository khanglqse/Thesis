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

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const SAT_PER_LANE = 0.5;      // veh/s discharged per lane on green
  const OUT_DECAY = 0.3;         // fraction/s outgoing occupancy drains downstream

  class MicroModel {
    constructor(intersection, meta, rng) {
      this.it = intersection; this.meta = meta; this.rng = rng;
      this.t = 0; this.greenIdx = 0; this.sinceSwitch = 0; this.yellowLeft = 0;
      this.inCounts = {}; this.outCounts = {};
      for (const l of intersection.incoming_lanes) this.inCounts[l] = 0;
      for (const l of intersection.outgoing_lanes) this.outCounts[l] = 0;
      // road -> its incoming lane ids (for spreading arrivals)
      this._inLanesByRoad = {};
      for (const ap of intersection.geometry.approaches)
        if (ap.role === "in") this._inLanesByRoad[ap.road] = ap.lanes;
    }
    arrivals(dt, ratePerApproach) {
      for (const road in this._inLanesByRoad) {
        const lanes = this._inLanesByRoad[road];
        const lam = (ratePerApproach[road] || 0) * dt;
        // expected lam arrivals spread across the road's lanes; Bernoulli per unit
        let n = 0; for (let k = 0; k < Math.ceil(lam) + 2; k++) if (this.rng() < lam / (Math.ceil(lam) + 2)) n++;
        for (let i = 0; i < n; i++) this.inCounts[lanes[i % lanes.length]] += 1;
      }
    }
    dischargeAndDecay(dt) {
      if (this.yellowLeft > 0) { this.yellowLeft = Math.max(0, this.yellowLeft - dt); }
      else {
        const ph = this.it.green_phases[this.greenIdx];
        const outFor = {};                       // unique in-lane -> representative out-lane
        for (const mv of ph.movements) {
          for (const il of mv.in_lanes) {
            if (!(il in outFor)) outFor[il] = (mv.out_lanes[0] != null ? mv.out_lanes[0] : null);
          }
        }
        for (const il in outFor) {
          const move = Math.min(this.inCounts[il], SAT_PER_LANE * dt);
          this.inCounts[il] -= move;
          const ol = outFor[il];
          if (ol != null) this.outCounts[ol] += move;
        }
      }
      for (const ol in this.outCounts) this.outCounts[ol] = Math.max(0, this.outCounts[ol] * (1 - OUT_DECAY * dt));
      this.t += dt; this.sinceSwitch += dt;
    }
    laneCountsIn() { return this.inCounts; }
    laneCountsOut() { return this.outCounts; }
    totalQueue() { let s = 0; for (const l in this.inCounts) s += this.inCounts[l]; return s; }
    applyChoice(choice) {
      const old = this.greenIdx;
      if (choice === old || choice < 0 || choice >= this.it.num_greens
          || this.sinceSwitch < this.meta.min_green) {
        return { changed: false, oldPhase: old, newPhase: old, yellow: 0 };
      }
      this.greenIdx = choice; this.sinceSwitch = 0; this.yellowLeft = this.meta.yellow_time;
      return { changed: true, oldPhase: old, newPhase: choice, yellow: this.meta.yellow_time };
    }
  }

  return { Net, Encoder, MicroModel, mulberry32, SAT_PER_LANE };
});
