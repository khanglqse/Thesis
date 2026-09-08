# Hai Chau Validation-Only Capacity Calibration Design

## Purpose and scope

The calibration workflow determines whether the synthetic Hai Chau demand is a
usable operating regime before expensive learning. It runs only the six cases
whose manifest split is `validation`; code must select those records before
opening any flow file. Outputs are diagnostic, cannot enter release evidence,
and never authorize held-out test evaluation.

## Stages

One CLI prepares or executes one immutable stage directory. `scale1` contains
the two 3,600-second Fixed-Time-30 normal probes and one seed-31 drain probe.
`ladder` contains Fixed-Time-30 normal-seed-31 probes at 0.25, 0.30, and 0.35.
`stage-d` requires one or more registered ladder scales and expands them over
all six validation cases and Fixed-Time-30 plus mask-corrected Max-Pressure.
The drain horizon defaults to 5,400 and may be explicitly changed to 7,200.

Scaled flows retain row count, route, vehicle template, end-of-bin boundary, and
the stream's relative offset inside the bin. The interval and offset are divided
by the scale factor, so lower rates remain staggered rather than bunching at the
bin boundary. Scheduled departures and free-flow-eligible counts are recomputed
from the materialized flow.

## Artifact and execution contract

Preparation verifies and hashes only selected validation flows, plus the source
manifest, training config, generator config, network, phase contract, CLI, and
library module. It writes a campaign manifest, one scaled flow, and one run
manifest per run before simulation. Identical files may be reused; differing
existing content is refused.

Execution resumes by skipping a completed run only after its result hash and run
manifest hash verify. Failed or interrupted runs retain status and may retry with
the same immutable inputs. Results contain 300-second metric snapshots, terminal
metrics, free-flow eligibility, individual gate outcomes, and a diagnostic
summary. Writes are atomic. The default CLI action is preparation; CityFlow runs
only with an explicit `--execute` flag inside the pinned Docker image.

## Metrics and decisions

The runner uses `NetworkMetricsObserver`, so queue accumulation includes both
network waiting and due vehicles held outside entry lanes. Each snapshot repeats
the full accounting counters and cumulative queue integrals. Pure functions
validate conservation and apply the exact pre-registered gates in
`docs/research/decision-log.md`. A stage-D scale passes only when both controllers
and both seeds meet all individual and aggregate requirements. No result is
marked release eligible, including a passing calibration.

## Testing

Unit tests use small temporary manifests and fake rollouts. They prove validation
selection never opens a missing test path, scaled flows preserve structure and
offsets, free-flow eligibility is exact, stage expansion is fixed, snapshots and
gates are evaluated correctly, and prepare/resume refuses hash drift or result
overwrite. CLI tests verify preparation is the default and execution is explicit.
