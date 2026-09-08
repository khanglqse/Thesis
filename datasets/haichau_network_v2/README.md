# Hai Chau network v2

This dataset is a synthetic research network derived from an OpenStreetMap extract. It is not an observed Hai Chau traffic-signal plan or a calibrated origin-destination model.

The immutable provenance root is the tracked source CityFlow roadnet at `source/roadnet_haichau_rush.json` (SHA-256 `cddce1090b214fd8250303a28b51e4a460f4af04dde87cafad9dabd58f2ac040`). The clipped PBF, OSM XML and SUMO network used along the recorded conversion path are also tracked under `source/`. The original OSM retrieval date and converter/tool versions were not recorded; `provenance.json` marks those facts `unknown_not_recorded` rather than inferring them.

The canonical `roadnet.json` differs from the source only at intersection `5896811072`. Its converter-produced single 80-second action was replaced with two 40-second movement actions and two 5-second clearances. This is an explicit **synthetic engineering normalization**, not recovered source evidence. `provenance.json` records the exact before/after transformation, and the verifier applies it to the tracked source and requires byte-equivalent JSON content to the canonical roadnet.

`phase-contract.json` defines controller semantics for all 53 agents. Its 107 `selectable_phases` are movement-serving phases whose configured duration satisfies the 20-second minimum green. Its 127 `transition_phases` include empty clearances and short permissive converter phases; they are never actions. Every directed switch has a non-empty ordered `transitions[source][target]` sequence with the phase index and declared duration. The contract derives these roles from movement permissions, phase duration and cyclic plan order because the CityFlow conversion did not retain the original SUMO signal color letters.
