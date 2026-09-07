# Da Nang thesis defense demo runbook

## Main path

1. Copy `results/defense_bundle/v1` to the presentation laptop and USB backup.
2. Double-click `launch_demo.command`. It opens port 8765, or tries through 8775 if occupied.
3. Confirm **Verified bundle loaded** and both panels show vehicles at 30:00.
4. Start with PM peak. Play at 10×, pause, and point to queue, pending, arrivals, and whole-episode vehicle-hours.
5. Explain that lower cumulative queue is better: the seed-12 representative is 50.0% lower, while the five-seed aggregate is 34.5% lower. The aggregate supports the PM-peak conclusion.
6. Change to Normal. Show that cumulative queue is 320.7% higher (worse) and explain why the deployable policy falls back to fixed time in light traffic.

## Fallback path

- Browser/server problem: open `fallbacks/demo-walkthrough.mp4` (15.5 s, H.264, 1920×1080).
- Video problem: open `fallbacks/result-summary.pdf` and move to slides 9–12.
- Final visual fallback: open `fallbacks/pm-peak.png`.

The replay needs Python 3 only for the local server. It needs no Internet, SUMO, checkpoint, package installation, or training.

## Five-minute script

- 0:00–0:35: identify the junction, observed date, four-movement scope, and replay mode.
- 0:35–1:45: play PM A/B and explain shared demand, time, and simulator seed.
- 1:45–2:35: compare the representative metrics and separate them from the aggregate result.
- 2:35–3:25: switch to Normal and show the known failure regime.
- 3:25–4:15: explain motorcycle `tau=1.2`, zero primary collisions, and pending-demand accounting.
- 4:15–5:00: conclude with demand-gated adaptation and the published fixed-time fallback.

## Defense-day preflight

- Run `python3 scripts/verify_defense_bundle.py` on the frozen copy.
- Put the laptop offline and launch the copied bundle.
- Connect the projector, select 1920×1080 where available, disable sleep and notifications, and connect power.
- Open the PPTX, browser, MP4, and PDF before the session.
- Rehearse the PM-to-Normal switch and fallback video.
