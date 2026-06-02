# Time-Based Improvement Analysis — Waiting Time

*How the controllers compare on TIME, for the paper and report. Explains why mean
travel time is the wrong headline and total waiting time is the right one.*

## 1. Why mean travel time barely moves

CityFlow's `average_travel_time` averages over **all vehicles in the system**. On the
arterial Hai Chau network most vehicles spend most of their trip moving at free-flow
speed; only a fraction of their time is lost at signals. Averaging the freely-moving
majority with the queued minority **dilutes** the congestion signal, so every controller
lands within ~0.5% of the others:

| Scenario | Fixed-Time | DQN | Difference |
|---|---|---|---|
| Normal | 386.3 s | 384.1 s | 2.2 s/veh (0.6%) |
| Peak | ~386 s | ~384 s | ~2 s/veh |

This is a known property of the metric, **not** evidence that control does not help.

## 2. The right time metric: total waiting (delay) time

The time a controller actually saves is the time vehicles spend **stopped in queues**.
Integrating the number of waiting vehicles over time gives total waiting time in
**vehicle-hours**:

```
waiting_vehicle_hours = Σ_decisions ( queued_vehicles × action_interval ) / 3600
```

(`cumulative_wait_hours` / `plot_cumulative_wait_time` in `src/traffic_rl/eval/compare.py`.)

| Scenario (horizon) | Fixed-Time | DQN | Max-Pressure | DQN vs Fixed-Time |
|---|---|---|---|---|
| Normal (800 s) | 1029 veh-h | 868 veh-h | 820 veh-h | **−161 veh-h (−15.6%)** |
| Peak (1000 s) | 1368 veh-h | 1135 veh-h | 1044 veh-h | **−233 veh-h (−17.1%)** |
| Peak window only | — | — | — | **−20.0%** |

**Interpretation:** per simulated hour, the learned DQN removes ~160–230 vehicle-hours of
waiting versus Fixed-Time, and the saving grows during the rush-hour peak. Max-Pressure is
marginally better on queue; DQN matches or beats it on the pressure reward.

## 3. Figures (for paper / report)

- `results/<scenario>/cumulative_wait.png` — cumulative waiting time over time. The vertical
  gap between Fixed-Time (top) and a controller is the waiting time saved; annotated with the
  DQN saving. Peak scenario shades the rush-hour window.
- `results/<scenario>/queue_over_time.png` (peak: `queue_over_time_peak.png`) — instantaneous
  queue over time; Fixed-Time rises fastest during the surge.
- `results/<scenario>/comparison_metrics.png`, `training_curve.png` — bar chart and DQN
  learning curve.

## 4. Scenarios compared

| | Normal (`haichau`) | Peak (`haichau_peak`) |
|---|---|---|
| Demand | 500 flows, uniform interval 1.5 s | 120 background + 800 flows surging in steps 250–600 |
| Peak vehicles in network | ~11,990 | ~13,160 |
| Vehicle mix | 90% motorbikes | 90% motorbikes |

Regenerate: `scripts/build_peak_flow.py` (peak), `run_comparison.py haichau[_peak]`, then the
plot calls above. Headline metric for the thesis: **total / cumulative waiting time**, not
mean travel time.
