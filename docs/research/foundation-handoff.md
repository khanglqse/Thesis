# Foundation handoff to network, calibration and experiments

## Research question

Can a reproducible traffic-signal controller trained with independent demand splits reduce queue/delay under observed Da Nang peak demand, remain competitive with a tuned fixed plan and Max-Pressure, and generalize from an empirically calibrated junction to synthetic Hai Chau network stress cases?

## Scope selected from evidence

The empirical pilot is the signalized Nguyen Thanh Nghi–Cach Mang Thang 8–2/9 junction. Build it in SUMO 1.24 with the three-phase, 103-second plan and 12 movement volumes totaling 6171 PCU/h at peak published by Phan, Le and Nguyen (2025). Use the official sublane model for motorcycle lateral behavior and document every non-published geometry or behavior assumption.

The 53-controller Hai Chau CityFlow network remains the scale benchmark. It is an OSM-derived topology with synthetic random-walk demand. It tests computational scale, coordination and distribution shift; it does not validate city-wide observed demand.

## Inputs ready

- Audited source/results baseline and checksum manifest.
- Working CityFlow smoke recipe and native SUMO installation.
- Published peak turning movements and signal timing source.
- Required metric, seed, split and replay-provenance corrections.
- Existing parameter-shared DQN, Max-Pressure, Fixed-Time, replay viewers and tests.

## Implementation gates for T04–T06

1. Add a versioned case-manifest schema and validator using TDD.
2. Encode the published junction, phase links and turning volumes; verify movement totals and cycle timing from hand-derived fixtures.
3. Add raw/per-step cohort metrics and separate scheduled/inserted/arrived/active counts.
4. Calibrate motorcycle/car behavior and capacity against held-out quantities where available; otherwise call it demand-matched rather than fully calibrated.
5. Export one SUMO baseline pilot to the backend-independent replay contract and load it in the 2D viewer.
6. Measure pilot runtime. Only then allocate Core/Standard/Extended training budget.

## Experiment protocol to implement

Run Fixed-Time (published and validation-tuned), actuated if supported, Max-Pressure, parameter-shared DQN and a neighbor-aware DQN candidate. Tune on validation only. Use at least five learning seeds for RL and multiple demand/simulator seeds for every controller. Evaluate normal, AM peak, PM peak, demand scale, sensor-noise and incident cases where data semantics support them. Report per-run values, mean/median, uncertainty/effect size, learning curves, runtime and negative results.

## Known blockers that do not stop implementation

Raw multi-day Hai Chau counts, complete normal-hour turning counts and observed signal plans for 53 nodes are missing. These block a claim of city-wide empirical calibration, but they do not block the observed one-junction pilot, synthetic network benchmark, software corrections, training, thesis structure or defense bundle.

The next code task is the case manifest and metric contract. It must begin with failing behavioral tests and preserve all legacy result directories.
