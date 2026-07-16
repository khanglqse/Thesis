# Live Policy Sandbox — real-time in-browser demo of the DQN controlling a signal

**Date:** 2026-07-15
**Status:** Design approved (single-node + scoreboard layout); pending spec review → implementation plan.
**Branch context:** `thesis/finalize-honest-empirical-study` (tight runway — build ONE focused artifact).

## 1. Problem

The current demo path (stock CityFlow PixiJS viewer + `frontend/demo-presets.js`) plays back
pre-computed replays of the full 53-intersection Hải Châu network. Even with auto-load, a HUD, and
a zoom-in, on that scale vehicles are ~1px dots and signals are tiny segments, so a viewer **cannot
see that the agent is controlling the lights**. The user wants a demo that *feels live* and makes
the agent's control obvious. Chosen direction (from brainstorming): a **live, real-time in-browser
sandbox** running the real trained policy on one intersection.

Enabling facts (verified in code):
- The DQN is a tiny from-scratch NumPy MLP: `obs → hidden → hidden → n_actions` (2 ReLU layers +
  linear head; `dueling=false` for the headline model). Weights saved as `.npz`
  (`SharedDQN.save`). Forward pass = 3 matmuls + ReLU + masked argmax → trivially portable to JS.
- The state (`state_mode=basic`) is **purely local**: incoming lane vehicle counts + outgoing lane
  vehicle counts + green-phase one-hot, each `/count_norm`, padded to global maxima
  (`ObservationEncoder`). No neighbor/global features in the headline model.
- The net is **parameter-shared** and only ever sees one intersection's padded local obs, so feeding
  a single real intersection's obs is exactly in-distribution → the agent's decisions are genuine.
- Headline model `haichau_rush`: `state_mode=basic`, `count_norm=5`, Fixed-Time green = 25s,
  `action_interval=10`, `min_green=10`, `yellow_time=3`. Weights at
  `results/haichau_rush/dqn_haichau_rush.npz`.
- `roadnet` lightphases carry `availableRoadLinks` → we know exactly which movements each green phase
  activates, so "which approach is green" is renderable from exported data.

## 2. Goals / Non-goals

**Goals**
- A single self-contained web page that runs the **real trained DQN weights live in the browser**
  (no Docker/CityFlow/container at demo time — immune to demo-day fragility).
- Make the control **obvious**: big top-down intersection, per-movement signal heads that change
  green/red as the agent switches phase, a decision flash + chosen-phase label + Q-value bars.
- A **live decision log** (scrolling event feed): one line per decision naming *which controller
  acted* and *what it did to the light* (kept vs switched phase, which movement got green, why), so
  the agent's control is legible as text as well as visually — and a mid-run controller toggle is
  visible in the log.
- **Interactive**: demand sliders per approach, controller toggle (DQN / Fixed-Time / Max-Pressure /
  Random), play/pause, speed, reset.
- **Quantify the benefit honestly**: a hidden Fixed-Time "shadow" runs on the *same* arrival stream;
  a live scoreboard shows cumulative waiting time DQN vs Fixed and %Δ.
- **Faithful & defensible**: the JS forward pass provably reproduces `SharedDQN.greedy_action`
  (parity test), and an on-screen note states the micro-model illustrates *policy behavior*, with the
  quantitative network results living in Chapter 4.

**Non-goals (this artifact)**
- Not the full 53-node network; not the real CityFlow micro-dynamics; not the source of thesis
  numbers. Those stay in the paper / existing replay demo.
- No twin side-by-side panels (deferred stretch; scoreboard covers the A/B need).
- No training, no server-side simulation, no new model.

## 3. Chosen approach

**Single hero intersection + live scoreboard** (user-selected over twin side-by-side): clearest for
*seeing the phase control*, least render work, and the shadow-Fixed scoreboard still delivers the A/B
"DQN helps" message. Twin panels are recorded as a future stretch goal.

