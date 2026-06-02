#!/bin/sh
# Batch 2: combine the two best changes (dueling + queue_norm reward) on normal,
# and bring the best variants to the peak scenario for a complete peak comparison.
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1

train_eval() {  # area tag reward dueling eval_steps
  echo "===== TRAIN area=$1 tag=$2 reward=$3 dueling=$4 ====="
  EXP_TAG="$2" REWARD_TYPE="$3" DUELING="$4" PYTHONPATH=src python3 scripts/train_dqn.py "$1"
  echo "===== EVAL area=$1 tag=$2 ====="
  MAX_STEPS="$5" EXP_TAG="$2" PYTHONPATH=src python3 scripts/run_experiment_eval.py "$1"
}

train_eval haichau       combo       queue_norm  1  800
train_eval haichau_peak  queue_norm  queue_norm  0  1000
train_eval haichau_peak  combo       queue_norm  1  1000
echo "BATCH2_DONE"
