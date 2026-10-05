# Da Nang data and claim boundary audit

> Source interpretation updated 2026-09-23: see [the current evidence ledger](thesis-evidence-ledger.md). In particular, street spelling varies in the source; the 2025 camera estimation statement does not establish row-level provenance for the 2022 table. Historical wording below is retained as an audit record.

**Audit date:** 2026-09-09  
**Purpose:** make the evidence boundary usable in the thesis and defense deck. This
audit reports repository evidence only; it does not infer missing counts.

## 1. Evidence that may be called an observed anchor

The only repository data that can be described as direct *vehicle-count evidence* are
the four digitized camera movement lines in
`datasets/danang_published/phan2025_camera_hourly_digitized.csv`. They cover Camera 01
and Camera 02, through and left-turn lines, at one junction, from 07:00--18:00 local
time on 2025-04-01. They are a digitization of Figures 17--18, rounded to five
vehicles/hour, with a stated reading tolerance of +/-15 or +/-30 vehicles/hour. They
are therefore **digitized published counts, not redistributed raw detector output**.

The summed count across those four lines is 1,255 veh/h at 07:00, 2,330 at 08:00,
1,395 at 13:00, and 2,400 at 17:00. The full hourly series is in the CSV; its
`derived_pcu_per_h` is a conversion using the paper's factors, not an extra observation.
The source and digitization method are documented in
`datasets/danang_published/README.md`.

Use the following citation for this anchor:

> Phan, T. C., Le, V. D., and Nguyen, T. (2025). *Application of Dueling Double
> Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City,
> Vietnam*. Machine Learning and Knowledge Extraction, 7(3), 65.
> https://doi.org/10.3390/make7030065

The corresponding BibTeX key is `phan2025danang` in
`paper/references_verified.bib`. The source paper identifies the site as the Nguyen
Thanh Nghi--Cach Mang Thang 8--2/9 junction; the local data README and the canonical
manuscript record that site-level scope.

`datasets/danang_published/tran2025_peak_turning_movements.csv` is useful contextual
evidence, but cannot be called direct observed vehicle counts. Its 12 rows total
6,171 PCU/h and every row is explicitly labelled
`published_aggregate_mixed_observed_estimated`. The local README says that directions
outside the two-camera coverage were estimated from observed proportions and that the
article does not identify observed versus inferred rows. Use it only as a published
aggregate PCU table or as a modelling/stress input, retaining that qualification.

## 2. Actual network scope

The CityFlow extension is the versioned `haichau_network_v2` dataset:

- `datasets/haichau_network_v2/provenance.json` fixes the OSM clip to WGS84
  `[108.1888, 16.0213, 108.2360, 16.1037]`, labels it
  `osm_topology_synthetic_demand`, and records `expected_controlled_signals: 53`.
- The tracked canonical `datasets/haichau_network_v2/roadnet.json` contains 528
  non-virtual intersections, 64 virtual intersections, and 1,107 roads; the controller
  contract selects 53 multi-phase signals as controlled agents. The 53-agent count is
  independently recorded in `datasets/haichau_network_v2/README.md` and
  `results/haichau_network_v2/release-inputs/viewer-network.json`.
- The OSM source is a Geofabrik Vietnam extract. Its retrieval date, converter version,
  and netconvert version are `unknown_not_recorded`, so no snapshot-date or tool-version
  claim is supportable.
- Signal plans are not field observations. The conversion used `netconvert` with
  `--tls.guess-signals`, `--tls.join`, `--tls.default-type actuated`, and the canonical
  roadnet has one documented synthetic normalization at intersection `5896811072`
  (one 80-second action split into two 40-second actions). The provenance file states
  that the normalized phase plan is not an observed Hai Chau controller plan.
- `configs/haichau_network_v2.yaml` labels demand
  `synthetic_osm_haichau_constrained_by_danang_profiles`: 500 deterministic
  boundary-to-boundary routes, 90% synthetic motorcycle share, and time-varying
  intervals scaled from the **sum of all four** camera lines. Those paths, their OD
  pairs, vehicle mix, route coverage rules, and signal plans are modelling choices.

## 3. Claims prohibited until district measurements exist

Do not claim that the 53-signal experiment uses measured Hai Chau demand, a calibrated
district OD matrix, observed turning counts at the 53 signals, observed route choice,
field signal timing, field capacity, or an observed Hai Chau vehicle mix. Do not use the
four-line totals to describe total junction volume, a corridor total, district volume,
or a citywide peak. Do not call 6,171 PCU/h twelve fully observed movements.

Consequently, no result may be phrased as a reduction in *real Hai Chau congestion*, a
district travel-time benefit, an operationally valid signal-plan improvement, a field
safety result, or a deployment recommendation. After the release verifier accepts a
campaign, the defensible scope is only comparative behavior **within the frozen synthetic
CityFlow protocol**. This boundary is consistent with `README.md`,
`datasets/haichau_network_v2/README.md`, and `docs/defense/demo-runbook.md`.

## 4. Recommended wording

Use this thesis wording:

> The empirical anchor is a reconstruction of the Nguyen Thanh Nghi--Cach Mang Thang
> 8--2/9 junction using four digitized camera movement lines published by Phan et al.
> (2025) for 1 April 2025. At 08:00, 13:00, and 17:00, these four lines sum to 2,330,
> 1,395, and 2,400 vehicles per hour, respectively. They are partial junction coverage;
> they are not a district OD dataset or a full-intersection count.

> The scale experiment controls 53 multi-phase signals in an OpenStreetMap-derived
> CityFlow topology. Its routes, OD pairs, demand magnitudes, vehicle mix, and signal
> programs are synthetic. The temporal demand profile is constrained by the four-line
> Da Nang camera series. Results therefore test controller behavior and scalability in
> this frozen simulation protocol, not measured Hai Chau traffic performance.

Use this short deck wording:

> **Observed anchor (one junction):** four published, digitized camera movement lines
> on 1 Apr 2025; partial coverage only.
>
> **Scale experiment (Hai Chau):** 53 OSM-derived controlled signals; synthetic routes,
> demand, vehicle mix, and signal programs. Camera evidence shapes time-of-day demand
> only; it does not calibrate district OD or turning flows.

If a final campaign is accepted, append only: “Comparative results are valid inside the
frozen synthetic protocol.” Do not replace the synthetic qualification with “real-world,”
“observed district,” “field-calibrated,” or “deployment-ready.”
