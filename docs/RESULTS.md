# Results & Visualization

All visualization/reporting runs on the **host** (Python 3.13) — no Docker needed.

## Comparison dashboard (Streamlit)
```bash
PYTHONPATH=src streamlit run dashboard/app.py
```
Shows the metric comparison table, per-metric improvement vs Fixed-Time, the
training curves, and replay instructions for the `full` (105-intersection) and
`subarea` scenarios.

## CityFlow web replay
```bash
# 1) make browser-loadable demo replays (~120 steps each)
PYTHONPATH=src python3 scripts/truncate_replay.py full 120
# 2) serve the vendored CityFlow frontend
python3 scripts/serve_replay.py
```
In the browser, pick the roadnet (`data/danang/replay_roadnet_full.json`) and one
demo replay (`results/full/demo/replay_<controller>_demo.txt`). The full 760 MB
replays are too large for the browser; the truncated demos load smoothly.

## Chapter 4 (results write-up, English)
```bash
PYTHONPATH=src python3 scripts/export_chapter4.py full
```
Regenerates `docs/chapter4_results.md` from the real result files.
