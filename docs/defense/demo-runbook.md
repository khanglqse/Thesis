# Hai Chau visual demo runbook

Use only `results/haichau_network_v2/demo-visual`. It is an offline recorded
PM-peak replay for the OSM-derived 53-signal Hai Chau model with synthetic
demand constrained by Da Nang evidence.

```sh
cd results/haichau_network_v2/demo-visual
python3 launch_demo.py --no-browser --port 8766
```

Open `http://127.0.0.1:8766/index.html` and wait for **Verified replay loaded**.
Select **Reset to guided view** before speaking. The guided frame is 18:05 at
junction `420249521`: Fixed-time has 14 queued vehicles and DDQN has 1. Describe
this as **13 fewer queued vehicles at this frame**. The panel now uses that
snapshot wording; the difference does not establish an additional discharge count.

Use **Play** at 10x only after explaining that fixed-time and DDQN replay the
same demand at synchronized times. Use **Linked junctions** to show adjacent
signals. Use **Whole network** to show the 53-signal geography; click a coloured
signal circle to return to its detailed view. Blue vehicle glyphs are motorcycles
and orange glyphs are cars.

The visual replay is illustrative. Aggregate thesis conclusions must be read
from the frozen full-horizon evaluation artifacts and the thesis, not inferred
from a single frame.

The PM aggregate panel reports **−8.86% mean per-case queue change** for
seed 14, with case-bootstrap interval **[−17.51%, −1.62%]** over five demand
cases. Both endpoints have percent units. This is not the five-learning-seed
gate interval or an interval in vehicle-seconds. Source:
`results/haichau_network_v2/final15-seed14-step4-summary.json`.

For questions about the data, model identity, rejected seeds and test independence,
use [the evidence-backed committee answers](committee-questions-evidence-vi.md).
The five-seed gate is post hoc; seeds 13 and 16 are diagnostic after validation rejection.
