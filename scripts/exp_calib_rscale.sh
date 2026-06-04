#!/bin/sh
# Fine-sweep reward_scale around 0.5 (the peak so far: 0.05->+10.8%, 0.5->+22.2%,
# 1.0->+9.5%) to push the DQN past 25% vs Fixed-Time on haichau_calib.
set -e
# Required deps must install (retry once for transient network); no matplotlib here.
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

run() {  # tag reward_scale
  echo "===== TRAIN haichau_calib tag=$1 rscale=$2 ====="
  EXP_TAG="$1" REWARD_TYPE=queue_norm REWARD_SCALE="$2" COUNT_NORM=10 \
    PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib
  echo "===== EVAL haichau_calib tag=$1 ====="
  EXP_TAG="$1" COUNT_NORM=10 MAX_STEPS=1000 \
    PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_calib
}

run rs03  0.3
run rs04  0.4
run rs06  0.6
echo "RSCALE_DONE"
