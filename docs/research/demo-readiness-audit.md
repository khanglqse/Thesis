# Legacy demo readiness audit

Date: 2026-09-07. Scope: existing 2D/3D replay assets, not final research runs.

## Verified automatically

- `node --test tests/replay_ab/*.test.cjs tests/replay_3d/*.test.cjs`: 18/18 pass when ignored roadnet/replay artifacts are present.
- The tests parse the real legacy Hai Chau roadnet, 120 replay steps, vehicles, signal states, scoreboard calculations and deterministic busy-view selection.
- `frontend/vendor/deck.min.js` is local, so the 3D implementation does not require a deck.gl CDN.

## Open failures and risks

- A clean worktree lacks `data/danang/replay_roadnet_haichau_rush.json` and `results/haichau_rush/demo/replay_dqn_demo.txt`; tests and demo fail until local artifacts are supplied.
- `scripts/serve_replay.py` defaults to `frontend/index.html`. That legacy page uses remote Bootstrap, PIXI and Chartist assets and is not the defense launcher.
- Existing scoreboard values are one legacy episode and may be mistaken for the five-seed aggregate.
- Browser interaction, network blocking, console state, 1280×720 layout, 15-minute endurance, port fallback and WebGL fallback have not yet been freshly verified on the final bundle.

## Required implementation

Build a self-contained `results/defense_bundle/v1/` from final frozen runs. Its manifest must bind scenario, controller/checkpoint, all seed axes, simulator version, replay and metrics hashes. The launcher must open the 2D A/B page by default and expose 3D and MP4/PDF fallbacks. The final certification record will include browser version, machine, resolution, offline state, bundle hash, measured load/preset time and every acceptance-test result.

Current verdict: the legacy viewer is a reusable base; the defense demo is not yet certified.
