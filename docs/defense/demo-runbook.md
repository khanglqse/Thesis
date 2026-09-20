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
junction `420249521`: Fixed-time has 14 queued vehicles and DDQN has 1. The
selected-intersection panel says that DDQN cleared 13 more queued vehicles.

Use **Play** at 10x only after explaining that fixed-time and DDQN replay the
same demand at synchronized times. Use **Linked junctions** to show adjacent
signals. Use **Whole network** to show the 53-signal geography; click a coloured
signal circle to return to its detailed view. Blue vehicle glyphs are motorcycles
and orange glyphs are cars.

The visual replay is illustrative. Aggregate thesis conclusions must be read
from the frozen full-horizon evaluation artifacts and the thesis, not inferred
from a single frame.
