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

# Regenerate the canonical baselines FIRST with the strengthened Fixed-Time (best
# green per scenario from the sweep), so the experiment evals below reuse the
# strong Fixed-Time row. Overwrites results/<area>/comparison.json; the original
# 10s-Fixed-Time numbers stay frozen in results/references/.
echo "===== REGEN baselines (strong Fixed-Time) ====="
FIXED_GREEN=25 MAX_STEPS=800  PYTHONPATH=src python3 scripts/run_comparison.py haichau
FIXED_GREEN=40 MAX_STEPS=1000 PYTHONPATH=src python3 scripts/run_comparison.py haichau_peak

train_eval haichau       combo       queue_norm  1  800
train_eval haichau_peak  queue_norm  queue_norm  0  1000
train_eval haichau_peak  combo       queue_norm  1  1000
echo "BATCH2_DONE"
