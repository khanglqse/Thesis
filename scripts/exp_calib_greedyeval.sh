#!/bin/sh
# Proper fix: select the checkpoint by periodic GREEDY evaluation (EVAL_EVERY=5),
# not by the last/training-queue episode. DQN here is noisy and peaks then
# diverges, so this reliably captures each run's true best policy. reward_scale=0.5
# (the tuned peak), 120 episodes, on haichau_calib.
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

run() {  # tag reward state lr
  echo "===== TRAIN haichau_calib tag=$1 reward=$2 state=$3 lr=$4 (greedy-eval ckpt) ====="
  EXP_TAG="$1" REWARD_TYPE="$2" STATE_MODE="$3" LR="$4" EPISODES=120 EVAL_EVERY=5 \
    REWARD_SCALE=0.5 COUNT_NORM=10 PYTHONPATH=src python3 scripts/train_dqn.py haichau_calib
  echo "===== EVAL haichau_calib tag=$1 ====="
  EXP_TAG="$1" COUNT_NORM=10 MAX_STEPS=1000 \
    PYTHONPATH=src python3 scripts/run_experiment_eval.py haichau_calib
}

run ge_qnorm  queue_norm          basic  0.0003
run ge_ats    efficient_pressure  ats    0.0003
echo "GREEDYEVAL_DONE"
