#!/bin/sh
# Push the calib DQN past 25%: reward_scale=0.5 is the peak (+22.2%); now tune the
# remaining learning-quality levers (more episodes, richer ATS state, higher lr).
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

# tag reward state episodes lr  (all at reward_scale=0.5, count_norm=10)
run() {
  echo "===== TRAIN haichau_calib tag=$1 reward=$2 state=$3 ep=$4 lr=$5 ====="
  EXP_TAG="$1" REWARD_TYPE="$2" STATE_MODE="$3" EPISODES="$4" LR="$5" \
    REWARD_SCALE=0.5 COUNT_NORM=10 PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib
  echo "===== EVAL haichau_calib tag=$1 ====="
  EXP_TAG="$1" COUNT_NORM=10 MAX_STEPS=1000 \
    PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_calib
}

run rs05_ep120  queue_norm          basic  120  0.0003
run rs05_ats    efficient_pressure  ats    60   0.0003
run rs05_lr6    queue_norm          basic  60   0.0006
echo "PUSH25_DONE"
