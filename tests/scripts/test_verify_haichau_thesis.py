import hashlib
import json

from scripts.verify_haichau_thesis import audit_demo, verify_project


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_complete_project(root):
    final = root / "results/haichau_network_v2/final"
    network = {
        "controlled_signals": 53,
        "agent_ids": ["N%02d" % index for index in range(53)],
    }
    _write(root / "release/network-manifest.json", json.dumps(network))
    cases = []
    for index in range(30):
        cases.append({
            "case_id": "case-%02d" % index,
            "split": ("train", "validation", "test")[index // 10],
            "demand_sha256": "%064x" % (index + 1),
        })
    _write(root / "release/case-manifest.json", json.dumps({"cases": cases}))

    checkpoints = []
    for seed in range(11, 16):
        path = root / ("release/checkpoint-%s.npz" % seed)
        _write(path, "checkpoint-%s" % seed)
        checkpoints.append({
            "learning_seed": seed,
            "path": str(path.relative_to(root)),
            "sha256": _digest(path),
            "validation_eligible": True,
            "checkpoint_contract": {"obs_schema_version": 2},
        })
    protocol = {
        "network_manifest_path": "release/network-manifest.json",
        "network_manifest_sha256": _digest(root / "release/network-manifest.json"),
        "case_manifest_path": "release/case-manifest.json",
        "case_manifest_sha256": _digest(root / "release/case-manifest.json"),
        "runtime_digest": "sha256:" + "a" * 64,
        "checkpoints": checkpoints,
        "code_commit": "fixture-commit",
    }
    _write(final / "frozen-protocol.json", json.dumps(protocol))

    runs = []
    learned = {"shared_ddqn_legacy", "neighbor_phase_ddqn"}
    controllers = (
        "tuned_fixed", "max_pressure", "hysteretic_mp",
        "shared_ddqn_legacy", "neighbor_phase_ddqn",
    )
    for regime_index, regime in enumerate(("normal", "am_peak", "pm_peak")):
        case_id = "test-%s" % regime
        for controller in controllers:
            seeds = range(11, 16) if controller in learned else (None,)
            for seed in seeds:
                run_id = "%s-%s-%s" % (regime, controller, seed)
                run = {
                    "run_id": run_id,
                    "case_id": case_id,
                    "regime": regime,
                    "controller_id": controller,
                    "learning_seed": seed,
                    "horizon_steps": 10,
                }
                runs.append(run)
                run_dir = final / "runs" / run_id
                payloads = {
                    "run-manifest.json": json.dumps(run),
                    "resolved-config.json": "{}",
                    "metrics.json": json.dumps({
                        "case_id": case_id,
                        "controller_id": controller,
                        "completed_steps": 10,
                        "fresh_evaluation": True,
                    }),
                    "stdout.log": "fixture",
                    "stderr.log": "",
                }
                for name, content in payloads.items():
                    _write(run_dir / name, content)
                hashes = {
                    name: _digest(run_dir / name) for name in payloads
                }
                _write(run_dir / "status.json", json.dumps({
                    "status": "complete", "artifact_sha256": hashes,
                }))
    _write(final / "campaign-manifest.json", json.dumps({"runs": runs}))

    summary = {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
        },
        "summary": {
            "neighbor_phase_ddqn": {
                regime: {"statistical_unit": "learning_seed_after_matched_case_mean"}
                for regime in ("normal", "am_peak", "pm_peak")
            },
        },
        "acceptance": {
            "accepted": False,
            "normal_point_noninferiority": False,
            "normal_ci_noninferiority": False,
            "peak_improvement": False,
            "completion_preserved": True,
            "five_learning_seeds": True,
        },
    }
    _write(final / "summary.json", json.dumps(summary))
    artifact_dir = root / "paper/generated/haichau_network"
    _write(artifact_dir / "table.tex", "fixture")
    _write(artifact_dir / "artifact-manifest.json", json.dumps({
        "summary_sha256": _json_digest(summary), "artifacts": ["table.tex"],
    }))
    _write(root / "paper/thesis_danang.pdf", "fixture")

    demo = root / "results/haichau_network_v2/demo"
    _write(demo / "index.html", "offline fixture")
    _write(demo / "network.json", json.dumps({
        "controlled_signals": 53,
        "nodes": [{"id": "N%02d" % index} for index in range(53)],
    }))
    _write(demo / "aggregate-summary.json", json.dumps(summary))
    fallbacks = {}
    for name in ("demo-walkthrough.mp4", "result-summary.pdf", "network-overview.png"):
        relative = "fallbacks/" + name
        _write(demo / relative, "fixture")
        fallbacks[name] = relative
    replays = []
    for regime in ("normal", "am_peak", "pm_peak"):
        for controller in ("tuned_fixed", "neighbor_phase_ddqn"):
            relative = "replays/%s-%s.json" % (regime, controller)
            _write(demo / relative, "{}")
            replays.append({
                "regime": regime, "controller_id": controller,
                "case_id": "test-%s" % regime, "path": relative,
            })
    files = {
        str(path.relative_to(demo)): _digest(path)
        for path in demo.rglob("*") if path.is_file()
    }
    _write(demo / "manifest.json", json.dumps({
        "controlled_signals": 53,
        "demand_label": "synthetic network demand constrained by Da Nang evidence",
        "network_path": "network.json",
        "aggregate_path": "aggregate-summary.json",
        "replays": replays,
        "fallbacks": fallbacks,
        "files": files,
    }))
    _write(root / "results/haichau_network_v2/verification/clean-checkout.json", json.dumps({
        "passed": True,
        "commit": "fixture-commit",
        "commands": ["make test"],
        "tool_versions": {"python": "fixture"},
        "wall_time_seconds": 1,
    }))


