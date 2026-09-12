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

The bounded confirmatory set contains nine test realizations: demand seeds
101, 102, and 105 for normal, AM peak, and PM peak. The residual model is the
pilot step-4 checkpoint, selected without reading the test split. The aggregate
result is:

| Controller | Queue-hours | Relative to fixed-time |
| --- | ---: | ---: |
| Fixed-time | 5,159.34 | 0.00% |
| Schedule-residual DDQN | 4,959.52 | **3.87% lower** |

The per-regime means show where the gain comes from:

| Regime | Cases | Mean change vs fixed | Range |
| --- | ---: | ---: | ---: |
| Normal | 3 | 0.00% | 0.00% to 0.00% |
| AM peak | 3 | 1.70% lower | −7.15% to 11.89% |
| PM peak | 3 | 4.75% lower | −9.66% to 19.20% |

The normal result is an exact tie by construction: the residual controller
uses the executed fixed-time reference in that regime. The peak results vary
with demand realization, so the aggregate number and the complete per-case
table should be presented together. A paired bootstrap over the nine case-level
percentage changes gives a 95% interval of −2.92% to 7.73%; the current sample
supports an observed aggregate gain but is not large enough for a definitive
significance claim.

The machine-readable source is
`results/haichau_network_v2/pilot-campaign-full9-summary.json`; regenerate it
with `scripts/summarize_haichau_short_campaign.py` after rerunning the campaigns.

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
held-out aggregate queue metric. It does not justify claiming improvement on
every individual demand realization. The nine-case table is an exploratory
bounded result; the preregistered 15-case release campaign remains the final
evidence gate when all five confirmatory seeds pass selection.
