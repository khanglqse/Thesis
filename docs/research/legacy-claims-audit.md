# Legacy claims and metric audit

The rows below govern reuse of existing results. “Legacy protocol” means internally traceable to the old artifacts; it does not mean suitable for the new thesis conclusion.

| Claim | Evidence inspected | Verdict | Required treatment |
|---|---|---|---|
| 53 signalized Hai Chau agents | roadnet parser and replay test recover 53 controllable nodes | supported in legacy protocol | describe as OSM-derived/heuristically converted until signal inventory is field-checked |
| `haichau_rush` has 50,500 vehicles | 500 flow entries schedule 50,000 departures in `[0,3600)` and 50,500 if CityFlow includes departures at exactly 3600 s | inconsistent wording | state endpoint convention; never equate scheduled departures with inserted, concurrent, or completed vehicles |
| 14,000 vehicles in the reported 1000-second window | exact enumeration of `startTime + k*interval` for `t < 1000` | supported schedule count | report scheduled/eligible only; instrument inserted/arrived counts separately |
| demand is real or calibrated | `flow_gen.py` creates seeded random-walk routes; no observed count registry is consumed | overclaimed | relabel all existing Hai Chau flows “synthetic on an OSM-derived network” |
| motorcycle share is a measured Da Nang value | flow entry ratios vary by scenario; `haichau_rush` entry ratio is 89.8%; config comments say 92% | inconsistent/unverified | use observed class data per case; treat old ratios as scenario assumptions |
| DQN reduces waiting by 37.1% vs Fixed-Time | old five-training-seed aggregate: 113.239 vs 179.889 vehicle-hours | supported only in legacy protocol | retain as historical result with ±3.892 veh-h CI half-width; do not headline the new thesis |
| DQN reaches or beats Max-Pressure | old aggregate: MP 107.831 veh-h, DQN 113.239 veh-h | contradicted for headline case | state DQN is worse than MP on mean waiting under that protocol |
| five-seed baseline uncertainty is zero | identical cached baseline rows are repeated across DQN seed folders | invalid uncertainty estimate | rerun baselines over demand and simulator seeds; one deterministic case is not population uncertainty |
| checkpoint selection is independent | trainer greedy-evaluates on the same environment/flow later used in comparison | false | introduce train/validation/test case manifests and select only on validation |
| waiting-hours is exact cumulative vehicle waiting time | `sum(queue_series) * 10 / 3600`; queue sampled once per decision | overclaimed | call it decision-sampled queue integral; add per-step integration or simulator-native waiting metric |
| yellow timing is modeled | env uses the first empty phase as an all-red transition for `yellow_time` seconds | inconsistent | call it all-red intergreen; add explicit yellow states if claiming yellow compliance |
| motorcycle behavior is realistic | CityFlow has `laneChange=False`; short/narrow templates do not create sublane filtering | overclaimed | use SUMO sublane pilot and retain CityFlow limitation |
| signal safety is guaranteed | min-green and transition tests exist; no maximum-red/pedestrian/clearance validation | overclaimed | add phase conflict, intergreen, max-red and starvation checks |
| travel-time comparison is population-valid | CityFlow final average and one demand realization are reported | unverified | define completed/active vehicle cohort and uncertainty across held-out demand cases |
| robustness generalizes to incidents | perturbation tests exist but old evaluation shares base flow and limited seeds | unverified | run preregistered demand shift, sensor noise and incident cases with independent seeds |

## Exact flow enumeration

For departures strictly before the horizon, the local files schedule:

| Scenario | Flow entries | Motorcycle-template entries | `[0,1000)` | `[0,3600)` |
|---|---:|---:|---:|---:|
| subarea | 300 | 73.3% | 150,000 | 540,000 |
| haichau | 500 | 89.8% | 333,500 | 1,200,000 |
| haichau_calib | 500 | 89.8% | 21,000 | 75,000 |
| haichau_peak | 920 | 93.2% | 310,800 | 310,920 |
| haichau_rush | 500 | 89.8% | 14,000 | 50,000 |

These counts expose how much insertion capacity, end-point semantics, and reporting horizon matter. The final evaluator must output `scheduled`, `eligible`, `inserted`, `active`, `arrived`, and `teleported/dropped` (when supported) as separate quantities.
