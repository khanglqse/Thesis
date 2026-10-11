# Thesis evidence ledger — 2026-09-23 (updated 2026-10-11)

This ledger is the current interpretation of the retained evidence. It supersedes conflicting source descriptions in older research notes. A checksum proves file identity; it does not prove field validity. An arithmetic audit pass does not mean that the strict release, independent confirmation, or university assessment has passed.

Recalculate: `python3 scripts/audit_thesis_evidence.py`. The output [thesis-evidence-audit.json](thesis-evidence-audit.json) lists source-file SHA-256 values, calculation checks, rejected checkpoint selections, and the current strict verifier response.

[Review verification](thesis-review-verification.md) records the commands, PDF/browser inspection, and an in-memory mutation check of the audit.

## 1. External data: source, extraction, permitted claim

The [archived publisher PDF](../../datasets/danang_published/sources/phan2025_make7030065.pdf) is Phan, Le and Nguyen (2025), DOI [10.3390/make7030065](https://doi.org/10.3390/make7030065). [Acquisition record and exact locators](../../datasets/danang_published/sources/README.md) retain its URL, date, license, and checksum. Page numbers below are printed article pages.

| ID | Input / claim | Exact source | Local evidence and transformation | Limit |
|---|---|---|---|---|
| E01 | Site and 2/2/3/3 approach lanes | p. 7; Table 1 p. 8; Figure 12 p. 17 | Isolated SUMO geometry in `results/research_pilot/generated/danang_isolated_published.net.xml`; bearings/build details in `build-manifest.json` | 300 m approaches are a modelling choice; no independent geometry survey |
| E02 | Historical fixed cycle 103 s | p. 7 and Figure 4 p. 8 | 32+7+28+7+22+7 seconds | Does not establish current field timing |
| E03 | 12 turning values, 6,171 PCU/h | Table 1 p. 8; attribution on p. 7 | `datasets/danang_published/tran2025_peak_turning_movements.csv`; each direction checked against the table | Underlying 2022 authority data and ref. 33 not obtained; row-level measurement status unknown |
| E04 | One-day camera profiles | p. 16 date/window; Figures 17–18 p. 20 | `datasets/danang_published/phan2025_camera_hourly_digitized.csv`: 48 rows, four movements, labels 07:00–18:00 | Approximate graph readings; four directions only; no raw detector export |
| E05 | 2,330 / 1,395 / 2,400 veh/h | Derived from E04 at 08:00 / 13:00 / 17:00 | Sum car+motorcycle+truck+bus over four movement rows at each label | These precise integer sums describe the retained rounded CSV, not exact field counts |
| E06 | PCU factors 0.3 / 1 / 2 / 2.5 | p. 19 | Motorcycle/car/bus/truck weighted sum, checked on all 48 rows | PCU is not another observed vehicle series to add to raw classes |
| E07 | Partial coverage, inferred other directions | pp. 16, 20–21 | Explicit boundary on camera-derived demand | Applies to 2025 camera expansion; does not prove which 2022 Table 1 rows were estimated |
| E08 | Raw data unavailable publicly | Data Availability Statement p. 23 | Archived source statement | This thesis did not collect the original camera data or acquire the authority raw data |
| E09 | 53-signal topology | `datasets/haichau_network_v2/provenance.json`, source OSM/SUMO artifacts and `phase-contract.json` | `roadnet.json`, topology normalization, source hashes and control-agent mapping | Original OSM retrieval date/tool versions unrecorded; inferred signal plans are not field plans |
| E16 | Public-camera YOLO counts (Tay Cau Rong, 2026-07-11 17:16–17:31) | YouTube `31Fhtgcq_fc`, channel @0511.VietNam; overlay date 11 Jul 2026 (title says 1/07/2026) | `results/camera_counts/caurong_20260711_1716/` (`meta.json`, `entries_exits.csv`, `only_car/`), realtime check `realtime_check_m1280_s4/timing.json`; thesis §3.6, audit-bound | Feasibility only: no hand count, far-field motorcycles under-counted, pedestrian/bicycle classes folded into motorcycle; one camera, 15 min; no simulator input |
| E17 | Green-wave context (Tran & Phan 2007) | UDN record https://scv.udn.vn/trantrungviet/BBao/5864: Tạp chí Cầu Đường Việt Nam no. 10/2007, pp. 23–28 | Abstract only | Local framing only; no timing value or count; do not identify its Phan Cao Thọ with the 2025 author |
| E10 | District demand | `configs/haichau_network_v2.yaml`, generator code and `results/haichau_network_v2/experiment-manifest.json` | 1,290 route families partitioned 644/323/323; 500 route streams per case; 30 cases | OD, routes, scale, vehicle parameters and 90% motorcycle share are synthetic |

### Source discrepancies and uncertainty

- **Street name:** source p. 7 says `Nguyenthanhnghi`; Table 1, Figure 12 and reference 33 say `Lethanhnghi`. The manuscript uses **Le Thanh Nghi–Cach Mang Thang 8–2/9, Hoa Xuan bridge approach**, records both spellings and uses compass movement IDs. The legacy `ntn_cmt8_29` ID is not evidence of a second site.
- **Table label:** the frozen CSV's `published_aggregate_mixed_observed_estimated` is a conservative project classification. Read it as “published aggregate with unverified row provenance.” Do not assert that the article proves specific 2022 rows were estimated.
- **Time:** collection is described as 06:00–18:00; twelve retained graph labels are 07:00–18:00. The legacy column `hour_start` does not resolve start-versus-end-of-window semantics.
- **Digitization:** original extraction-coordinate logs are not retained. The PDF permits inspection; this audit visually spot-checked representative scenario points and verified all CSV arithmetic. The ±15/±30 veh/h allowances are project reading tolerances, not author-reported detector errors, not confidence intervals, and not propagated experimental uncertainty.
- **Site calibration:** no independently measured headways, saturation flow, queue lengths, travel times, pedestrian demand or full-turn counts validate the simulator. Use “camera-profile-informed reconstruction.”

## 2. Experimental results and calculation paths

### E11 — Single-junction SUMO

Inputs: `configs/danang_pilot.yaml`, `results/danang_protocol_v1/experiment-manifest.json`, the isolated network, generated route files and the camera CSV. Code: `scripts/prepare_danang_protocol.py`, `scripts/train_danang_sumo.py`, `scripts/evaluate_danang_protocol.py`, `scripts/summarize_danang_protocol.py`.

Raw retained results: `results/danang_protocol_v1/evaluation/*.json`. Eight files contain 15 one-hour cases each: 5 learned seeds × 15 = 75 learned runs; 3 baselines × 15 = 45 baseline runs; **120 total**. The prior manuscript count of 105 was wrong. Zero collisions and zero emergency-braking events are recorded in this set.

| Scenario | Published fixed, xe·giờ | Dueling DDQN, xe·giờ | Relative queue change | Paired absolute 95% interval, xe·giờ |
|---|---:|---:|---:|---|
| Normal | 9.8628 | 41.4955 | +320.7255% | [7.5953, 56.1433] |
| AM | 79.2042 | 78.4083 | −1.0049% | [−9.4685, 8.4944] |
| PM | 152.6676 | 99.9714 | −34.5169% | [−69.5464, −35.3436] |

Primary metric: integrate stopped network vehicles plus due-but-not-inserted vehicles every second, divide vehicle-seconds by 3,600. It is not mean waiting time per vehicle. Average matched demand cases within training seed before resampling seeds. AM's interval includes zero, so neither superiority nor equivalence is established.

**Development-informed test:** a held-out failure prompted motorcycle headway `tau` 1.0→1.2. Old models were discarded and rerun, but reuse of the cases does not restore an untouched test. See `results/research_pilot/calibration/tau_sensitivity.json` and `docs/research/pilot-calibration.md`.

### E12 — SUMO demand sensitivity

`results/danang_protocol_v1/sensitivity/*.json` contains 120 one-hour records: six controller/seed configurations × four scales × five realizations. Scales are 0.75/1.00/1.25/1.50. There are zero collisions and four emergency-braking events. The 30 outcomes at scale 1.00 repeat the primary AM outcomes; do not add them as 30 independent new conditions. Even the base scale is simulated departures informed by approximate published counts, not recorded trajectories.

### E13 — Four-controller CityFlow matrix

`results/haichau_network_v2/final15-controller-matrix-summary.json` contains fifteen matched cases. `final15-controller-matrix-provenance.json` binds seed 14, episode 4, source campaigns, runtime and checkpoint identities. Local source campaigns retain raw metrics; large directories are Git-ignored. The quick runner reserializes unchanged full-hour flow JSON with sorted keys, indentation and a final newline. Thus source `flow_sha256` differs from run `demand_sha256`; the audit reconstructs the run serialization and checks its hash, rather than mistaking formatting changes for different demand.

| Controller | Sum queue, xe·giờ | Reduction versus fixed |
|---|---:|---:|
| Tuned fixed | 8,339.4300 | 0% |
| Max-Pressure | 6,347.0022 | 23.8917% |
| Hysteretic MP | 6,739.1275 | 19.1896% |
| Residual DDQN, seed 14 step 4 | 7,829.2522 | 6.1177% |

The DDQN mean of per-case reductions is 3.5318% for AM and 8.8621% for PM. The ratio of regime queue sums gives 3.4769% for AM and 10.3877% for PM. These are different aggregation definitions, not conflicting measurements. Report the denominator with each number. Max-Pressure is strongest in this matrix.

The demo's PM interval is a case bootstrap on **relative changes**: [−17.5119%, −1.6213%], five demand cases for policy seed 14. Its old `vehicle-seconds` label was wrong and has been corrected to percent; it must not be confused with the five-learning-seed post hoc gate interval. Demo source-controller and queue-snapshot wording were also corrected, with refreshed asset hashes and unchanged replay measurements.

`final15-seed14-secondary-summary.json` shows completion 66.92%→67.98%, but completed-trip travel time 737.81→743.26 s and spillback 1,432.33→1,497.53 lane-seconds. Queue reduction does not establish improvement in every outcome. Incomplete trips make completed-trip travel time selective.

### E14 — Post hoc PM-only gate

Calculation inputs: each `final15-regime-gated-seed*-summary.json`; calculation code `scripts/summarize_regime_gated_direct.py`; aggregate `final15-regime-gated-direct-multi-seed-summary.json`. The independent audit recomputes using the retained four-controller baseline rows, not the original summarizer's functions.

For each seed: `100 × (sum fixed queue − sum gated queue) / sum fixed queue` over fifteen reset one-hour cases. Average the five resulting percentages. The retained JSON field `derived_full_day_improvement_pct` is a legacy name for this **pooled-case** quantity; it is not a continuous 24-hour simulation.

| Seed | Original validation selection | Gate pooled reduction | PM cell regressions |
|---|---|---:|---:|
| 12 | Selected, step 8 | 2.3623% | 3/5 |
| 13 | **Rejected**; diagnostic step 12 used | 5.6222% | 1/5 |
| 14 | Selected, step 4 | 5.1079% | 1/5 |
| 15 | Selected, step 8 | 1.0261% | 3/5 |
| 16 | **Rejected**; diagnostic step 4 used | 3.2732% | 2/5 |

Mean **3.4783%**, bootstrap 95% **[2.0100%, 4.9467%]** from five seed effects, 10,000 resamples, RNG seed 20260913. Of 75 seed-case cells, 50 normal/AM cells tie by construction; among 25 PM cells, 15 improve and 10 regress. Seed 13/16 coverage combines normal/AM fixed replays with PM residual replays. Some compact rows omit `horizon_steps`; a 3,600-second summary header does not independently prove each raw run's horizon.

The gate was chosen after inspecting test behavior. Its apparent positive interval is conditional and does not correct selection bias. Seeds 13/16 do not become eligible merely because the gate helps. Exact selection files and resolved configs are copied byte-for-byte into [the evidence snapshot](evidence-snapshot-2026-09-23/snapshot-manifest.json). Seed 13's diagnostic step 12 fails peak-regime queue noninferiority and per-case completion; seed 16's step 4 fails the same categories.

### E15b — Baseline Monte-Carlo (added 2026-10-11)

`results/danang_baseline_mc/` (`runs.jsonl`, `summary.json`): 9,000 paired SUMO runs, 1,000 realizations per regime (demand seed 100000+k, SUMO seed 200000+k, disjoint from the protocol), three non-learning baselines. Fixed < raw MP in 3,000/3,000 and < hysteretic MP in 2,999/3,000; hysteretic < raw MP 1,000 / 758 / 884 of 1,000 (normal / AM / PM). Realizations of one observed profile, not independent days. **Collisions were not recorded** in this batch (script key bug, fixed afterwards); make no safety claim from it. Thesis §6.3, audit-bound.

### E15 — Actual model identity

The SUMO agent is dueling Double DQN with a three-step return. The CityFlow residual agent is `ResidualDDQN`, based on `PhaseScoringDDQN`: two 64-unit hidden layers, shared scalar score, 27 macro features, **no dueling heads**, semi-Markov macro target, raw network-plus-pending queue reward scaled by 100,000 for critic units. The snapshot of seed 14's resolved config and contract is the evidence for the reported model; later v3c/v3d YAMLs do not retroactively change that model.

Normal/AM gating uses an externally declared regime. No learned traffic-regime classifier, field sensor reliability, continuous AM-to-PM transition, or causal neighbor-feature benefit has been established.

## 3. Bibliographic source identity

[bibliography-metadata-audit.json](bibliography-metadata-audit.json) records checks for all 71 bibliography entries (re-screened 2026-10-11). Fifty-one DOI/title pairs match Crossref metadata; cited author surnames and publication years were also screened. Nineteen other entries have publisher, proceedings, author-repository or official-report identity evidence. These checks establish source identity, not verification of every full-text literature claim.

The SURTRAC entry was corrected against the [CMU conference record](https://publications.ri.cmu.edu/smart-urban-signal-networks-initial-application-of-the-surtrac-adaptive-traffic-signal-control-system): the title is *Smart Urban Signal Networks: Initial Application of the SURTRAC Adaptive Traffic Signal Control System*, ICAPS 2013, pp. 434–442; Xiao-Feng Xie's name was also corrected. The CMU PDF has a 2014 copyright line; the citation follows the repository's 2013 conference record. JICA documents are planning context only. Their report identities do not establish current traffic counts.

The original Webster (1958) report was not obtained. [FHWA's literature review](https://ops.fhwa.dot.gov/arterial_mgmt/rpt/sig_tim_proc/sect_4.htm) corroborates its bibliographic identity, and [FHWA's timing guide](https://ops.fhwa.dot.gov/publications/signal_timing/03.htm) describes the classical equation. This is explicitly agency secondary confirmation, not a claim of inspecting the original. The thesis uses it as historical background; it supplies no experimental input or measured result.

## 4. What is resolved and what remains open

| Question | Current resolution | Additional evidence needed for a stronger claim |
|---|---|---|
| Where did inputs come from? | Source PDF, page locators, CSVs and hashes retained | Original authority/camera exports for raw-data claims |
| Are headline calculations reproducible? | Arithmetic audit reconciles retained rows and summaries | Full raw-run release for end-to-end reruns |
| Are both simulators using the same model? | No; manuscript now identifies each architecture/configuration | None for this descriptive distinction |
| Did all five residual seeds pass selection? | No; three selected and two rejected, explicitly disclosed | A new frozen selection/confirmation study |
| Does RL beat all baselines? | No; pressure baselines outperform it on this network matrix | No change required to report the negative finding honestly |
| Is the PM gate independently confirmed? | No; exploratory post hoc result | Freeze the gate before new uninspected demand tests |
| Is the current 420-episode robustness appendix completed? | No; design only, not current-controller results | Run an appropriately frozen new robustness study |
| Is this continuous full-day operation? | No; separate one-hour cases | Time-varying continuous runs with regime transitions |
| Can the model claim field safety or Hai Chau congestion reduction? | No; scope restricted to simulations | Independent multi-day field calibration and traffic-engineering validation |
| Is the strict release complete? | No; fresh verifier response included in audit | Missing final protocol/campaign, valid selections, complete artifacts and clean-checkout reproduction |

For a future confirmation, write the new protocol before opening new results; retain all seeds and failed selections, define the fallback rule without test-based changes, include the pressure baselines, and use uninspected demand realizations. If the original selector still rejects a seed, report failure under that rule. Do not silently use a diagnostic checkpoint, rerun until a favorable seed appears, or relax thresholds after seeing the new test.

The thesis can defend an implementation, reconstruction, and exploratory comparison with these limits. These documents do not claim that missing observations or an uncompleted experiment have been resolved by wording alone.
