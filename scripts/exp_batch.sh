#!/bin/sh
# Experiment batch runner (executed INSIDE the CityFlow Docker container).
#   make cf-run CMD="sh scripts/exp_batch.sh <area> <eval_steps>"
# Trains + evaluates each DQN variant sequentially, reusing one container so the
# pip install / engine startup cost is paid once. Outputs land in
# results/<area>/exp_<tag>/ ; the frozen references in results/<area>/ are untouched.
set -e
AREA="${1:-haichau}"
EVAL_STEPS="${2:-800}"

pip install dataclasses numpy pyyaml >/dev/null 2>&1

run() {  # tag reward dueling
  echo "===== TRAIN area=$AREA tag=$1 reward=$2 dueling=$3 ====="
  EXP_TAG="$1" REWARD_TYPE="$2" DUELING="$3" PYTHONPATH=src python3 scripts/train_dqn.py "$AREA"
  echo "===== EVAL area=$AREA tag=$1 ====="
  MAX_STEPS="$EVAL_STEPS" EXP_TAG="$1" PYTHONPATH=src python3 scripts/run_experiment_eval.py "$AREA"
}

run queue        queue        0
run queue_norm   queue_norm   0
run dueling      pressure     1
echo "ALL_DONE_${AREA}"
