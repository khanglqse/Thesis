# Hai Chau release status

This document records the current evidence boundary for the 53-signal Hai
Chau experiment. It is intentionally separate from the bounded presentation
result and must be updated before claiming a frozen release.

## Verified now

- The foundation verifier reports a 53-signal network, 30 declared cases, and
  a 9/6/15 train/validation/test split.
- The machine-readable audit at
  `results/haichau_network_v2/verification/gated-thesis-audit.json` confirms that
  the presentation bundle and exploratory gate pass their scoped checks, while
  preserving the strict verifier's failed-gate list separately.
- The bounded seed-14 step-4 evaluation covers all 15 test cases at a 3,600 s
  horizon. Schedule-residual DDQN reduces total queue-hours from 8,339.43 to
  7,829.25 (6.12%); the paired bootstrap 95% interval is 0.90%--8.35%.
- On the same cases, Max-Pressure reduces queue-hours by 23.89% and
  hysteretic Max-Pressure by 19.19%. These are stronger baselines and remain
  part of the claim boundary.
- Three completed learned seeds (12, 14 and 15) give aggregate reductions of
  0.78%, 6.12% and 0.44%; the mean seed-level reduction is 2.45%. The AM
  mean across these seeds is −1.32%, so seed variance is material.
- Normal operation is exactly tied to fixed-time by the residual controller's
  anchored policy. AM and PM improvements are 3.53% and 8.86% respectively,
  with individual-case regressions still present.
- The offline bundle in `results/haichau_network_v2/demo-bounded` validates as
  a 53-signal portable bundle and was served successfully over loopback.
- Secondary outcomes are now generated from the same matched seed-14 pairs:
  completion +1.06 percentage points, insertion +0.82 points, mean maximum
  node queue −16.93 vehicles, completed-trip travel time +5.45 seconds, and
  spillback +65.20 lane-seconds. They are descriptive and stored in
  `results/haichau_network_v2/final15-seed14-secondary-summary.json`.
- The thesis PDF and defense Q&A now distinguish bounded evidence from the
  pending strict release. The short launch and preflight procedure is in
  `docs/defense/haichau-bounded-demo.md`.
- A regime-gated exploratory composition over the three completed seeds keeps
  tuned fixed-time in normal and AM-peak cases and enables the residual policy
  only in PM peak. Across 45 matched case rows it reduces queue-hours by
  2.83%; the three seed-level reductions are 2.36%, 5.11%, and 1.03%. The
  source-bound summary is
  `results/haichau_network_v2/final15-regime-gated-summary.json`. This result
  diagnoses a practical demand gate; it is not a fresh strict campaign and
  still needs direct simulator confirmation before a confirmatory claim.
- A direct fresh replay of that gate for seed 14 covers all 15 test cases and
  reproduces the composed result: 8,339.43 to 7,913.46 vehicle-hours, a 5.11%
  reduction. Normal and AM are exact fixed-time ties; PM improves 10.39% in
  aggregate. The compact, hash-bound rows are in
  `results/haichau_network_v2/final15-regime-gated-seed14-direct-summary.json`.
  It remains exploratory because the gate is outside the frozen five-seed
  release protocol.
- The same PM-only replay for seed 13 covers all five PM test cases: 4,100.74
  to 3,631.89 vehicle-hours, an 11.43% aggregate reduction. One case regresses
  by 1.76%, so the result is reported as an aggregate with case-level variation;
  rows are in `results/haichau_network_v2/final15-regime-gated-seed13-pm-direct-summary.json`.
- A second independent PM-only replay for seed 16 covers the same five cases:
  4,100.74 to 3,827.77 vehicle-hours, a 6.66% aggregate reduction. Two cases
  regress, so this is also exploratory evidence with case-level variation; rows
  are in `results/haichau_network_v2/final15-regime-gated-seed16-pm-direct-summary.json`.
- Across the three direct PM gate replays (seeds 13, 14, and 16), the derived
  full-day aggregate reductions are 5.62%, 5.11%, and 3.27% (mean 4.67%).
  These runs strengthen the presentation claim that the gate improves the
  fixed-time aggregate on this network, while remaining outside the frozen
  five-seed confirmatory protocol.
- Fresh full-day gate replays for seeds 12 and 15 cover all 15 held-out cases,
  reducing 8,339.43 vehicle-hours to 8,142.43 (2.36%) and 8,253.86 (1.03%).
  Normal and AM are exact fixed-time ties; the fresh PM reductions are 4.80%
  and 2.09%, with case-level regressions. The compact rows are in
  `results/haichau_network_v2/final15-regime-gated-seed12-direct-summary.json`
  and `results/haichau_network_v2/final15-regime-gated-seed15-direct-summary.json`.
- Combining all five seed-level gate summaries gives derived full-day reductions
  of 2.36%, 5.62%, 5.11%, 1.03%, and 3.27% (mean 3.48%). All five seeds now
  have fresh 15-case coverage: seeds 12, 14, and 15 use direct full-day gate
  campaigns, while seeds 13 and 16 combine fresh fixed normal/AM replays with
  fresh PM gate replays. The complete provenance table is
  `results/haichau_network_v2/final15-regime-gated-direct-multi-seed-summary.json`.
  At the case level, the gate regresses 3/15 cases for seed 12, 1/15 for seed 13,
  1/15 for seed 14, 3/15 for seed 15, and 2/15 for seed 16; aggregate gains
  therefore do not imply improvement for every demand realization.
- A short safety-margin sensitivity run with seed 13, one test case per regime,
  and a 900 s horizon compares residual score margins 0 and 5. Margin 5 exactly
  falls back to fixed-time in all three cases; margin 0 changes the queue by only
  0.019% in AM and 0.011% in PM, with an AM completion gain of 0.34 percentage
  points and a PM loss of 0.10 points. This exploratory parameter evidence is
  recorded in `results/haichau_network_v2/quick-safety-margin-seed13-summary.json`;
  it does not replace the full frozen campaign.

## Still required for a frozen confirmatory release

The strict verifier is not complete. It still requires a frozen protocol and
runtime attestation, five selected confirmatory learning seeds (12--16), fresh
matched release runs, hierarchical seed-level statistics, acceptance evidence,
hash-derived thesis artifacts, an offline-demo release manifest, and a clean
checkout record. Seeds 13 and 16 currently have no eligible checkpoint under
the preregistered selector; their rejection is evidence and must not be hidden
by relabelling a bounded run as final.

The seed-14 and seed-12 full 15-case runs are therefore useful results for the
thesis and defense, but they are not evidence that all five confirmatory seeds
have passed.
