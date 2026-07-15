#!/bin/sh
# Honest ablation variants on a chosen (realistic) regime, using the FIXED report-horizon
# greedy-eval checkpoint selection (EVAL_EVERY -> trainer._greedy_eval at eval_max_steps).
# Re-points the ablation off the buggy/oversaturated dense regime (see
# docs/ablation_honest_plan.md). Reuses the regime's base config (reward/state/scale/
# count-norm/episodes) from the multi-seed cfg_for; overrides only what each variant tests.
#
#   make cf-run CMD="sh scripts/exp_ablation_honest.sh <area> [variants...]"
#   (run DETACHED after the multi-seed re-run finishes — same CityFlow container, do not
#    contend on the critical path.)
#
# Variants (default "ws basic"):
#   ws       - main reward/state + Max-Pressure warm-start (400) + n-step (3)  [negative result]
#   basic    - pressure reward + basic state   [the ATS contrast; = "DQN basic"]
#   pressure - alias of basic (reference reward)
#   ats      - efficient_pressure + ats state  [approaching-demand channel]
#   dueling  - main reward/state + dueling head
#
# Writes results/<area>/exp_abl_<tag>/comparison.json. Resumable (skips existing).
# SINGLE-SEED by design: only large sign-flip / directional effects (ws-hurts, ats-vs-basic)
# are read from this; near-tie variant *rankings* are within the multi-seed seed-CI and must
# NOT be claimed (docs/ablation_honest_plan.md).
set -eu

AREA="${1:?usage: exp_ablation_honest.sh <area> [variants...]}"
shift 2>/dev/null || true
VARIANTS="${*:-ws basic}"
EVAL_EVERY="${EVAL_EVERY:-5}"
SEED="${SEED:-0}"

cfg_for() {  # REWARD_TYPE STATE_MODE REWARD_SCALE COUNT_NORM EPISODES  (matches exp_multiseed_tier2.sh)
  case "$1" in
    haichau)       echo "queue_norm basic 0.05 40 60" ;;
    haichau_calib) echo "queue_norm basic 0.5 10 120" ;;
    haichau_peak)  echo "efficient_pressure ats 0.05 40 60" ;;
    haichau_rush)  echo "queue_norm basic 0.5 5 120" ;;
    *) echo "" ;;
  esac
}

cfg=$(cfg_for "$AREA")
[ -z "$cfg" ] && { echo "!! unknown area $AREA"; exit 1; }
# shellcheck disable=SC2086
set -- $cfg
BRT=$1; BSM=$2; RS=$3; CN=$4; EP=$5

run_variant() {  # tag REWARD_TYPE STATE_MODE DUELING WARMSTART_STEPS N_STEP
  tag="$1"; RT="$2"; SM="$3"; DU="$4"; WS="$5"; NS="$6"
  out="results/${AREA}/exp_abl_${tag}/comparison.json"
  if [ -f "$out" ]; then echo "== SKIP ${AREA}/abl_${tag} (exists) =="; return 0; fi
  echo "===== TRAIN ${AREA} abl_${tag} [rt=$RT sm=$SM du=${DU:-} ws=${WS:-} ns=${NS:-} rs=$RS cn=$CN ep=$EP] ====="
  # Empty env values are ignored by train_dqn.py (it uses `if os.environ.get(...)`).
  if SEED="$SEED" EXP_TAG="abl_${tag}" REWARD_TYPE="$RT" STATE_MODE="$SM" \
      DUELING="$DU" WARMSTART_STEPS="$WS" N_STEP="$NS" \
      REWARD_SCALE="$RS" COUNT_NORM="$CN" EPISODES="$EP" EVAL_EVERY="$EVAL_EVERY" \
      PYTHONPATH=src python3 scripts/train_dqn.py "$AREA"; then
    echo "===== EVAL ${AREA} abl_${tag} ====="
    EXP_TAG="abl_${tag}" COUNT_NORM="$CN" MAX_STEPS=1000 \
      PYTHONPATH=src python3 scripts/run_experiment_eval.py "$AREA" || echo "!! eval failed ${AREA} abl_${tag}"
  else
    echo "!! train failed ${AREA} abl_${tag}"
  fi
}

for v in $VARIANTS; do
  case "$v" in
    pressure|basic) run_variant "$v"    pressure           basic ""  ""  "" ;;
    ats)            run_variant ats      efficient_pressure ats   ""  ""  "" ;;
    dueling)        run_variant dueling  "$BRT"             "$BSM" 1  ""  "" ;;
    ws)             run_variant ws       "$BRT"             "$BSM" "" 400  3 ;;
    *) echo "!! unknown variant '$v' (want: ws basic pressure ats dueling)" ;;
  esac
done
echo "ABLATION_HONEST_DONE ${AREA} [${VARIANTS}]"
