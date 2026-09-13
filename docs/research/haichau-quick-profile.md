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
valid. `configs/haichau_training_v3d_residual_quick.yaml` contains the quick
tier, while the canonical full protocol config is unchanged. Use
`scripts/train_haichau_residual.py --mode quick --config
configs/haichau_training_v3d_residual_quick.yaml`; it writes immutable
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

For a broader bounded comparison, combine full-hour campaigns from multiple
demand realizations with:

```bash
PYTHONPATH=src python3 scripts/summarize_haichau_short_campaign.py \
  results/haichau_network_v2/pilot-campaign-full6 \
  results/haichau_network_v2/pilot-campaign-full3 \
  --output results/haichau_network_v2/pilot-campaign-full9-summary.json
```

The completed 15-case seed-14 step-4 comparison reports a 6.12% aggregate
queue-hour reduction for residual DDQN versus fixed-time. Its paired bootstrap
95% interval is 0.90%--8.35%; normal demand is exactly tied by design, while
AM and PM peak means improve by 3.53% and 8.86%. The seed-12 step-8 run is
retained as a negative sensitivity result (0.78% aggregate, with a 5.67% AM
regression). These bounded results do not replace the five-seed release gate.

Generate the presentation chart with:

```bash
PYTHONPATH=src python3 scripts/plot_haichau_short_campaign.py \
  results/haichau_network_v2/pilot-campaign-full9-summary.json \
  --output results/haichau_network_v2/pilot-campaign-full9-improvement.png
```

The portable defense demo is built from the completed 15-case seed-14 replay
and includes one matched normal, AM-peak, and PM-peak case:

```bash
PYTHONPATH=src python3 scripts/build_haichau_bounded_demo.py
cd results/haichau_network_v2/demo-bounded
./launch_demo.command --no-browser
```

Open the printed loopback URL in a browser. The bundle is self-contained and
validated for 53 controlled signals; its aggregate label is explicitly marked
as bounded evidence pending the five-seed release gate.
