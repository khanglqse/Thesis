# Published Da Nang pilot data

`tran2025_peak_turning_movements.csv` transcribes Table 1 of Phan, Le and Nguyen (2025), “Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam,” DOI `10.3390/make7030065`.

Values are passenger-car-equivalent vehicles per hour for the signalized Nguyen Thanh Nghi–Cach Mang Thang 8–2/9 junction and sum to 6171 PCU/h. The article attributes the traffic volumes to the Da Nang Department of Transport (2022), gives PCU factors motorcycle 0.3, car 1.0, bus 2.0 and truck 2.5, and reports that directions not directly covered by two cameras were estimated from observed proportions. The article text available during this audit does not identify row-by-row which movements are directly observed and which are inferred, so every row carries the conservative mixed-provenance label. Refine it only from stronger source evidence before final data freeze.

This CSV is a transcription for reproducible analysis, not a claim that the underlying raw Department of Transport dataset is redistributed here. Keep the article citation and observation-status column in every derivative.

`phan2025_camera_hourly_digitized.csv` is a digitization of Figures 17 and 18 in the same article. It covers 07:00–18:00 on 2025-04-01 for the through and left-turn counting lines at Camera 01 and Camera 02. Marker centers were extracted from a 180-DPI rendering using the four plotted series colors, mapped through each chart axis, and rounded to the nearest 5 vehicles/hour. The uncertainty column is a conservative reading tolerance (±15 vehicles/hour, or ±30 when a plotted class is at least 500 vehicles/hour); it does not measure YOLO/SORT counting error. `derived_pcu_per_h` uses the article's factors: motorcycle 0.3, car 1.0, truck 2.5 and bus 2.0.

The digitized four-movement totals are 1255 vehicles/hour at 07:00, 2330 at the AM peak preset (08:00), 1395 at the normal preset (13:00), and 2400 at the PM peak preset (17:00). These are only the four observed camera lines, not the whole intersection. The final pipeline must keep that denominator in labels.
