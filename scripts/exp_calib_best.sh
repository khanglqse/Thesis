#!/bin/sh
# With best-checkpoint saving in place, re-run the strong config for longer (safe
# now — a late divergence can't overwrite the peak) plus a more-stable low-lr
# variant, to lock in / exceed +22.2% on haichau_calib.
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

run() {  # tag reward state episodes lr
  echo "===== TRAIN haichau_calib tag=$1 reward=$2 state=$3 ep=$4 lr=$5 ====="
  EXP_TAG="$1" REWARD_TYPE="$2" STATE_MODE="$3" EPISODES="$4" LR="$5" \
    REWARD_SCALE=0.5 COUNT_NORM=10 PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib
  echo "===== EVAL haichau_calib tag=$1 ====="
  EXP_TAG="$1" COUNT_NORM=10 MAX_STEPS=1000 \
    PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_calib
}

run best_long   queue_norm          basic  120  0.0003
run best_lr2    queue_norm          basic  120  0.0002
run best_ats    efficient_pressure  ats    120  0.0003
echo "BEST_DONE"
