# Archived primary source

`phan2025_make7030065.pdf` is the publisher PDF of Phan, T. C., Le, V. D., and Nguyen, T. (2025), *Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam*. Machine Learning and Knowledge Extraction, 7(3), 65.

- DOI: https://doi.org/10.3390/make7030065
- Article: https://www.mdpi.com/2504-4990/7/3/65
- Download: https://mdpi-res.com/d_attachment/make/make-07-00065/article_deploy/make-07-00065.pdf
- Retrieved for this audit: 2026-09-23.
- SHA-256: `26caabea121d7077fba881c40af4d7d01dae52ea1e85e34102f0fc1a67a9bebd`
- Length: 24 pages. Page 1 states CC BY 4.0. This is an unmodified copy; article authors retain attribution.
- Underlying camera/transport-authority data are not included. The Data Availability Statement on page 23 requires a request to the authors.

## Exact source locations

| Claim | Printed page and location |
|---|---|
| Lane counts and green times 32/28/22 s; cycle 103 s | Page 7, site description |
| Three seven-second yellow intervals | Page 8, Figure 4 |
| Twelve PCU/h movements totaling 6,171 | Page 8, Table 1 |
| Attribution of traffic volumes to transport authority in 2022 | Page 7, last paragraph; reference 33 on page 24 is a 2024 planning document |
| Camera collection on 1 April 2025, 06:00–18:00 | Page 16, section 3.2 |
| Two cameras, straight/left lines, estimation of unobserved directions | Pages 16–17 and pages 20–21 |
| Camera 01 SW→NE / SW→NW; Camera 02 NW→SE / NW→NE | Figure 12 and surrounding text, page 17; page 18 |
| PCU factors: motorcycle 0.3, car 1, bus 2, truck 2.5 | Page 19, paragraph before Figures 17–18 |
| Hourly plotted vehicle classes, four movements | Page 20, Figure 17(a,b) and Figure 18(a,b) |
| Raw data access restriction | Page 23, Data Availability Statement |

## Source ambiguities

Page 7 spells the street `Nguyenthanhnghi`, while Table 1, Figure 12, and reference 33 use `Lethanhnghi`. The revised manuscript uses **Le Thanh Nghi**, identifies the site by its connecting roads and Hoa Xuan bridge, and discloses the discrepancy. Legacy internal identifiers such as `ntn_cmt8_29` are not geographical evidence.

The estimation statement is about extending the **2025 camera** data to unobserved directions. It does not establish which, if any, **2022 Table 1** rows were estimated. The CSV's legacy mixed-provenance status is the project's conservative classification, not a row-level finding established by the article.

The article describes 06:00–18:00 collection; the plotted values retained in the CSV have labels 07:00–18:00. `hour_start` is a legacy field name, not proof that each value describes an interval starting at that hour.

The historical digitization method is described in the parent README. The original marker-coordinate extraction log is unavailable. This audit visually checks the retained graph against representative scenario points and checks CSV arithmetic for all rows; it does not claim to have reproduced the original extraction pipeline or measured detector error.
