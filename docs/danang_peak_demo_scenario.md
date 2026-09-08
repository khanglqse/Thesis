# Demo scenario `danang_peak` — archived synthetic CityFlow scenario

> **ARCHIVED LEGACY DEMO — NOT V2 THESIS EVIDENCE.** The topology is OSM-derived and
> this scenario's flows, vehicle mix, and volume are synthetic assumptions. Planning figures
> may provide context, but they do not calibrate this Hai Chau demand. Do not present these
> counts as observed or as a validated district slice.

## The three different "vehicle numbers" (do not conflate them)

| Quantity | Da Nang value | Meaning |
|---|---|---|
| **Registered fleet** | ~1,000,000 motorbikes + ~200,000 cars | Vehicles *owned* in the city (mostly parked at any instant) |
| **Concurrent in circulation at peak (city-wide)** | **~100,000–200,000** | Vehicles actually *moving on all city roads* at rush hour. Source: Ton et al., 2024 (JST-UD 22(6B)) — per the thesis author's reading of the full text; a city-wide, all-roads figure. |
| **Concurrent on our sub-network** | **~6,900** (sim, at peak of the 300-step run) | Vehicles on the **Hai Chau arterial corridor (53 signals, ~1,100 road segments, a few km)** — a realistic *slice* of the city-wide 100k–200k, since this is one central district, not all ~1,000+ km of Da Nang roads. |

**Why the demo is not "1.2M vehicles":** 1.2M is the *fleet*, not the *concurrent* count. Even
city-wide, only ~100k–200k circulate at peak; on a few km of central arterials only a few
thousand can physically be present at once (more would stack bumper-to-bumper). Our sim reaches
**~6,900 concurrent** on the sub-network and injects **~432,600 vehicle-trips over the simulated
hour** — the right order of magnitude for a busy central corridor.

## What is faithful vs abstracted

- **Faithful — vehicle composition:** the *observed flowing traffic* at peak is ~**70% motorbikes**
  (the registered fleet is 83% motorbike, but a larger share of cars is on the road during the
  commute peak). We set `motorbike_ratio = 0.70` (realized ~72%) to match the observed mix.
- **Faithful — peak density:** demand tuned so ~6,900 vehicles are concurrent at peak, a realistic
  slice of the city-wide 100k–200k.
- **Abstracted (stated honestly):** we model the Hai Chau **arterial sub-network** (53 signals), not
  all of Da Nang; CityFlow is lane-disciplined (no true motorbike sub-lane filtering); the control
  question is the *volume-to-capacity ratio* at the arterial signals, not the city-wide headcount.
  This is standard TSC methodology (representative sub-network + calibrated demand).

## Files
`data/danang/roadnet_danang_peak.json`, `flow_danang_peak.json` (600 route-flows, interval 5 s,
84.3% motorbike); replays via `run_comparison.py danang_peak`; demo preset in
`frontend/demo-presets.js`; the demo clip uses the **saturated window (steps 180–300)** so
~6,900 vehicles are on screen. Citation: `DaNangTraffic_MOT2024` in `paper/references.bib`.