## 4. Faithfulness contract (the crux)

The JS policy must be the *same function* as the trained net. Guaranteed by:
1. **Export from the same encoder the net trained with.** `export_sandbox_model.py` builds
   `ObservationEncoder(full_roadnet, count_norm, state_mode)` — identical to training — and dumps its
   global dims (`max_in`, `max_out`, `max_green`, `obs_dim`) plus, for the hero intersection, the
   *ordered* `incoming_lanes`, `outgoing_lanes`, `green_phases` (lightphase indices), `num_greens`,
   and the action mask. The JS encoder places the hero intersection's lanes into the same slots and
   zero-pads the rest — byte-for-byte the obs the net saw for that intersection in training.
2. **Export the exact weights.** Read the `.npz`; dump whichever param set is present
   (`W1,b1,W2,b2,W3,b3` for the headline non-dueling net; also support the dueling param set so other
   checkpoints work). `hidden` is inferred from `W1.shape[1]`.
3. **Mirror the forward pass.** JS computes `q = relu(relu(x·W1+b1)·W2+b2)·W3+b3` (or the dueling
   recombination `q = v + (adv - mean adv)`), masks invalid actions to `-1e9`, takes `argmax` — the
   exact logic of `SharedDQN._forward` + `greedy_action`.
4. **Parity test (must pass before we trust the demo).** The export also dumps N sample tuples
   `(obs, q_values, greedy_action)` computed by the real `SharedDQN` on random obs. A headless check
   (Node or a tiny Python re-impl mirroring the JS) asserts the JS/reference forward pass reproduces
   those `q_values` within tol (e.g. 1e-4) and the same `greedy_action`. This catches any
   encoder/matmul mismatch and lets us claim "this is the trained policy, live."

Known, disclosed abstraction: on an isolated intersection the outgoing lanes drain freely, so their
counts sit near zero (a valid uncongested-downstream state). The pressure signal the policy acts on
comes chiefly from incoming counts + green one-hot, so behavior stays representative.

## 5. Components & data flow

```
results/haichau_rush/dqn_haichau_rush.npz  ─┐
data/danang/roadnet_haichau_rush.json      ─┼─►  scripts/export_sandbox_model.py  ─►  frontend/sandbox_model.json
encoder constants (count_norm, state_mode) ─┘        (host Python 3.13, no container)
                                                                                          │
                                                              frontend/sandbox.html ◄─────┘ (fetch on load)
                                                              frontend/sandbox.js  (micro-model + encoder + net + render)
                                                              served by scripts/serve_replay.py (add sandbox URL print)
```

