#!/bin/sh
# Batch 4: Max-Pressure warm-start + n-step returns, combined with the best
# per-scenario config. The warm-start makes RL start AT Max-Pressure, n-step
# fixes delayed credit; together the best shot at finally beating MP.
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1

train_eval() {  # area tag reward state warmstart nstep eval_steps
  echo "===== TRAIN area=$1 tag=$2 reward=$3 state=$4 warmstart=$5 nstep=$6 ====="
  EXP_TAG="$2" REWARD_TYPE="$3" STATE_MODE="$4" WARMSTART_STEPS="$5" N_STEP="$6" \
    PYTHONPATH=src python3 scripts/train_dqn.py "$1"
  echo "===== EVAL area=$1 tag=$2 ====="
  MAX_STEPS="$7" EXP_TAG="$2" PYTHONPATH=src python3 scripts/run_experiment_eval.py "$1"
}

# normal: warm-start + n-step, basic state (pressure) and best-reward (queue_norm)
train_eval haichau       ws_nstep   pressure            basic  400  3  800
train_eval haichau       ws_qnorm   queue_norm          basic  400  3  800
# peak: warm-start + n-step on top of the ATS state that already helped peak
train_eval haichau_peak  ws_ats     efficient_pressure  ats    400  3  1000
echo "BATCH4_DONE"
