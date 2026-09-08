# Demand-scenario regimes — load-based framing (why `rush` is the headline)

> **ARCHIVED LEGACY RESULTS — NOT V2 THESIS EVIDENCE.** All demand regimes and performance
> values here belong to the earlier synthetic CityFlow protocol. They are retained for audit,
> not as observed/calibrated Hai Chau traffic or a current thesis result.

**Purpose.** Resolve the "Hải Châu peak" question: the honest way to present the four
scenarios is a *legacy synthetic saturation spectrum*, not a cherry-pick. `haichau_rush` (~50k
scheduled trips) is a loaded simulator regime
where RL beats Fixed-Time, whereas the dense `haichau` baseline is grossly oversaturated and
RL degrades there. Both are kept and reported.

## The four regimes on two measured, controller-independent load axes

Load axes are measured **under tuned Fixed-Time** (a deterministic replay), so they describe
the *demand*, not the learned policy. `Concurrent` = vehicles simultaneously in the network
at horizon end (`final_vehicle_count`); `Peak queue` = max of the per-decision total-queue
series (`max(queue_series)`); `% stopped` = peak queue / concurrent (approx. saturation).

| Scenario        | Trips injected | Concurrent | Peak queue | % stopped | Regime |
|-----------------|---------------:|-----------:|-----------:|----------:|--------|
| `haichau_rush`  |         50,500 |      2,900 |      1,210 |       42% | legacy synthetic load |
| `haichau_calib` |         75,500 |      4,680 |      2,370 |       51% | moderately heavy |
| `haichau`       |      1,200,500 |     11,370 |      7,340 |       65% | grossly oversaturated (stress limit) |
| `haichau_peak`  |        310,900 |     12,570 |      8,530 |       68% | oversaturated surge |

Trip counts are exact (`scripts` count of `data/danang/flow_<scen>.json`). Load axes from
`results/<scen>/comparison.json` (FixedTime row). Note the load ordering is by *saturation*,
not by raw trips: `haichau_peak` (311k trips, concentrated surge) is more saturated than the
raw `haichau` baseline (1.2M trips spread over the horizon).

## Why `rush` = the fix, not a cherry-pick

- 50,500 scheduled trips (with documented endpoint ambiguity) and ~2,900 concurrent with ~1,210 queued (42%) form a
  **loaded but not gridlocked** network — queues form, so signal timing has leverage, but a
  good policy can still clear them. That is the operating point where adaptive control wins.
- This demonstrates simulated queuing rather than free flow. It does not establish a real or
  calibrated peak for Hai Chau.

## RL performance across the spectrum (multi-seed, post horizon-fix)

Headline metric = cumulative waiting time (veh-hours), % = reduction vs tuned Fixed-Time.
Multi-seed (K=5) means from the re-run with the checkpoint horizon-bug fix
(`_greedy_eval` selects on the report horizon). **FINAL — all 5/5, folded into Chapter 4 (2026-07-15).**

| Scenario        | DQN vs Fixed-Time (wait-hours) | seeds | status |
|-----------------|-------------------------------:|:-----:|--------|
| `haichau_rush`  | **+37.1% ± 3.9 veh-h**          | 5/5   | FINAL — headline (vs MP −5.0%) |
| `haichau_calib` | **+21.6% ± 28.9 veh-h**         | 5/5   | FINAL |
| `haichau_peak`  | **+5.1% ± 35.3 veh-h**          | 5/5   | FINAL |
| `haichau`       | **−39.9% ± 12.4 veh-h**         | 5/5   | FINAL — worse than Random |

> **CI note (2026-07-22):** CIs above use the corrected Student-t formula (df=4, sample std) — see
> `docs/thesis_improvement_review.md` §A1. As a *reduction %* vs Fixed-Time the intervals are rush
> +37.1% [34.9, 39.2], calib +21.6% [13.1, 30.1], peak +5.1% [2.2, 8.1], dense −39.9% [−41.3, −38.5]
> — **all four keep their sign** (none crosses 0). The pre-2026-07-22 CIs (±2.5/±18.3/±22.3/±7.9) used
> a too-narrow normal-approx (z=1.96, ddof=0) and are superseded.

**The legacy spectrum:** the control gap is largest in `rush`, shrinks as the
network saturates (`calib` → `peak`), and **reverses to a loss under gross oversaturation**
(`haichau`, −39.9%). This is the honest story: a purely *local* value-based controller helps
when queues form but can still be cleared, and degrades when no local policy can drain a
gridlocked network. We report the dense failure rather than hide it.

## Demo vs results (two different "vehicle numbers")

- **Legacy results only** use `rush` (50k scheduled trips, ~2,900 concurrent). These values do
  not enter the current v2 thesis conclusion.
- **Visual demo** uses `danang_peak` (`data/danang/flow_danang_peak.json`, ~70% motorbike,
  saturated-window clip ~6,900 on screen) for a *busy-looking* projection. See
  [danang_peak_demo_scenario.md](danang_peak_demo_scenario.md). Do not conflate the demo's
  on-screen count with the results demand.

## Chapter 4 wiring

- `paper/chapter4_experiments_results.tex` → Demand Scenarios subsection now leads with
  Table `tab:scenarios` (this two-axis load table) and names `rush` the headline realistic
  peak, `haichau`/`peak` the oversaturated stress regimes.
- **DONE (2026-07-15):** `tab:waiting` + `tab:queue` rewritten with multi-seed CI (honest dense
  −39.9%); saturation-spectrum + oversaturation-degradation analysis added to `sec:analysis` /
  `sec:limits`; headline **+37.1%** propagated to Abstract/Contribution/Conclusion + Ch4 prose;
  `fig:training` switched to rush (queue −45.5%); 4 `methods_*.png` regenerated with CI error bars
  (`scripts/regen_methods_multiseed.py`). Tooling: `scripts/emit_ch4_tables.py` (stale-guard).
- **Ablation DONE (option A, 2026-07-15):** `tab:ablation` re-pointed off dense to rush+peak.
  Dueling resolved ×5 (416.8±31.7 Student-t; mean well above MP 388.2, CI reaches MP only at lower
  tail → "no variant beats MP" holds — mean is clearly worse); warm-start
  regime-scoped (hurts only under oversaturation); ATS-not-robust (0.6% < CI); pressure-at-rush
  dropped (rs mis-scale). Full record: `docs/ablation_honest_plan.md`.
