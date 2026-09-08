# Hai Chau validation-only pressure diagnostic

Run this after the full-horizon fixed-time baseline cache finishes and before
committing to the expensive learned-policy campaign. It evaluates the corrected
production raw Max-Pressure and hysteretic Max-Pressure controllers on exactly
the six frozen validation cases, for 3,600 seconds each. Hysteresis uses the same
three-decision hold and 2.5-vehicle pressure margin as the final controller config.
There is no parameter search and no learner. It does not open test demand files
or simulate any train/test case.

From the repository root:

```sh
docker run --rm --platform linux/amd64 \
  -v "$PWD":/work -w /work traffic-rl-cityflow-research:v2 \
  python3 scripts/diagnose_haichau_pressure.py \
  --baseline-tuning-artifact results/haichau_network_v2/training/final-baseline-tuning.json \
  --output results/haichau_network_v2/diagnostics/pressure-validation-v1
```

`diagnostic.json` is updated after each of the 12 runs. The command refuses an
existing output directory. Interrupted or failed work remains
`diagnostic_partial`; only all 12 complete runs become `diagnostic_complete`.
Both statuses always carry `eligible_for_release: false` and
`eligible_for_test_evaluation: false`. A fresh directory is required for a rerun.
These outputs must not populate the final campaign or thesis results table.

The diagnostic reuses the training environment factory and the final campaign's
per-second metric observer. Queue is on-network waiting plus vehicles whose
entry is due but not inserted; future departures are excluded. Each row reports
both queue components, scheduled/due/unreleased/inserted/arrived/running/pending/
removed, completion rate, switching, maximum red, and matched regret against the
cached selected fixed-time baseline. Artifact checks bind the network, phase
contract, generator config and validation flow hashes. The output retains the
manifest/runtime/objective binding, code commit, resolved training-config hash,
controller settings and baseline artifact provenance.

Inspect each regime separately. Better pressure results with failed DDQN pilots
suggest an opportunity the learner has not captured. Poor results from both
pressure controllers are evidence to inspect demand, topology, transition costs
and saturation before assuming that more learning alone will solve the problem.
This is diagnostic reasoning from validation cases; final performance claims
still require the separate frozen held-out campaign.
