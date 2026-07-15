# Honest ablation re-point (option A) — CI-triaged, minimal compute

**Context.** `tab:ablation`'s "Normal" (=dense) rows used the buggy checkpoint selection
(greedy-eval at the *training* horizon 800, reported at 1000). The honest multi-seed dense
result is DQN −39.9% (loses to Fixed), so the old "+6.5% best-learned on Normal" ranking is an
artifact. Option A = re-point the ablation to a realistic regime and re-run honestly. This doc
records the CI-triage that keeps the re-run **minimal** and the conclusion **stronger**.

## Why not just re-run the whole variant sweep

On the realistic regimes the DQN queue seed-CI **swamps** the variant differences the old
ablation ranked on:

| Regime | DQN queue (multi-seed) | CI95 | CI as % |
|--------|-----------------------:|-----:|--------:|
| rush   | 428.2 | ±29.4 | **±6.9%** |
| calib  | 978.4 | ±69.8 | **±7.1%** |
| peak   | 4079.4 | ±116.8 | ±2.9% |
| dense  | 4593.6 | ±28.3 | ±0.6% |

The old variant ranking spanned **~2.0%** (dense NORMAL: 3838.9–3916.9). On rush/calib that
2% sits **entirely inside** the ~7% seed CI. Re-running pressure/queue_norm/dueling single-seed
to re-rank them would re-manufacture a fragile, examiner-pokeable claim — the exact failure the
whole multi-seed effort exists to kill.

## CI-triage — which claims survive seed noise

1. **"No learned variant beats Max-Pressure"** — SURVIVES on every regime. Favorable-CI edge:
   rush 398.8 > MP 388.2; calib 908.6 > 843.1; peak 3962.6 > 3758.3. This is the headline
   ablation claim and it is robust. *(supported by multi-seed main configs — no new runs)*
2. **Reward/architecture ranking (queue_norm > pressure > dueling)** — DOES NOT survive
   (2% spread ≪ 7% CI). **Drop the ranking.** Reframe: "reward and architecture move queue by
   only a few percent, within seed variability; no single learned variant is statistically
   separable, so we report the best per regime (Table `tab:dqncfg`) without over-interpreting
   the order." *(no new runs)*
3. **"Max-Pressure warm-start + n-step degrades below Fixed-Time"** — SURVIVES (a sign-flip:
   normal DQN +5% vs Fixed → warm-start −1.3…−3.4% vs Fixed, far outside CI). Catastrophic
   forgetting. **1 honest run** on the realistic regime to reconfirm under the fixed protocol.
4. **"ATS approaching-demand state helps under congestion, hurts under light demand"** —
   BORDERLINE (peak basic 4085.2 vs ATS 3926.6 = 3.9% vs peak CI 2.9%). Keep the claim **only**
   if the honest basic-vs-ATS gap on the congested regime exceeds CI. **≤1 run** (basic-on-peak;
   ATS-on-peak already in the multi-seed re-run) — and only if honest peak DQN beats Fixed.

## Minimal compute plan (after the multi-seed re-run finishes)

Gate on the honest re-run so regime choice is data-driven (peak may behave like dense).

- **rush** (headline realistic peak) = the ablation's primary regime. Main config `queue_norm`
  comes from the multi-seed re-run WITH CI. Add **warm-start+n-step on rush** (1 run) for the
  negative result.
- **congested regime** (peak if it honestly beats Fixed, else calib): main config from
  multi-seed; add **basic (pressure) on that regime** (1 run) to test ATS-vs-basic honestly.
- Total: **~2 runs**, single-seed is acceptable for the two *sign-flip / directional* claims
  (both are large-effect, outside CI). Reuse everything else from the multi-seed aggregates.

Runner: `scripts/exp_ablation_honest.sh <area>` (regime-agnostic; sets `EVAL_EVERY` so the
fixed report-horizon greedy-eval checkpoint selection is used; writes `results/<area>/exp_<tag>/`;
resumable — skips existing `comparison.json`). Do NOT run in parallel with the multi-seed
re-run (same CityFlow container, x86 emulation — contention on the critical path).

## New ablation table shape (`tab:ablation`)

