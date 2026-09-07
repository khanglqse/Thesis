# Da Nang data feasibility and pilot decision

## Chosen public-data pilot

The signalized junction formed by Nguyen Thanh Nghi, Cach Mang Thang 8 and 2/9 streets is the strongest immediately reproducible candidate. Phan, Le and Nguyen (2025) publish a 103-second, three-phase fixed plan and 12 turning-movement peak volumes collected by the Da Nang Department of Transport in 2022. The movements total 6171 passenger-car-equivalent vehicles per hour. This is adequate to construct a disclosed observed-peak demand case and to check the published baseline geometry/plan.

The same article reports camera observations on 2025-04-01 from 06:00–18:00 and identifies 07:00–09:00 and 16:00–18:00 as peaks. It states that the raw data are available only on request due to privacy/ethical restrictions and that directions outside the two cameras were estimated from proportions. Therefore, the published peak table is `observed_aggregate_with_estimated_movements`, not raw trajectory data. Figures 17–18 have now been digitized with explicit plot-reading uncertainty for four observed counting lines; these rows are derived observations and remain distinct from raw counts.

## Other sources

- Ton et al. (2024), DOI `10.31130/ud-jst.2024.022ICT`, studies multi-object tracking for real-time Da Nang vehicle flow. A downloadable traffic-count dataset was not verified.
- The 2026 Vietnamese urban traffic detection dataset reports 23,364 annotated images from fixed CCTV at major Da Nang intersections with seven classes and traffic-light states. Its use for turning counts depends on dataset availability, timestamps, camera continuity and license; sampled still images alone do not form demand counts.
- The JICA Da Nang sustainable/resilient urban development report describes traffic survey and future DATRAMAC data integration. It is planning evidence, not a current downloadable calibration dataset.
- A Da Nang roadside observation study counted 17,142 vehicles at 24 sites (14,750 motorcycles and 2,392 cars), but its outcome is turn-signal use rather than movement demand by time interval.

## Decision branch

Current branch is D2: public aggregate observations are sufficient for a one-intersection peak pilot, while a multi-day normal/AM/PM Hai Chau corridor calibration dataset is unavailable. The thesis will proceed with:

1. an observed-peak one-intersection SUMO pilot;
2. transparent normal/peak sensitivity cases derived from the available 12-hour profile only when extraction is documented;
3. the OSM-derived 53-node Hai Chau network as an explicitly synthetic scalability/generalization benchmark;
4. a drafted data request for DATRAMAC/authors, never sent without separate authorization.

This design preserves the user's city-scale focus while keeping the central empirical claim within available evidence.
