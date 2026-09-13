# Chapter 4 — Hai Chau V2 network results

This chapter reports the current 53-signal Hai Chau network experiment. The
network is derived from the constrained Da Nang OSM dataset and uses the pinned
CityFlow runtime. All comparisons use identical road network, demand realization,
simulator seed, and 3,600-second horizon for a matched pair of controllers.

## 4.1 Controllers and metric

The reference is the validation-tuned 25-second fixed-time controller. The
proposed controller is schedule-residual DDQN: macro actions modify a fixed
300-second schedule block, while normal-regime operation is anchored exactly to
the fixed-time trace. The primary metric is network queue integral including
pending demand, reported as vehicle-hours. Lower values are better.

## 4.2 Matched held-out comparison

The strongest completed bounded comparison uses the final seed-14 step-4
checkpoint, selected without reading the test split. It covers all 15 declared
test realizations: demand seeds 101--105 for each of normal, AM peak, and PM
peak. The aggregate result is:

| Controller | Queue-hours | Relative to fixed-time |
| --- | ---: | ---: |
| Fixed-time | 8,339.43 | 0.00% |
| Schedule-residual DDQN (seed 14, step 4) | 7,829.25 | **6.12% lower** |

The per-regime means show where the gain comes from:

| Regime | Cases | Mean change vs fixed | Range |
| --- | ---: | ---: | ---: |
| Normal | 5 | 0.00% | 0.00% to 0.00% |
| AM peak | 5 | 3.53% lower | −4.24% to 8.75% |
| PM peak | 5 | 8.86% lower | −2.40% to 26.11% |

The normal result is an exact tie by construction: the residual controller
uses the executed fixed-time reference in that regime. The peak results vary
with demand realization, so the aggregate number and the complete per-case
table should be presented together. A paired bootstrap over the 15 case-level
percentage changes gives a 95% interval of 0.90% to 8.35%.

The machine-readable source is
`results/haichau_network_v2/final15-seed14-step4-summary.json`; regenerate it
with `scripts/summarize_haichau_short_campaign.py` after rerunning the campaigns.

### 4.2.1 Baseline matrix

The same 15 cases were also run with raw Max-Pressure and hysteretic
Max-Pressure. The complete matrix is:

| Controller | Total queue-hours | Mean completion rate | Change vs fixed-time |
| --- | ---: | ---: | ---: |
| Fixed-time | 8,339.43 | 66.92% | 0.00% |
| Max-Pressure | 6,347.00 | 70.56% | **23.89% lower** |
| Hysteretic Max-Pressure | 6,739.13 | 69.77% | **19.19% lower** |
| Schedule-residual DDQN | 7,829.25 | 67.98% | **6.12% lower** |

Max-Pressure is the strongest baseline in this synthetic network. The learned
controller still improves over fixed-time, but this comparison prevents an
unsupported claim that DDQN is the best controller for every regime. The
machine-readable matrix is
`results/haichau_network_v2/final15-controller-matrix-summary.json`.
Its network, runtime, checkpoint and case identities are recorded in
`results/haichau_network_v2/final15-controller-matrix-provenance.json`.

### 4.2.2 Secondary operational outcomes

The same matched seed-14 pairs provide additional diagnostics. Values below
are arithmetic means over the fifteen cases; they are descriptive and do not
replace the primary seed-level inference.

| Outcome | Fixed-time | Residual DDQN | Difference (DDQN - fixed) |
| --- | ---: | ---: | ---: |
| Completion rate | 66.92% | **67.98%** | **+1.06 pp** |
| Insertion rate | 97.15% | **97.97%** | **+0.82 pp** |
| Mean maximum node queue | 141.87 | **124.93** | **−16.93 vehicles** |
| Completed-trip travel time | 737.81 s | 743.26 s | +5.45 s |
| Spillback lane-seconds | 1,432.33 | 1,497.53 | +65.20 |

The improvement in completion and maximum queue is consistent with the lower
queue integral. Completed-trip travel time is slightly higher, so queue
reduction should not be presented as universal travel-time improvement. The
spillback increase is concentrated in AM peak (1,461.0 versus 1,144.8
lane-seconds); PM peak decreases from 2,751.4 to 2,630.8 lane-seconds. The
machine-readable source is
`results/haichau_network_v2/final15-seed14-secondary-summary.json`, generated
by `scripts/summarize_haichau_secondary.py`.

As a checkpoint sensitivity result, seed 12 step 8 over the same 15 cases
reduced the aggregate metric by only 0.78% and regressed 5.67% in AM peak.
Seed 15 step 8 reduced the aggregate metric by 0.44%, with a paired bootstrap
interval of −3.99% to 3.99%. These are retained as negative sensitivity
results: passing validation for one seed does not guarantee test
generalization. The two sensitivity summaries are
`results/haichau_network_v2/final15-seed12-step8-summary.json` and
`results/haichau_network_v2/final15-seed15-step8-summary.json`.

Treating the three completed learning seeds as the independent unit gives a
mean aggregate improvement of 2.45% (seed-level range 0.44%--6.12%). The
corresponding AM mean is −1.32%, while the PM mean is 4.21%. This hierarchical
summary is stored in `results/haichau_network_v2/final15-three-seed-summary.json`;
it is a sensitivity result because the preregistered cohort still includes
seeds 13 and 16.

Figure `results/haichau_network_v2/final15-seed-sensitivity.png` visualizes the
same seed-level spread for presentation.

## 4.3 Training and validation

The reduced training profile uses three learning seeds (12, 13, and 14), one
300-second episode per seed, and one representative AM and PM training case.
Each run produced eight optimizer updates and a valid checkpoint. The longer
pilot checkpoint used for the full-hour comparison was trained for four
full-hour episodes. Validation on six cases at pilot step 4 reduced queue
integral by 3.76% in aggregate while remaining exactly equal to fixed-time on
normal cases.

## 4.4 Interpretation and limits

The result answers the practical failure mode seen in the earlier experiment:
the learned controller no longer incurs a normal-hour penalty and improves the
held-out aggregate queue metric across the complete 15-case matrix. It does
not justify claiming improvement on every individual demand realization. This
is a bounded one-seed result; the preregistered five-seed release campaign
remains the final evidence gate.
