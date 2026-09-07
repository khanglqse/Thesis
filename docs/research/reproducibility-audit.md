# Reproducibility audit

Audit run: `results/research_foundation/20260907T133327743207Z`
Git commit at snapshot: `1668402070e5164b1d68f51b2c975b194e516578`

## Verified environment

- Host: Apple Silicon (`arm64`), 12 logical CPUs, Python 3.13.7, Node 25.2.1.
- SUMO: 1.24 development build `1_24_0+1559-61e8e739dad`, native arm64.
- Docker client/server: 29.4.1/29.2.1; Colima is running on arm64.
- CityFlow image: `cityflowproject/cityflow@sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32`, image architecture `amd64`.
- Input manifest: SHA-256 `51abb09d92f21297af63545918bc810df647a5069ca7c333d90a259e1f38f567`, covering 29 `data/`, 2 `osm_danang/`, and 35 frozen reference-result files.

## Baseline evidence

The original checkout passed 85 selected Python tests and 18 Node replay tests. A clean linked worktree initially failed one Python test and two replay tests because `data/` and `results/*/demo/` are ignored by Git. After linking the local-only snapshot, the same suites passed (85/85 selected; 18/18). This proves the local code baseline, while also proving that a fresh clone is not currently self-contained.

The unmodified CityFlow image failed import with `ModuleNotFoundError: dataclasses`. A temporary, explicit runtime recipe installed `dataclasses==0.8`, `numpy==1.19.5`, and `PyYAML==5.4.1`. The repaired 60-second Fixed-Time technical smoke then completed with 10 agents and 60 simulator steps. Its output is `smoke-cityflow.json` (SHA-256 `583994a301687d859226337eabe74286f968517cb4e570b8356fb277626f8b36`). The metric values are a technical check and must not appear as a research result.

## Artifact classification

| Class | Current state | Required action |
|---|---|---|
| Source, tests, paper, most historical results | tracked | retain commit identity |
| `data/` (92 MB) | local-only, ignored | create a versioned data manifest and a redistribution-safe release bundle |
| demo replay excerpts | local-only, ignored | regenerate from selected final runs and include in defense bundle |
| frozen references (135 MB) | 35 tracked files in `results/references/` | keep immutable; do not overwrite |
| current CityFlow runtime | digest known but needs runtime pip repair | build/pin a research image or record exact install recipe |
| LaTeX toolchain | not verified in this run | install or containerize before T11 |

## Reproduction risks

The largest risks are ignored research inputs, use of an amd64/Python-3.6 image under arm64 emulation, use of the mutable `latest` tag in Makefile commands, and evaluation scripts that merge newly evaluated DQN rows with cached baselines. The new runner must write all controller results from the same case manifest, simulator build, horizon, and seed tuple.

Fresh-clone reproducibility is not yet achieved. The final release gate requires a new checkout that obtains data through a documented checksum-verified route, executes a toy smoke, regenerates final tables, and launches the defense bundle offline.
