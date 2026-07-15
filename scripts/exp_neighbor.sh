#!/bin/sh
# C4: train the neighbour-coordinated DQN (state_mode=neighbor, CoLight-lite) per
# scenario and eval vs the frozen baselines. Isolated under results/<scen>/exp_neighbor/.
# The question: does upstream-neighbour context (approaching demand) let the learned
# policy close the gap to Max-Pressure? Report honestly either way.
#
#   make cf-run CMD="sh scripts/exp_neighbor.sh"
# Tunables: SCENARIOS (default rush+peak+normal, where the MP gap matters most).
set -u
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

SCENARIOS="${SCENARIOS:-haichau_rush haichau_peak haichau}"

# "REWARD_SCALE COUNT_NORM EPISODES" (reward_type stays queue_norm; neighbour augments it)
cfg_for() {
  case "$1" in
    haichau)       echo "0.05 40 60" ;;
    haichau_peak)  echo "0.05 40 60" ;;
    haichau_rush)  echo "0.5 5 120" ;;
    *) echo "" ;;
  esac
}

for scen in $SCENARIOS; do
  cfg=$(cfg_for "$scen")
  if [ -z "$cfg" ]; then echo "!! unknown $scen"; continue; fi
  # shellcheck disable=SC2086
  set -- $cfg
  RS=$1; CN=$2; EP=$3
  if [ -f "results/${scen}/exp_neighbor/comparison.json" ]; then
    echo "== SKIP ${scen} (exists) =="; continue
  fi
  echo "===== TRAIN ${scen} neighbor [rs=$RS cn=$CN ep=$EP] ====="
  if STATE_MODE=neighbor EXP_TAG=neighbor REWARD_TYPE=queue_norm REWARD_SCALE="$RS" \
      COUNT_NORM="$CN" EPISODES="$EP" EVAL_EVERY=5 \
      PYTHONPATH=src python3 scripts/train_dqn.py "$scen"; then
    echo "===== EVAL ${scen} neighbor ====="
    EXP_TAG=neighbor COUNT_NORM="$CN" MAX_STEPS=1000 \
      PYTHONPATH=src python3 scripts/run_experiment_eval.py "$scen" || echo "!! eval failed ${scen}"
  else
    echo "!! train failed ${scen}"
  fi
done
echo "NEIGHBOR_DONE"
