# Published Da Nang pilot data

The source is Phan, Le and Nguyen (2025), DOI [10.3390/make7030065](https://doi.org/10.3390/make7030065). An unmodified publisher PDF, checksum, access date and exact page/table/figure locators are retained in [sources/README.md](sources/README.md).

## Published movement table

`tran2025_peak_turning_movements.csv` transcribes **Table 1, page 8**. The legacy filename does not identify the authors: the correct authors are Phan, Le and Nguyen. Its twelve movement values sum to **6,171 PCU/h**. Page 7 attributes these volumes to the Da Nang Department of Transport in **2022** and cites reference 33, a 2024 planning document. That underlying document and raw authority dataset have not been independently obtained.

The source is inconsistent about the street name: page 7 uses `Nguyenthanhnghi`, while Table 1, Figure 12 and reference 33 use `Lethanhnghi`. The thesis uses **Le Thanh Nghi–Cach Mang Thang 8–2/9, Hoa Xuan bridge approach**, with NW/SE/NE/SW movement identifiers. The internal site ID is retained to preserve existing artifact identity.

Every CSV row retains the historical project label `published_aggregate_mixed_observed_estimated`. Interpret this conservatively as **published aggregate; row-level measurement provenance unverified**. The article's explicit estimation statement concerns unobserved directions in the 2025 camera reconstruction (pages 16, 20–21); it does not prove that individual 2022 table rows were estimated. This table is used for context and modelled full-intersection stress, not as raw detector data.

## Digitized camera profiles

`phan2025_camera_hourly_digitized.csv` contains **48 rows**: four camera movement lines at twelve plotted hourly labels, 07:00–18:00, on **2025-04-01**. Figures 17–18 on page 20 supply the four class series. The article describes collection from 06:00–18:00 on page 16. The `hour_start` column preserves the plot label; the exact hourly-window convention is not independently established.

The historical extraction description records a 180-DPI rendering, colored marker extraction, axis mapping, and rounding to five vehicles/hour. The original marker-coordinate extraction log is unavailable. The retained CSV is therefore an approximate transcription, not raw detector output. The ±15/±30 vehicles/hour column is a project reading tolerance. It is neither YOLO/SORT accuracy nor a 95% confidence interval and has not been propagated through the controller experiments.

`derived_pcu_per_h` uses the factors on **page 19**: motorcycle 0.3, car 1.0, truck 2.5, bus 2.0. PCU values are derived from the class counts and are not additional observations. Sum only the four vehicle-class columns when reporting vehicles/hour; do not also add the PCU column.

| Plot label | Sum of four movements, veh/h | Scenario |
|---|---:|---|
| 08:00 | 2,330 | AM peak |
| 13:00 | 1,395 | Normal |
| 17:00 | 2,400 | PM peak |

These sums cover four camera lines at **one junction on one date**. They are not whole-junction counts, independently observed survey days, district OD, or real-time data collected by this thesis. The source article's Data Availability Statement (page 23) says the underlying data require a request.

## Recheck

From the repository root:

```sh
python3 scripts/audit_thesis_evidence.py
```

The command checks the source checksum, the twelve transcribed movement values, all PCU conversions and selected scenario sums. See [the evidence ledger](../../docs/research/thesis-evidence-ledger.md) for result calculations, source boundaries, selection failures and unresolved evidence.
