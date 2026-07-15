#!/bin/sh
# Tier-2 multi-seed: retrain the best-config DQN per scenario across K seeds and
# eval each on the canonical flow, reusing the frozen deterministic baseline rows.
# Isolated under results/<scen>/exp_ms<seed>/ -- NEVER touches frozen artifacts.
# Resumable: skips a (scenario, seed) whose exp_ms<seed>/comparison.json exists.
#
# Run in the CityFlow container:
#   make cf-run CMD="sh scripts/exp_multiseed_tier2.sh"
# Tunables (env): K (default 5), EVAL_EVERY (default 5), SCENARIOS (default all four).
# POSIX-sh only (no bashisms) so it runs on the container's minimal shell.
set -u
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml

K="${K:-5}"
EVAL_EVERY="${EVAL_EVERY:-5}"
SCENARIOS="${SCENARIOS:-haichau haichau_calib haichau_peak haichau_rush}"

# Per-scenario best-config: "REWARD_TYPE STATE_MODE REWARD_SCALE COUNT_NORM EPISODES"
cfg_for() {
  case "$1" in
    haichau)       echo "queue_norm basic 0.05 40 60" ;;
    haichau_calib) echo "queue_norm basic 0.5 10 120" ;;
    haichau_peak)  echo "efficient_pressure ats 0.05 40 60" ;;
    haichau_rush)  echo "queue_norm basic 0.5 5 120" ;;
    *) echo "" ;;
  esac
}

for scen in $SCENARIOS; do
  cfg=$(cfg_for "$scen")
  if [ -z "$cfg" ]; then echo "!! unknown scenario $scen, skipping"; continue; fi
  # shellcheck disable=SC2086
  set -- $cfg
  RT=$1; SM=$2; RS=$3; CN=$4; EP=$5
  k=0
  while [ "$k" -lt "$K" ]; do
    tag="ms${k}"
    out="results/${scen}/exp_${tag}/comparison.json"
    if [ -f "$out" ]; then
      echo "== SKIP ${scen} seed ${k} (exists) =="
      k=$((k+1)); continue
    fi
    echo "===== TRAIN ${scen} seed=${k} [rt=$RT sm=$SM rs=$RS cn=$CN ep=$EP] ====="
    if SEED="$k" EXP_TAG="$tag" REWARD_TYPE="$RT" STATE_MODE="$SM" REWARD_SCALE="$RS" \
        COUNT_NORM="$CN" EPISODES="$EP" EVAL_EVERY="$EVAL_EVERY" \
        PYTHONPATH=src python3 scripts/train_dqn.py "$scen"; then
      echo "===== EVAL ${scen} seed=${k} ====="
      EXP_TAG="$tag" COUNT_NORM="$CN" MAX_STEPS=1000 \
        PYTHONPATH=src python3 scripts/run_experiment_eval.py "$scen" || echo "!! eval failed ${scen} ${k}"
    else
      echo "!! train failed ${scen} ${k}"
    fi
    k=$((k+1))
  done
done
echo "MULTISEED_TIER2_DONE"
