#!/bin/sh
# Fixed-Time green-duration sweep on both scenarios (eval-only; quick).
set -e
pip install dataclasses numpy pyyaml >/dev/null 2>&1
echo "===== SWEEP haichau ====="
MAX_STEPS=800 PYTHONPATH=src python3 scripts/sweep_fixed_time.py haichau
echo "===== SWEEP haichau_peak ====="
MAX_STEPS=1000 PYTHONPATH=src python3 scripts/sweep_fixed_time.py haichau_peak
echo "SWEEP_DONE"
