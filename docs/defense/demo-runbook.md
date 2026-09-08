# Da Nang thesis defense demo runbook

## 53-signal Hai Chau extension: release-gated path

This path uses only `results/haichau_network_v2`. Its demand label is **synthetic network
demand constrained by Da Nang evidence**. Do not substitute any `results/haichau*` legacy
row, checkpoint or replay into this namespace.

The foundation/model pipeline must first provide a tracked or checksum-verified canonical
network manifest, a frozen 30-case split, CityFlow image digest and five validation-eligible
checkpoint contracts for learning seeds 11--15. Record their exact paths and hashes in
`results/haichau_network_v2/final/frozen-protocol.json`. Do not create that file from
placeholders.

Prepare the immutable run set from the frozen case manifest, then execute it. Every
controller command in the case manifest must run a fresh evaluation and print its result
JSON on the final stdout line.

```sh
PYTHONPATH=src python3 scripts/run_haichau_campaign.py \
  --manifest path/to/frozen-case-manifest.json --prepare-only
PYTHONPATH=src python3 scripts/run_haichau_campaign.py
PYTHONPATH=src python3 scripts/run_haichau_campaign.py --verify-only
PYTHONPATH=src python3 scripts/summarize_haichau_campaign.py
```

Generate the paper evidence only after `summary.json` exists. The generator reads that
summary and refuses unsupported claims. A negative acceptance result must remain visible.

```sh
PYTHONPATH=src python3 scripts/build_haichau_thesis_artifacts.py
tectonic paper/thesis_danang.tex
```

Choose one matched tuned-fixed/DDQN pair for each of `normal`, `am_peak` and `pm_peak`.
Export all six run IDs with fallbacks made from the same frozen evidence:

```sh
PYTHONPATH=src python3 scripts/export_haichau_replays.py \
  --network path/to/verified-53-signal-viewer-network.json \
  --run-id NORMAL_FIXED --run-id NORMAL_DDQN \
  --run-id AM_FIXED --run-id AM_DDQN \
  --run-id PM_FIXED --run-id PM_DDQN \
  --fallback-mp4 path/to/demo-walkthrough.mp4 \
  --fallback-pdf path/to/result-summary.pdf \
  --fallback-png path/to/network-overview.png
python3 -m http.server 8765 --directory results/haichau_network_v2/demo
```

Open `http://127.0.0.1:8765/` with the network disabled. Confirm **Verified bundle
loaded**, then exercise play/pause, seek, all three regimes and node selection. The browser
console must have no warning or error.

Repeat the documented tests, paper build, demo launch and audit from a clean checkout that
contains only tracked files plus the checksum-verified release inputs. Record the tested
commit, commands, tool versions and wall time in
`results/haichau_network_v2/verification/clean-checkout.json`; set `passed` to true only
after those commands actually succeed. Then run:

```sh
make test
make cf-test
npm run test:replay
PYTHONPATH=src python3 scripts/verify_haichau_thesis.py
```

The extension is release-ready only when the final command exits zero and its report has
`"complete": true` with no failed gates.

### 53-signal fallback order

1. If the browser or local server fails, open `fallbacks/demo-walkthrough.mp4`.
2. If video playback fails, open `fallbacks/result-summary.pdf`.
3. If the PDF viewer fails, open `fallbacks/network-overview.png`.

All three files must appear in the demo manifest and pass its SHA-256 check.

## Legacy single-junction defense bundle

The remainder of this runbook applies to the existing `results/defense_bundle/v1`
evidence. Its observed-date and representative percentages are legacy claims and must not
be presented as results of the 53-signal extension.

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
