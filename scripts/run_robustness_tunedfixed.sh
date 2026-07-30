#!/bin/sh
# Re-run the robustness grid with the TUNED Fixed-Time green (25 s for the moderate
# rush/calib regimes) so the Fixed-Time baseline matches the headline tab:waiting/
# tab:queue. Only the Fixed-Time rows change; Max-Pressure/DQN/Random are independent
# of FIXED_GREEN (verified by comparing against the green=40 run). Overwrites the
# noise/incident/shift JSONs. Run INSIDE the CityFlow container.
pip install dataclasses numpy pyyaml >/dev/null 2>&1 || true
export FIXED_GREEN=25

echo "### rush noise";     COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush  noise               || echo "FAILED rush noise"
echo "### rush incident";  COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush  incident            || echo "FAILED rush incident"
echo "### rush shift";     COUNT_NORM=5  PYTHONPATH=src python3 scripts/run_robustness.py haichau_rush  shift haichau_calib || echo "FAILED rush shift"
echo "### calib noise";    COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_robustness.py haichau_calib noise               || echo "FAILED calib noise"
echo "### calib incident"; COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_robustness.py haichau_calib incident            || echo "FAILED calib incident"
echo "### calib shift";    COUNT_NORM=10 PYTHONPATH=src python3 scripts/run_robustness.py haichau_calib shift haichau_rush  || echo "FAILED calib shift"
echo "### ALL DONE"
