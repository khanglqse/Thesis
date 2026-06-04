#!/bin/sh
# Retune the DQN for the calibrated (low-demand) regime: the old reward_scale=0.05
# was tuned for the dense regime and kills the (now much smaller) learning signal.
# Try larger reward_scale, and also the ATS state (congested-regime signal).
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || true

train_eval() {  # tag reward state reward_scale
  echo "===== TRAIN haichau_calib tag=$1 reward=$2 state=$3 rscale=$4 ====="
  EXP_TAG="$1" REWARD_TYPE="$2" STATE_MODE="$3" REWARD_SCALE="$4" COUNT_NORM=10 \
    PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib
  echo "===== EVAL haichau_calib tag=$1 ====="
  EXP_TAG="$1" COUNT_NORM=10 MAX_STEPS=1000 \
    PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_calib
}

train_eval rs1     queue_norm          basic  1.0
train_eval rs05    queue_norm          basic  0.5
train_eval ats_rs1 efficient_pressure  ats    1.0
echo "RETUNE_DONE"
