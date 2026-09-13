# Likely defense questions

**Are these real Da Nang counts?** The primary scenarios use counts digitized from four published camera movement lines on 1 April 2025. They do not cover the full intersection. The 6,171 PCU/h twelve-movement table remains separate.

**Why one intersection?** A full OSM conversion introduced neighboring signals and short fragments without validated demand or timings. The isolated junction supports a causal comparison but no corridor claim.

**Does the 53-signal extension use observed district-wide demand?** No. It uses an OpenStreetMap-derived Hai Chau topology and synthetic network demand constrained by Da Nang evidence. The JICA and DaCRISS planning studies provide context only; they do not calibrate the 53 signal timings, routes, or flows. The bounded seed-14 replay reports a 6.12% aggregate queue reduction, and the five-seed gated analysis reports a 3.48% mean full-day reduction. The gated result is exploratory; the strict confirmatory release remains pending until the release verifier reports `"complete": true`.

**Why does RL lose in normal traffic?** Fixed time clears sparse arrivals with little residual queue. Adaptive switching pays clearance cost without enough benefit. This motivates demand gating.

**Why five seeds?** Five independent policies reveal variation and permit seed-level intervals. More seeds would narrow uncertainty; crossed evaluations are not counted as independent policies.

**Is the demo live inference?** No. It is a synchronized replay of frozen SUMO runs. The exporter reproduces exact evaluation metrics before writing data. This removes training risk during the defense.

**Does zero collision prove road safety?** No. It describes the final simulator assumptions across 105 primary runs. Field use requires behavior calibration, shadow testing, and traffic-engineering review.

**Why change motorcycle headway?** A held-out AM case reproduced a rear-end collision at `tau=1.0`. The one-parameter test removed it at `tau=1.2`; all policies and evaluations were then rerun.

**Why did Max-Pressure perform poorly?** Pressure sees partial movements, and each switch pays seven seconds of clearance. Hysteresis helped but did not overcome the observation mismatch. This does not refute Max-Pressure theory.
