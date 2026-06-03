#!/bin/sh
# Batch 3: Advanced-XLight ATS state (running-vehicle channel) — the SOTA-backed
# attempt to beat Max-Pressure. Baselines reused from the (strong-Fixed-Time)
# canonical comparison.json.
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1

train_eval() {  # area tag reward state_mode dueling eval_steps
  echo "===== TRAIN area=$1 tag=$2 reward=$3 state=$4 dueling=$5 ====="
  EXP_TAG="$2" REWARD_TYPE="$3" STATE_MODE="$4" DUELING="$5" \
    PYTHONPATH=src python3 scripts/train_dqn.py "$1"
  echo "===== EVAL area=$1 tag=$2 ====="
  MAX_STEPS="$6" EXP_TAG="$2" PYTHONPATH=src python3 scripts/run_experiment_eval.py "$1"
}

train_eval haichau       ats_effp   efficient_pressure  ats  0  800
train_eval haichau       ats_qnorm  queue_norm          ats  0  800
train_eval haichau_peak  ats_effp   efficient_pressure  ats  0  1000
echo "BATCH3_DONE"