### 5.1 `scripts/export_sandbox_model.py` (host Python)
- Args: `--area haichau_rush` (default), `--ckpt <path>` (default the area's npz), `--inter <id>`
  (optional; if omitted, auto-pick per §8), `--out frontend/sandbox_model.json`,
  `--samples 32` (parity samples).
- Reads env hyperparams the same way training/eval do (env vars / `configs/training.yaml` /
  known per-scenario overrides — `haichau_rush`: `count_norm=5`, `state_mode=basic`). Records them.
- Emits `sandbox_model.json` per the schema in §6, including geometry needed to draw the approaches
  (intersection point, and for each incoming/outgoing road its direction/angle from the roadnet), the
  per-green-phase movement set (from `availableRoadLinks` → roadLinks → start/end road), weights, and
  parity samples.

### 5.2 `frontend/sandbox.js` (vanilla JS, Canvas 2D)
- **Model loader:** fetch `sandbox_model.json`; build the JS `Net` (matmul forward + masked argmax)
  and `Encoder` (basic-mode `encode(laneCounts, greenIdx)` reproducing `ObservationEncoder.encode`).
- **Micro-model:** per incoming lane a FIFO queue; Poisson arrivals at slider-controlled rate per
  approach; discharge at saturation flow (~1 veh / 2s per lane) for movements whose phase is green.
  `dt` sim-seconds per animation tick; decision every `action_interval=10s`; enforce `min_green=10s`
  and a `yellow_time=3s` all-red on a phase switch (mirrors `MultiAgentTrafficEnv.step`).
- **Controllers:** `DQN` (net), `FixedTime` (cycle green phases, 25s each), `MaxPressure` (argmax
  pressure from queue counts, computed in JS), `Random`.
- **Shadow scoreboard:** a second headless micro-model instance driven by the *same* arrival draws
  (single seeded PRNG feeds both) under Fixed-Time; accumulate cumulative waiting
  `Σ queued × dt` (veh-seconds → veh-hours, matching `eval/compare.py` convention) for the visible
  controller and the shadow; render totals + `%Δ vs Fixed`.
- **Render:** big intersection top-down; per approach a lane of car glyphs sized to be legible + a
  queue count; per-movement signal heads colored green/red by the active phase; a large "Pha đang
  xanh: …" label; on each decision, flash the intersection + show "DQN chọn pha X" and horizontal
  Q-value bars (highlight argmax); controller badge (RL vs baseline styling); the honesty note.
- **Interactions:** demand sliders (master + per-approach or N/S/E/W), controller `<select>`,
  play/pause, speed slider, reset. All text in Vietnamese to match `demo-presets.js`.

### 5.3 Live decision log
A scrolling panel beside the canvas that appends **one entry per decision tick** (every
`action_interval=10s`), driven by the same decision the controller just made:
- Content (Vietnamese): `[t=120s] DQN — đổi pha 2→0 · xanh cho hướng Bắc–Nam · (hàng chờ B=12 dài
  nhất) · Q₀=3.1`, or when unchanged `[t=130s] DQN — giữ pha 0 (đang xanh)`.
- Each line carries the **controller name + badge** (RL vs baseline styling), so toggling controller
  mid-run is obvious in the log; the "why" string is the argmax phase + its dominant queue/pressure
  and (for DQN) the winning Q-value.
- Behavior: newest on top (or auto-scroll to bottom), capped to the last ~200 lines, pause-on-hover
  so a viewer can read a line; a "clear" affordance. Implemented in `sandbox.js` (no new file).
- The same decision event drives the on-canvas flash/label, so log and animation never disagree.

### 5.4 Serving
- Extend `scripts/serve_replay.py` (or accept its existing static serving) to print the sandbox URL
  `http://localhost:<port>/frontend/sandbox.html`. No new server framework.

## 6. `sandbox_model.json` schema (contract)

```jsonc
{
  "meta": { "area": "haichau_rush", "intersection_id": "...", "state_mode": "basic",
            "count_norm": 5, "action_interval": 10, "min_green": 10, "yellow_time": 3,
            "fixed_green": 25, "dueling": false },
  "dims": { "max_in": <int>, "max_out": <int>, "max_green": <int>, "obs_dim": <int>,
            "hidden": <int>, "n_actions": <int> },
  "intersection": {
    "incoming_lanes": ["road_a_0", ...],      // ordered exactly as the encoder
    "outgoing_lanes": ["road_b_0", ...],
    "num_greens": <int>,
    "green_phases": [ { "phase_index": <int>,
                        "movements": [ { "from_road": "...", "to_road": "...",
                                         "in_lanes": [..], "out_lanes": [..],
                                         "turn": "go_straight|turn_left|turn_right" } ] } ],
    "geometry": { "center": [x, y],
                  "approaches": [ { "road": "...", "angle_deg": <n>, "role": "in|out",
                                    "lanes": ["road_0", ...] } ] }
  },
  "weights": { "W1": [[..]], "b1": [..], "W2": [[..]], "b2": [..], "W3": [[..]], "b3": [..] },
  // dueling checkpoints instead carry Wv,bv,Wa,ba
  "parity": [ { "obs": [..obs_dim..], "q": [..n_actions..], "greedy": <int> }, ... ]
}
```

## 7. Micro-model parameters (tunable, defaults)

- `dt = 1s` sim per tick; render loop uses `requestAnimationFrame` with a speed multiplier.
- Saturation discharge ≈ 0.5 veh/s per lane during green (i.e. one car every ~2s).
- Arrival rate per approach: slider 0–0.6 veh/s; defaults chosen so per-lane queues reach ~5–25 at
  high demand (normalized by `count_norm=5` → obs magnitudes ~1–5, matching the rush training range).
- Yellow/all-red = 3s; min-green = 10s; decision cadence = 10s.
- Basic-mode obs uses **all-vehicle** lane counts (queued + approaching); the micro-model tracks a
  per-lane occupancy (queue + a short approach zone) so incoming counts are non-trivial.

## 8. Hero-intersection selection

Auto-pick (or `--inter` override): among `roadnet_haichau_rush.json` signalized intersections, prefer
one with **4 incoming approaches** and **≥3 green phases** and roughly symmetric geometry (4-way),
so the agent has meaningful phase choices and the drawing is clean. The export script provides a
`--list` mode ranking candidates by (num_greens, num_incoming_approaches) to make the pick reviewable.

## 9. Honesty framing (thesis integrity)

- On-screen note (Vietnamese): the sandbox is an **illustrative micro-model running the real trained
  policy**; full quantitative results on the 53-node network are in Chapter 4 / the replay demo.
- The scoreboard is labeled as within-sandbox (same arrival stream), not a network-wide claim.
- No inflated wording; consistent with the repo's honest-empirical-study stance.

## 10. Testing / verification

1. **Parity test (blocking):** JS/reference forward pass reproduces the exported `parity` samples'
   `q` (tol 1e-4) and `greedy` action. Provide as a small Node script or a Python mirror asserting
   the same math. Without this, we do not claim "real policy."
2. **Export unit test:** `sandbox_model.json` validates against the §6 schema; lane ordering matches
   `ObservationEncoder` for the chosen intersection; `obs_dim == dims.obs_dim`.
3. **Behavioral smoke (manual):** under high demand, DQN visibly favors the longest-queue phase and
   the scoreboard shows DQN ≤ Fixed cumulative wait; Fixed-Time alone jams a surging approach.
4. **No-container check:** the page runs from `serve_replay.py` with only host Python + a browser.

## 11. Risks & mitigations

- *Off-distribution inputs from the toy dynamics* → keep obs magnitudes in the training range via
  `count_norm` and arrival tuning; disclose the abstraction. Parity test guarantees the *math*, not
  the input realism — that's acceptable for an illustrative demo.
- *Chosen intersection too simple (2-phase)* → selection criteria require ≥3 green phases.
- *Scope creep* → single node only; twin panels and full-network A/B replay (old "H2") are explicitly
  future work.

## 12. Out of scope / future

- Twin side-by-side (DQN | Fixed) sharing arrivals.
- Synchronized A/B replay player on the real 53-node network (the earlier "H2").
- 2×2 mini-grid sandbox (multi-agent), Max-Pressure/CoLight comparison beyond the JS toggle.

## 13. File summary

| File | New/changed | Purpose |
|---|---|---|
| `scripts/export_sandbox_model.py` | new (host Python) | npz + roadnet + config → `frontend/sandbox_model.json` (+parity samples, `--list`) |
| `frontend/sandbox.html` | new | self-contained demo page |
| `frontend/sandbox.js` | new | micro-model + encoder + net forward + render + interactions + scoreboard + live decision log |
| `frontend/sandbox.css` | new (or inline) | big, projector-legible styling |
| `frontend/sandbox_model.json` | generated | exported model+geometry (git-ignored or committed) |
| `scripts/serve_replay.py` | changed | print the sandbox URL |
| `tests/test_export_sandbox.py` | new | schema + parity + lane-ordering tests |
