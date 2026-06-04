set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || pip install dataclasses numpy pyyaml
echo "===== TRAIN DQN haichau_rush (reward_scale=0.5, greedy-eval ckpt, count_norm=5) ====="
REWARD_TYPE=queue_norm REWARD_SCALE=0.5 COUNT_NORM=5 EVAL_EVERY=5 EPISODES=120 \
  PYTHONPATH=src python3 scripts/train_dqn.py haichau_rush
echo "===== COMPARE haichau_rush ====="
FIXED_GREEN=25 COUNT_NORM=5 MAX_STEPS=1000 PYTHONPATH=src python3 scripts/run_comparison.py haichau_rush
echo "RUSH_DONE"
