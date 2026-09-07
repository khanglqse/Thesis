# Da Nang pilot network and calibration record

Updated: 2026-09-07. Target: Nguyen Thanh Nghi–Cach Mang Thang 8–2/9.

## Evidence layers

The pinned OSM extract supplies the target location and approach bearings. Phan,
Le and Nguyen (2025) supply the 103-second plan, the published lane description,
12 peak turning movements totalling 6171 PCU/h, and one day of camera profiles.
Figures 17–18 were digitized with an explicit ±15 or ±30 vehicle/h reading
uncertainty per plotted series. The source CSV retains the four vehicle classes.

Two demand families are kept separate:

- `observed_camera_demands` contains the four camera movement lines only. Counts
  are 1395 vehicles/h at 13:00, 2330 at 08:00 and 2400 at 17:00. These are the
  closest available public values to observed vehicle counts, although they were
  digitized from figures rather than obtained as raw detector exports.
- `estimated_full_intersection_demands` expands the 12 published PCU movements
  using the camera class mix. The resulting 5793/9676/9967 vehicle schedules are
  model estimates and must never be labelled direct counts.

## Network isolation decision

The full OSM conversion was retained as a reference artifact. A full 3600-second
run exposed confounding queues and collisions at adjacent junctions and very
short OSM edge fragments. The failure record is
`results/research_pilot/calibration/osm_full_horizon_failure_seed1.json`; it is
not a controller result.

The primary pilot therefore isolates the target junction. It uses 300 m
approaches along the pinned OSM bearings, two lanes per Lethanhnghi/Hoaxuan
approach and three per 2/9/Cachmangthang8 approach, as described in the paper.
The three greens and three seven-second clearances reproduce the published
32+7+28+7+22+7 = 103 second cycle. This design tests signal control at the
supported site without allowing unvalidated neighboring signals to determine
the result.

## Safety and capacity checks

The earlier 300-second sublane smoke was insufficient. At a full hour, the OSM
reference produced 14–21 collision events and large insertion backlogs. On the
isolated target, the four observed movements completed a full-hour lane-model
run with zero collisions for normal, AM and PM cases. The same cases under the
0.4 m sublane model produced 0, 1 and 3 collision events respectively. Smaller
time steps and several lateral/car-following parameter variants did not remove
the problem consistently.

The primary controller comparison uses standard SUMO lanes, explicit motorcycle
vehicle dimensions and the observed camera demand family. The sublane model is
retained only as a sensitivity analysis until independent trajectory/headway
data can calibrate it. The full-intersection expansion is a stress case and its
outside-network pending queue must be reported.

A held-out explicit realization later exposed one lane-model rear-end collision
with the default 1.0 s motorcycle headway. A one-parameter reproduction showed
that `tau=1.2` removed the collision. Because this changed capacity and policy
dynamics, every tau=1.0 training/evaluation artifact was invalidated and the
complete protocol was rerun. Across the final 105 held-out controller runs,
collision output recorded zero collisions. The safety change raised congestion
in several scenarios; the before/after diagnostic is retained in
`results/research_pilot/calibration/tau_sensitivity.json`.

The static published plan at simulator seed 101 produced zero collisions. Queue
integrals were 9.81, 63.35 and 128.54 vehicle-hours for normal, AM and PM;
arrivals were 1374, 2158 and 2057, with 0, 0 and 160 vehicles pending at the
boundary. These are engineering pilot values, not final multi-seed estimates.

## Remaining calibration limits

Only one observed date and partial camera coverage are public. There is no raw
headway, saturation-flow, queue-length or travel-time ground truth for this
junction. The pilot is therefore **demand-matched and geometry-audited**, not
fully behavior-calibrated. Final claims must preserve that wording and report
digitization uncertainty, pending vehicles, residual queues and completion.
