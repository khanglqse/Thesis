# Defense demo QA record

> **LEGACY ARCHIVE.** This QA record covers the older single-junction
> `results/defense_bundle/v1` replay. Its 34.5% PM and 320.7% normal-demand
> figures are not the current 53-signal Hai Chau evidence. For presentation,
> use [`haichau-bounded-demo.md`](haichau-bounded-demo.md) and
> `results/haichau_network_v2/demo-bounded`.

Date: 2026-09-07. Host: macOS, Chrome, SUMO 1.24 replay bundle.

| Check | Evidence | Result |
|---|---|---|
| Bundle load | Header showed `Verified bundle loaded` | Pass |
| Initial view | PM case, both panels at 30:00 with visible vehicles and signals | Pass |
| Playback | At 10×, 30:00 advanced to 30:12 in about 1.2 wall seconds | Pass |
| Pause and seek | Paused and sought to 59:55; both panels updated together | Pass |
| Scenario switch | PM changed to Normal and reset both panels to 30:00 | Pass |
| Representative metrics | PM: 152.5 vs 76.3 vehicle-hours; Normal: 9.9 vs 15.3 | Pass |
| Aggregate labels | Explicit cumulative-queue metric and direction: PM −34.5% better; Normal +320.7% worse/use fixed time | Pass |
| Browser console | No warnings or errors after play, pause, seek, switch | Pass |
| Local entry load | `curl` completed in 0.0013 s on the test host | Pass |
| Remote dependencies | No `http://` or `https://` in HTML/CSS/JS | Pass |
| Replay integrity | Four replay hashes and exact frozen metrics checked | Pass |
| Unit tests | 21 Node replay tests passed | Pass |
| PPTX | ZIP integrity passed; all 15 rendered slides inspected | Pass |
| Fallback video | H.264, 1920×1080, 15.5 seconds | Pass |
| Projector rehearsal | Requires access to the defense room | Pending |

This supports readiness on the tested laptop. Repeat preflight after copying the frozen bundle.