def test_final_verifier_lists_missing_requirements(tmp_path):
    report = verify_project(tmp_path)
    assert report["complete"] is False
    assert "five_learning_seeds" in report["failed_gates"]
    assert "offline_demo" in report["failed_gates"]
    assert "network_53_signals" in report["failed_gates"]


def test_final_verifier_accepts_complete_hash_valid_negative_result(tmp_path):
    _write_complete_project(tmp_path)

    report = verify_project(tmp_path)

    assert report["complete"] is True
    assert report["failed_gates"] == []
    assert report["gates"]["acceptance_reported"]["evidence"]["accepted"] is False


def test_negative_acceptance_result_is_complete_reporting_not_a_failed_gate(tmp_path):
    _write(tmp_path / "results/haichau_network_v2/final/summary.json", json.dumps({
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
        },
        "summary": {},
        "acceptance": {
            "accepted": False,
            "normal_point_noninferiority": False,
            "normal_ci_noninferiority": False,
            "peak_improvement": False,
            "completion_preserved": True,
            "five_learning_seeds": True,
        },
    }))
    report = verify_project(tmp_path)
    assert report["gates"]["acceptance_reported"]["passed"] is True
    assert report["gates"]["acceptance_reported"]["evidence"]["accepted"] is False


def test_offline_demo_rejects_remote_dependency_even_when_hashed(tmp_path):
    demo = tmp_path / "results/haichau_network_v2/demo"
    _write(demo / "index.html", '<script src="https://example.com/a.js"></script>')
    _write(demo / "network.json", json.dumps({
        "controlled_signals": 53,
        "nodes": [{"id": "N%02d" % index} for index in range(53)],
    }))
    _write(demo / "aggregate-summary.json", "{}")
    for name in ("demo-walkthrough.mp4", "result-summary.pdf", "network-overview.png"):
        _write(demo / "fallbacks" / name, "fixture")
    files = {}
    for path in demo.rglob("*"):
        if path.is_file():
            files[str(path.relative_to(demo))] = _digest(path)
    _write(demo / "manifest.json", json.dumps({
        "controlled_signals": 53,
        "demand_label": "synthetic network demand constrained by Da Nang evidence",
        "network_path": "network.json",
        "aggregate_path": "aggregate-summary.json",
        "replays": [],
        "fallbacks": {
            "demo-walkthrough.mp4": "fallbacks/demo-walkthrough.mp4",
            "result-summary.pdf": "fallbacks/result-summary.pdf",
            "network-overview.png": "fallbacks/network-overview.png",
        },
        "files": files,
    }))

    result = audit_demo(tmp_path)

    assert result["passed"] is False
    assert "remote dependency" in result["detail"]


def test_offline_demo_requires_every_payload_file_in_hash_set(tmp_path):
    demo = tmp_path / "results/haichau_network_v2/demo"
    _write(demo / "index.html", "offline fixture")
    _write(demo / "network.json", json.dumps({
        "controlled_signals": 53,
        "nodes": [{"id": "N%02d" % index} for index in range(53)],
    }))
    _write(demo / "aggregate-summary.json", "{}")
    for name in ("demo-walkthrough.mp4", "result-summary.pdf", "network-overview.png"):
        _write(demo / "fallbacks" / name, "fixture")
    files = {}
    for path in demo.rglob("*"):
        if path.is_file() and path.name != "network.json":
            files[str(path.relative_to(demo))] = _digest(path)
    _write(demo / "manifest.json", json.dumps({
        "controlled_signals": 53,
        "demand_label": "synthetic network demand constrained by Da Nang evidence",
        "network_path": "network.json",
        "aggregate_path": "aggregate-summary.json",
        "replays": [],
        "fallbacks": {
            "demo-walkthrough.mp4": "fallbacks/demo-walkthrough.mp4",
            "result-summary.pdf": "fallbacks/result-summary.pdf",
            "network-overview.png": "fallbacks/network-overview.png",
        },
        "files": files,
    }))

    result = audit_demo(tmp_path)

    assert result["passed"] is False
    assert "file set" in result["detail"]
