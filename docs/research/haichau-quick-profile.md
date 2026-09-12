# Hai Chau quick profile

The repository now has a deliberately small profile for iteration and the
presentation demo. It uses the same 53-signal Hai Chau network, pinned CityFlow
image, feature contract, and reward definition as the research pipeline, but
limits computation as follows:

| Part | Full protocol | Quick profile |
| --- | ---: | ---: |
| training episodes per seed | 12 × 3600 s | 1 × 300 s |
| training peak cases | all declared peak cases | one AM + one PM case |
| validation cases | 6 | 3 (normal, AM, PM) |
| test cases | 15 | 3 (one per regime) |
| test controllers | release cohort | fixed, max-pressure, residual DDQN |
| learning seeds | 5 | 3 (12, 13, 14) |

The simulator requires a 300-second macro block, so shorter horizons are not
valid. `scripts/train_haichau_residual.py --mode quick` writes immutable
per-seed artifacts under `results/haichau_network_v2/training/quick300-seedN/`.
The comparison runner is:

```bash
PYTHONPATH=src python3 scripts/run_haichau_quick_campaign.py
```

Its output is `results/haichau_network_v2/quick-campaign/campaign-summary.json`.
The runner truncates each demand stream at 300 seconds, records the resulting
vehicle count and hash, and runs at most two Docker jobs concurrently. The
result is suitable for smoke checks, parameter iteration, and a short demo;
the frozen 15-case full-hour campaign remains the thesis evidence protocol.
