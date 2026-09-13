# Hai Chau bounded demo

This is the presentation path for the currently completed 53-signal evidence.
It is a portable replay of the bounded 15-case matrix and does not require
CityFlow, Docker, package installation, or Internet access.

## Launch

From the repository root:

```sh
cd results/haichau_network_v2/demo-bounded
python3 launch_demo.py --no-browser
```

Open the loopback URL printed by the launcher. If the default port is occupied,
use `--port 8900`; the launcher tries the next ten ports automatically.

The bundle contains six matched replays: fixed-time and schedule-residual DDQN
for normal, AM peak, and PM peak. The normal replay is intentionally identical
to fixed-time because the controller contract anchors light-demand operation to
the reference schedule.

## What to show

1. Start with the network map and state that it contains 53 OSM-derived Hai Chau
   signals. Routes, flows, and signal plans are synthetic and constrained by Da
   Nang evidence; they are not measured district traffic.
2. Play the normal pair and show the exact tie to fixed-time.
3. Play the AM and PM pairs, then show the aggregate result: fixed-time
   8,339.43 vehicle-hours versus residual DDQN 7,829.25, a 6.12% reduction.
4. Explain the regime means: 3.53% lower in AM and 8.86% lower in PM. Mention
   the paired 95% interval of 0.90%--8.35% and the individual-case range of
   -4.24% to 26.11%.
5. Show that Max-Pressure and hysteretic Max-Pressure are stronger baselines in
   this synthetic matrix (23.89% and 19.19% lower than fixed-time). The claim
   is improvement over fixed-time, not universal superiority.

## Scope statement

The displayed result uses learning seed 14, checkpoint step 4, and all fifteen
declared held-out cases. Three completed learning seeds give a mean aggregate
reduction of 2.45%; seed variation is therefore part of the result. The strict
five-seed confirmatory release is still pending and must not be described as
accepted until `scripts/verify_haichau_thesis.py` reports `complete: true`.

## Preflight

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'results/haichau_network_v2/demo-bounded'))
import launch_demo
manifest = launch_demo.validate_bundle(Path('results/haichau_network_v2/demo-bounded'))
print('portable bundle:', manifest['controlled_signals'], 'signals;',
      manifest['evidence_scope'])
PY
```

Run the preflight from the repository root. Disconnect the network, launch the
server, switch all three regimes, play/pause, seek, and select a node before
the presentation. Keep the PDF thesis and the JSON summaries as fallback
evidence if the browser is unavailable.
