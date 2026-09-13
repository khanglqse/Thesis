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
