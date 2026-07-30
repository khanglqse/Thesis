#!/bin/sh
# Strengthened-study batch — run INSIDE the CityFlow container (Python 3.6):
#   docker run -d --name strengthen -v "$PWD":/work -w /work \
#     cityflowproject/cityflow:latest \
#     sh -lc 'sh scripts/run_strengthen_batch.sh 2>&1 | tee results/_strengthen_batch.log'
#
# Produces the two experiments coded-but-never-run: DQN<->Max-Pressure agreement,
# and the robustness incident + demand-shift rows. Each step SKIPS if its output
# already exists (resumable after a kill). COUNT_NORM must match each checkpoint's
# training normalizer (rush=5, calib=10); MAX_STEPS defaults to 1000 (report horizon).
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || true

echo "### agreement rush";       [ -f results/haichau_rush/agreement/agreement.json ]  || COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_agreement.py  haichau_rush                 || echo "FAILED agreement rush"
echo "### agreement calib";      [ -f results/haichau_calib/agreement/agreement.json ] || COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_agreement.py  haichau_calib                || echo "FAILED agreement calib"
echo "### incident rush";        [ -f results/haichau_rush/robustness/incident.json ]  || COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush  incident        || echo "FAILED incident rush"
echo "### incident calib";       [ -f results/haichau_calib/robustness/incident.json ] || COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_robustness.py haichau_calib incident        || echo "FAILED incident calib"
echo "### shift rush->calib";    [ -f results/haichau_rush/robustness/shift.json ]     || COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush  shift haichau_calib || echo "FAILED shift rush"
echo "### shift calib->rush";    [ -f results/haichau_calib/robustness/shift.json ]    || COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_robustness.py haichau_calib shift haichau_rush  || echo "FAILED shift calib"
echo "### ALL DONE"
