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

As a checkpoint sensitivity result, seed 12 step 8 over the same 15 cases
reduced the aggregate metric by only 0.78% and regressed 5.67% in AM peak.
This is retained as a negative result: passing validation for one seed does not
guarantee test generalization.

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
