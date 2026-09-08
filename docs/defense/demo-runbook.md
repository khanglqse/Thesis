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
network manifest, a frozen 30-case split, CityFlow image digest and five validation-eligible
candidate checkpoints for learning seeds 11--15. Record their exact paths and hashes in
`results/haichau_network_v2/final/frozen-protocol.json`. Do not create that file from
placeholders.

The frozen protocol also records the ordered 53 agent IDs, hashes for both the executable
CityFlow roadnet and the viewer projection, the complete resolved config for every
controller, and checkpoint contracts for both learned controllers at seeds 11--15. Each
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

Use the freeze CLI only after the ten learned training runs are complete and
validation-eligible. Train both controller families for each required seed, then create
the release inputs and verified viewer geometry. The input scripts refuse an incomplete,
ineligible, drifted, or mixed-duration training set. The resulting index has exactly the
two learned controller IDs and seeds `11` through `15`; the controller configuration has
the resolved evaluator config and entries for all five controllers.

```sh
for seed in 11 12 13 14 15; do
  make haichau-train-final LEARNING_SEED="$seed"
  make haichau-train-legacy-final LEARNING_SEED="$seed"
done
python3 scripts/prepare_haichau_release_inputs.py
python3 scripts/prepare_haichau_viewer_network.py
```

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
Export all six run IDs with fallbacks made from the same frozen evidence:

```sh
PYTHONPATH=src python3 scripts/export_haichau_replays.py \
  --network results/haichau_network_v2/release-inputs/viewer-network.json \
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

### Vehicle accounting shown in the demo and thesis

`scheduled = inserted + pending`, and `inserted = arrived + running + removed`. Completion
is `arrived / scheduled`; insertion is reported separately. Pending means scheduled demand
that has not entered the network. Running and removed vehicles remain separate censored
categories. The metric bundle also reports the pending-demand integral, so boundary blocking
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
