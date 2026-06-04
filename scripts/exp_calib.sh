#!/bin/sh
# Calibrated-demand scenario (haichau_calib, ~6% of the unrealistic original =
# realistic congested regime where signal control has real leverage). Train the
# DQN and run the full comparison so we can measure the true improvement %.
set -e
pip install dataclasses numpy pyyaml matplotlib >/dev/null 2>&1

# DQN: queue_norm reward (best on normal), count_norm=10 (queues are much smaller
# at this demand than in the oversaturated original, so rescale the observation).
echo "===== TRAIN DQN on haichau_calib ====="
REWARD_TYPE=queue_norm COUNT_NORM=10 PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib

echo "===== COMPARE all controllers on haichau_calib ====="
FIXED_GREEN=25 COUNT_NORM=10 MAX_STEPS=1000 PYTHONPATH=src python3 scripts/run_comparison.py haichau_calib
echo "CALIB_DONE"
