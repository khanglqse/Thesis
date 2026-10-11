#!/bin/bash
# Waits until 01:00 local, then runs the 1000-realization baseline Monte-Carlo (resumable).
cd /Users/khanglq1/workplace/Thesis/traffic-rl
target=$(date -j -v+1d -f "%H:%M:%S" "01:00:00" +%s 2>/dev/null)
[ "$(date +%H)" -lt 1 ] && target=$(date -j -f "%H:%M:%S" "01:00:00" +%s)
echo "scheduled for $(date -r $target)  (pid $$)"
while [ "$(date +%s)" -lt "$target" ]; do sleep 30; done
echo "start $(date)"
SUMO_HOME=/opt/homebrew/share/sumo python3 scripts/run_danang_baseline_mc.py -n 1000 -j 11
echo "exit $? at $(date)"
