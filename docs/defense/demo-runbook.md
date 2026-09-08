# Da Nang thesis defense demo runbook

## 53-signal Hai Chau extension: release-gated path

This path uses only `results/haichau_network_v2`: a 53-signal **OpenStreetMap-derived Hai
Chau topology** with **synthetic network demand constrained by Da Nang evidence**. The
[JICA Tien Sa--Da Nang port study](https://openjicareport.jica.go.jp/pdf/12250627.pdf) and
[DaCRISS integrated-development study](https://openjicareport.jica.go.jp/pdf/12014940_02.pdf)
provide planning context only. They do not calibrate the 53 signal timings, routes, or flows.
Do not substitute any `results/haichau*` legacy row, checkpoint or replay into this namespace.

The extension has no performance or acceptance claim until
`scripts/verify_haichau_thesis.py` exits zero and its report says `"complete": true`.

The foundation/model pipeline must first provide a tracked or checksum-verified canonical
network manifest, a frozen 30-case split, CityFlow image digest and five
validation-eligible candidate checkpoint bundles for the selected
`neighbor_phase_ddqn` family at confirmatory seeds 12--16. Record their exact paths and hashes in
`results/haichau_network_v2/final/frozen-protocol.json`. Do not create that file from
placeholders.

The frozen protocol also records the ordered 53 agent IDs, hashes for both the executable
CityFlow roadnet and the viewer projection, the complete resolved config for every
controller, and checkpoint contracts for the selected learned controller at seeds 12--16. Each
checkpoint contract contains the observation schema version, feature order, normalization,
hidden size, action contract and compatible network hash. Its acceptance rules declare the
same five seeds, all three regimes, at least two matched demand units per regime, bootstrap
seed `20260908`, 10,000 samples, normal point limit 0, normal CI margin 5%, strict peak CI
upper limit 0 and maximum completion degradation 2%. Every case has a `demand_path` whose
bytes match its `demand_sha256`.

Commit the evaluation code before freezing the protocol. Record the full 40-character
`code_commit`, immutable `runtime_image` (`repository@sha256:...`), its inspected
`runtime_image_id`, and the path/hash of `docker/haichau-evaluation.Dockerfile`. The
Dockerfile `FROM` line must use that exact image. Preparation and verification require a
clean descendant checkout with no changes to code paths since `code_commit`; campaign
execution re-inspects the image and runs every controller command inside it with networking
disabled. A digest-shaped string that is absent from `docker image inspect` is rejected.
The release runner owns this Docker invocation; an injected Python executor is marked as
test-only and cannot pass the final audit. Release containers remain stopped after their
command exits. The runner starts each container detached, waits for its exit, and stores the
two streams returned by `docker logs` as canonical `stdout.log` and `stderr.log`. Docker
client or daemon diagnostics, including platform warnings, go in
`docker-cli-diagnostics.json` and never enter the container stderr hash. Each completed
status records the exact run/wait argv, container ID, execution Git head, inspected image
identity, exit code and hashes of all three records. The verifier calls
`docker container inspect` and `docker logs` itself, verifies the
retained container's image ID/reference, command, working directory, disabled network,
project mount and exit state, then requires its stdout JSON to equal the hashed config,
metrics and replay artifacts. Keep these containers until the final audit succeeds.

Use the freeze CLI only after the five confirmatory training runs are complete and
validation-eligible. First precompute one shared, validation-only fixed-time tuning
artifact; the launcher hash-binds it to every final run. Pilot seed `11` is used only to
select the preregistered schedule-rehearsal arm and is excluded from the confirmatory
campaign. Then launch the selected `neighbor_phase_ddqn` family for seeds `12` through
`16`, exactly 12 one-hour episodes per seed with validation at steps `4`, `8`, and `12`.
The launcher resumes by skipping only fully verified completed jobs and refuses partial,
ineligible, or hash-drifted outputs. The resulting index has exactly one learned controller
ID and seeds `12` through `16`; the controller configuration contains the three
deterministic baselines plus the selected learned family.

```sh
make haichau-precompute-final-baseline
make haichau-select-schedule-pilot
make haichau-train-final-campaign
python3 scripts/prepare_haichau_release_inputs.py
python3 scripts/prepare_haichau_viewer_network.py
```

The V3 schedule selector must succeed before final training. It binds the winning
rehearsal or no-rehearsal configuration and eligible checkpoint step to one immutable
decision identity. The launcher, release-input builder, freeze command, campaign, statistics
and final verifier all recheck that decision, selected YAML and SHA-256 binding. Freeze reads
validation evidence only; any test metric or held-out case reference in selection evidence
is rejected.

To select a different campaign parallelism, set `HAICHAU_FINAL_CONCURRENCY`; leave it at
the default `2` for the release path. The focused launcher test is available as
`make haichau-final-training-test`.

The freeze command reads only training/validation evidence, verifies the selected
checkpoint bundle, and creates the network manifest, case manifest, and protocol together.
It refuses an existing final directory, hash drift, a non-final/short run, or any
test-case reference in selection evidence.

```sh
PYTHONPATH=src python3 scripts/freeze_haichau_protocol.py \
  --manifest results/haichau_network_v2/experiment-manifest.json \
  --viewer-network results/haichau_network_v2/release-inputs/viewer-network.json \
  --controller-configs results/haichau_network_v2/release-inputs/final-controller-configs.json \
  --training-index results/haichau_network_v2/release-inputs/training-index.json \
  --runtime-image registry.example/traffic-rl@sha256:IMMUTABLE_IMAGE_DIGEST
```

Prepare the immutable run set from the frozen case manifest, then execute it. Every
controller command in the case manifest must run a fresh evaluation and print its result
JSON on the final stdout line.

```sh
PYTHONPATH=src python3 scripts/run_haichau_campaign.py \
  --protocol results/haichau_network_v2/final/frozen-protocol.json \
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
PYTHONPATH=src python3 scripts/build_haichau_thesis_artifacts.py \
  --record-release-only
```

The first artifact command replaces its generated directory, so a table from an older
summary cannot survive. The final command records the hashes of the summary, generated
manifest, thesis source and compiled PDF. Run the project verifier again after any source,
figure, table or PDF change.

Choose one matched tuned-fixed/DDQN pair for each of `normal`, `am_peak` and `pm_peak`.
First generate the three fallback files. This command refuses all legacy single-junction or
SUMO evidence, verifies the frozen network/summary/thesis hashes, renders a walkthrough from
the final matched replays, then decodes all generated media. Its provenance sidecar is retained
with the staged media; do not substitute manually made media.

```sh
PYTHONPATH=src python3 scripts/build_haichau_demo_fallbacks.py \
  --output results/haichau_network_v2/demo-fallbacks
```

Export all six run IDs with the complete validated fallback directory. The exporter reads
`fallback-provenance.json`, copies it with the three media files, and rejects any six IDs that
do not exactly match its predeclared walkthrough order. Do not pass fallback files one by one.

`NORMAL_FIXED`, `NORMAL_DDQN`, `AM_FIXED`, `AM_DDQN`, `PM_FIXED`, and `PM_DDQN`
below are deliberate placeholders. Replace them only with exact run IDs from the verified
frozen campaign. A command containing any placeholder is preparation documentation, not a
valid demo export and not thesis evidence.

```sh
PYTHONPATH=src python3 scripts/export_haichau_replays.py \
  --network results/haichau_network_v2/release-inputs/viewer-network.json \
  --run-id NORMAL_FIXED --run-id NORMAL_DDQN \
  --run-id AM_FIXED --run-id AM_DDQN \
  --run-id PM_FIXED --run-id PM_DDQN \
  --fallback-dir results/haichau_network_v2/demo-fallbacks
PYTHONPATH=src python3 scripts/serve_haichau_demo.py \
  --port 8080 --port-fallback-count 10
```

The launch command requires the complete project verifier to pass before binding only to
`127.0.0.1`; it refuses an incomplete, legacy, stale or hash-drifted v2 bundle. It tries
ports `8080` through `8090` and prints the exact local URL it bound. Disconnect the network,
open that URL, and confirm **Verified bundle loaded**. Exercise play/pause, seek, all three
regimes, and node selection. The browser console must have no warning or error.

### Portable presentation copy

After the canonical launch and verifier have passed, create the laptop/USB copy from that
canonical bundle. The packager never accepts an arbitrary replay directory and refuses to
overwrite an existing destination.

```sh
PYTHONPATH=src python3 scripts/package_haichau_demo.py \
  --output results/haichau_network_v2/demo-portable
```

Copy the resulting `demo-portable` directory as one unit. On the presentation laptop,
double-click `launch_demo.command`, or run `python3 launch_demo.py --no-browser` from inside
that directory. The portable launcher uses Python's standard library only, rechecks every
asset hash listed in `manifest.json`, binds only to `127.0.0.1`, and tries ports `8080`
through `8090`. It does not contact a network, run CityFlow, load a checkpoint, or install
packages. The terminal prints the local URL when a port is chosen.

### What the viewer proves at presentation time

The **Verified replay provenance** panel is part of the 53-signal viewer. For the displayed
fixed-time and DDQN replay it shows the run ID, case ID, controller, checkpoint and contract
SHA-256, learning seed, terminal pending demand, and pending-demand integral. It also shows
the frozen acceptance status. The viewer shows `N/A` for any field absent from the exported
bundle; it does not infer a checkpoint, seed, acceptance decision, or pending-demand value.
Acceptance becomes `N/A` if the authenticated manifest and aggregate summary do not agree.

Every selected replay contains the exact `0, 5, ..., horizon` time grid. The exporter binds
the viewer network, campaign manifest and aggregate summary hashes; the final verifier
parses each replay again and compares it with the immutable source run. Every viewer node
must have finite coordinates and an explicit neighbor list containing only known node IDs.

Install `ffmpeg`, `ffprobe`, `pdfinfo` and `pdftoppm` on the verification host. The audit
fully decodes the PNG frame and every MP4 video frame with decoder errors promoted to a
failure, requires nonzero image dimensions and video duration, parses every PDF and renders
its first page. Readable container metadata or a valid-looking signature is insufficient.

Create the clean-checkout attestation with the repository command below. It first verifies
that the checkout is clean and that the frozen Git and Docker identities are real. It then
runs the exact host, integration, replay, paper-build and pre-attestation audit commands
itself. It records each argv, environment override, exit code, duration and tool-version
probe, writes stdout/stderr logs with SHA-256 hashes, and hashes the release artifacts. Do
not write `clean-checkout.json` by hand.

```sh
PYTHONPATH=src python3 scripts/attest_haichau_release.py
git add results/haichau_network_v2/verification
git commit -m "verify: attest Hai Chau release checkout"
PYTHONPATH=src python3 scripts/verify_haichau_thesis.py
```

The generator writes `verification_version: 3` and binds the pre-attestation commit, actual
Docker image ID, generator hash, exact command contract, logs, every campaign run-file hash
and release hashes. Commit
only the generated verification record and logs after it exits zero. The production
generator has no injectable runner or command contract; its separate test capture path is
always labeled synthetic and ineligible. The final verifier requires that commit to descend
from the recorded checkout, rejects later changes outside the verification directory,
re-inspects Git and Docker, reads each release/run artifact from the attested Git commit,
and then directly re-runs all five release commands. The pre-attestation audit uses
`--skip-clean-checkout --no-write` internally to avoid a circular record dependency.

The extension is release-ready only when the final command exits zero and its report has
`"complete": true` with no failed gates.

### 53-signal fallback order

1. If the browser or local server fails, open `fallbacks/demo-walkthrough.mp4`.
2. If video playback fails, open `fallbacks/result-summary.pdf`.
3. If the PDF viewer fails, open `fallbacks/network-overview.png`.

All three files must appear in the demo manifest, pass its SHA-256 check and decode with
nonzero pages, dimensions or duration as appropriate.

### Five-minute 53-signal defense script

- **0:00--0:35 — Scope first.** State that the map has 53 OSM-derived controlled signals
  in Hai Chau. The routes, flows and signal plans are synthetic and constrained by Da Nang
  evidence; the experiment tests scalability and coordination, not measured district
  performance.
- **0:35--1:10 — Evidence contract.** Show **Verified bundle loaded** and the **Verified
replay provenance** panel. Read the shown acceptance status, run/case IDs, controller,
checkpoint digest, learning seed, and pending-demand fields; distinguish `N/A` from evidence.
State the 30-case split (9 train, 6 validation, 15 held-out test) and the result of every
acceptance gate. If acceptance is negative, say so directly.
- **1:10--2:10 — Network behavior.** Open the matched normal tuned-fixed and neighbor-DDQN
  replays. Play them in sync, select one or two nodes, and explain queue integral, pending
  demand and completion. Describe what the replay shows without turning one case into the
  aggregate conclusion.
- **2:10--3:25 — Peak cases.** Repeat the comparison for AM and PM. Point to the aggregate
  queue-difference interval and completion degradation for each regime. Use the generated
  values shown by the bundle; do not memorize or insert values before the final campaign.
- **3:25--4:15 — Controller contribution.** Explain how the candidate scores valid phase
  rows using local movement features, fixed-schedule context and mean-pooled
  upstream/downstream queues. Clarify that this is neighbor-aware DDQN rather than learned
  CoLight-style graph attention.
- **4:15--5:00 — Claim boundary and takeaway.** State whether the predeclared normal
  non-inferiority, peak improvement and completion gates passed. Conclude only at the level
  supported by that status. Finish with the empirical single-junction anchor as the source
  of real camera-count evidence and identify measured district demand/signal plans as future
  work.

### 53-signal defense-day preflight

1. Run `PYTHONPATH=src python3 scripts/verify_haichau_thesis.py` from the clean frozen copy
   and confirm exit zero plus `"complete": true` in the newly written report.
2. Check that the six displayed run IDs equal the selected IDs in the demo manifest and that
   none of the uppercase placeholders above remains in an executed command or manifest.
3. Disconnect the Internet, start the local server, and exercise all three regime switches,
synchronized playback, seeking, node selection, and the provenance panel. Confirm it reports
the selected replay IDs and acceptance status rather than manually memorized values.
4. Create and test the `demo-portable` folder on a second local directory or USB copy. Confirm
`launch_demo.command` reports a loopback URL if port 8080 is already occupied.
5. Open `fallbacks/demo-walkthrough.mp4`, `fallbacks/result-summary.pdf`, and
`fallbacks/network-overview.png` locally before the session.
6. Rehearse both outcomes: an accepted candidate and a scientifically valid negative
result. The verbal conclusion must match the generated acceptance status.

### Vehicle accounting shown in the demo and thesis

The fixed-time tuning artifact records queue-objective schema `2`: network queue is
per-step waiting, entry pending is due-but-not-inserted, and future departures are
unreleased and excluded. Its vehicle accounting is `scheduled = due + unreleased`,
`due = inserted + pending`, and `inserted = arrived + running + removed`. Completion
is `arrived / scheduled`; insertion is reported separately. Pending means scheduled demand
that has not entered the network. Running and removed vehicles remain separate censored
categories. Only due vehicles held outside an entry lane count as pending; future
departures are unreleased. The metric bundle reports the pending-demand integral, so boundary blocking
cannot disappear into the departure denominator.

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