Rows per featured regime: Fixed-Time, Max-Pressure, DQN main-config (**with ±CI95**), plus the
two surviving qualitative results (warm-start negative; ATS-vs-basic under congestion). Caption
states the ranking among learned variants is within seed variation. Findings prose (`sec:analysis`)
updates to: *no learned variant is statistically distinguishable and none beats Max-Pressure;
the only directional signals are ATS-under-congestion (small) and warm-start-hurts (negative).*

---

## FINAL DRAFT (post-run 2026-07-15) — honest ablation on rush + peak, dueling-gated

Single-seed variant runs (`results/<scen>/exp_abl_*`) + multi-seed main configs
(`results/multiseed/*`). Metric = mean total queue (lower better). **HOLD insertion into
`tab:ablation` until dueling ×5 lands** (it gates the "beats Max-Pressure" wording).

### Measured numbers (queue)
Rush — Fixed 647.6, Max-Pressure 388.2:
- DQN `queue_norm` (MAIN, 5-seed): **407.7 ± 8.8**  (vs Fixed +37.1%, vs MP −5.0%)
- DQN `dueling` (5-seed [378.6, 420.3, 449.8, 412.9, 422.4]): **416.8 ± 20.0**  (vs Fixed +35.6%, vs MP −7.4%)
  → **RESOLVED: mean−CI95 = 396.8 > MP 388.2 → the 378.6 was a lucky seed; "no variant beats MP" HOLDS (bulletproof).**
  Dueling (416.8±20.0) ≈ queue_norm (407.7±8.8): overlapping CIs, statistically indistinguishable (dueling slightly worse).
  Applied: kept Abstract/Conclusion "does not beat MP"; tab:ablation + findings rewritten on rush+peak (DONE).
- DQN warm-start+n-step: 430.7  (vs Fixed +33.5%, vs MP −10.9%)  ← did NOT hurt at realistic peak
- DQN `pressure` reward: 827.6  ← DROP: rs=0.5 was tuned for queue_norm, mis-scales pressure (artifact, not a reward finding)

Peak — Fixed 4314.0, Max-Pressure 3758.3:
- DQN `ats`+`efficient_pressure` (MAIN, 5-seed): **4093.8 ± 80.3**  (vs Fixed +5.1%, vs MP −8.9%)
- DQN basic (pressure+basic): 4118.5  (vs Fixed +4.5%, vs MP −9.6%)  → ATS vs basic = 0.6%, WITHIN CI

### Decision rule for dueling (queue, MP = 388.2)
- dueling `mean + CI95 < 388.2`  → **genuinely beats MP** at realistic peak. Soften ceiling
  narrative to "a dueling head edges past Max-Pressure at realistic peak; larger margins need
  coordination." Update Abstract/Contribution/Conclusion "does not beat" → "matches/edges past".
- dueling `mean − CI95 > 388.2`  → 378.6 was a lucky seed; "no variant beats MP" **holds and is
  now bulletproof** (keep abstract wording).
- CI straddles 388.2  → "approaches but does **not significantly** beat MP" (soften "never").

### Three text fixes (dueling-independent) to bake into findings + `tab:ablation`
1. **Reward** — do NOT present pressure-on-rush (827.6) as "pressure reward is bad": it is a
   reward-scale × reward-type interaction artifact (rs=0.5 tuned for queue_norm). State reward
   choice is coupled to its scale; on the honest regimes queue_norm is the working reward.
2. **Warm-start** — regime-scope: "Max-Pressure warm-start + n-step degraded **below Fixed-Time
   under oversaturation** (dense/peak), but **not at the realistic peak** (rush: +33.5% vs Fixed).
   The clone is eroded by naive fine-tuning only when the reward signal is itself unstable
   (saturated queues)." More nuanced and true.
3. **ATS state** — soften Claim 4: "adding the incoming running-vehicle channel did **not
   significantly change** queue at peak (4093.8 vs 4118.5, within seed CI); the approaching-demand
   signal did not yield a robust gain on this network." Replace the stale −8.7%→−4.5% (buggy
   single-seed) numbers.

### New `tab:ablation` shape
Two regime blocks (rush headline, peak congested). Each: Fixed-Time, Max-Pressure, DQN main
(±CI95), + the surviving variants (dueling ±CI95 once resolved; warm-start). Caption: learned
variants are reported single-seed except the main config and dueling (5 seeds); differences among
learned variants at realistic peak are within seed variation. Findings prose updated per the
three fixes above + the dueling branch.
