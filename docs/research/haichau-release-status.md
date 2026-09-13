# Hai Chau release status

This document records the current evidence boundary for the 53-signal Hai
Chau experiment. It is intentionally separate from the bounded presentation
result and must be updated before claiming a frozen release.

## Verified now

- The foundation verifier reports a 53-signal network, 30 declared cases, and
  a 9/6/15 train/validation/test split.
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
