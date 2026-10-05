# Verification of the evidence corrections — 2026-09-23

This review corrected interpretation, provenance, manuscript text and demo labels. It did not rerun training or create new independent traffic observations.

| Check | Actual outcome |
|---|---|
| `python3 scripts/audit_thesis_evidence.py` | 63/63 checks passed; see `thesis-evidence-audit.json` for input hashes and scope |
| In-memory mutation of one camera CSV derived-PCU value | Audit failed `camera_derived_pcu_all_rows`; original file bytes remained unchanged |
| Independent SUMO interval recalculation | All three paired intervals matched: NumPy RandomState(20260907), 20,000 resamples of five seed effects, percentile 2.5/97.5 |
| `tectonic -k --keep-logs paper/thesis_danang.tex` | Exit 0, 57-page PDF; no undefined citations. Underfull text warnings and one 0.69 pt overfull paragraph remain; visual review found no clipping |
| PDF visual review | All 57 pages inspected through contact sheets; source description, demand figure, and evidence appendix inspected at higher resolution; corrected quotation marks re-rendered |
| `node --check results/haichau_network_v2/demo-visual/haichau_network_demo.js` | Exit 0 |
| Browser, guided PM frame at 1,085 s | Verified replay loaded; fixed queue 14, residual queue 1; text says 13 fewer queued vehicles at this moment; correct schedule-residual controller label |
| Browser, aggregate labels | Percent interval −17.5% to −1.6%, five cases for policy seed 14; separate post hoc five-seed analysis explained |
| Demo bundle hashes | All listed files match the updated manifest; replay measurement files were not changed |
| `git diff --check` | Exit 0 |
| Strict thesis verifier, `--no-write` | Exit 1, `complete: false`, 14 failed release gates; preserved in the evidence audit |

The auxiliary generic UI static audit was inconclusive: it flags undeclared native-select ownership and does not resolve event listeners bound from the external JavaScript. The reset action and corrected text were checked in the browser. This review does not claim comprehensive UI accessibility or design-system compliance.

The PDF, TeX, bibliography and audit script SHA-256 values match the final evidence audit. Bibliographic identity evidence is in `bibliography-metadata-audit.json`; the original Webster report remains unobtained. Independent confirmation, full raw-run distribution, and field calibration remain open as described in `thesis-evidence-ledger.md`.
