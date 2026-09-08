import hashlib
import json
import shutil
import subprocess

import pytest

import traffic_rl.eval.release_identity as release_identity
from traffic_rl.agents.dqn import SharedDQN
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from scripts.export_haichau_replays import export_bundle
from scripts.verify_haichau_thesis import (
    _checkpoint_contract_valid, audit_demo, verify_project)
from traffic_rl.eval.network_campaign import bind_frozen_manifest, expand_runs, run_pending
from traffic_rl.eval.network_statistics import aggregate_campaign, evaluate_acceptance
from traffic_rl.report.haichau_network import write_artifacts, write_release_manifest
from traffic_rl.sim.phase_encoder import FEATURES


RUNTIME_DIGEST = "sha256:" + "a" * 64
RUNTIME_IMAGE = "cityflowproject/cityflow@" + RUNTIME_DIGEST


@pytest.fixture(autouse=True)
def _verified_fixture_runtime(monkeypatch):
    def inspect(image):
        if image != RUNTIME_IMAGE:
            raise ValueError("runtime image differs from inspected fixture image")
        return {
            "runtime_image": image,
            "runtime_image_id": RUNTIME_DIGEST,
            "repo_digests": [RUNTIME_IMAGE],
        }
    monkeypatch.setattr(release_identity, "inspect_runtime_image", inspect)


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args),
        universal_newlines=True).strip()


def _commit(root, message):
    _git(root, "add", ".")
    _git(root, "commit", "-qm", message)
    return _git(root, "rev-parse", "HEAD")


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_placeholder_project(root):
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


def _checkpoint_contract(network_sha256, controller="neighbor_phase_ddqn",
                         phase_sha256=None, generator_sha256=None,
                         manifest_sha256=None):
    phase_sha256 = phase_sha256 or "b" * 64
    generator_sha256 = generator_sha256 or "c" * 64
    manifest_sha256 = manifest_sha256 or "d" * 64
    return {
        "obs_schema_version": 2,
        "feature_order": (list(FEATURES)
                          if controller == "neighbor_phase_ddqn"
                          else ["lane_count_0"]),
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "hidden_size": 64,
        "action_contract": ({
            "type": "phase_rows", "version": 1,
            "mask_type": "boolean_selectable_green_rows",
            "padding_actions_selectable": False,
        } if controller == "neighbor_phase_ddqn" else {
            "type": "fixed_vector", "version": 1,
            "mask_type": "boolean_phase_index",
            "padding_actions_selectable": False,
            "n_actions": 3,
        }),
        "network_compatibility": {
            "network_sha256": network_sha256,
            "phase_contract_sha256": phase_sha256,
            "generator_config_sha256": generator_sha256,
            "manifest_sha256": manifest_sha256,
        },
        "controller_family": controller,
    }


def _write_bound_project(root):
    runtime_dockerfile = root / "docker/haichau-evaluation.Dockerfile"
    _write(runtime_dockerfile, "FROM %s\n" % RUNTIME_IMAGE)
    subprocess.check_call(["git", "init", "-q", str(root)])
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    code_commit = _commit(root, "frozen code")
    final = root / "results/haichau_network_v2/final"
    agent_ids = ["N%02d" % index for index in range(53)]
    roadnet_path = root / "release/roadnet.json"
    viewer_path = root / "release/viewer-network.json"
    _write(roadnet_path, json.dumps({"intersections": agent_ids}))
    viewer = {
        "controlled_signals": 53,
        "nodes": [{"id": node_id, "x": index, "y": index % 7,
                   "neighbors": []}
                  for index, node_id in enumerate(agent_ids)],
        "links": [],
    }
    _write(viewer_path, json.dumps(viewer))
    network_sha = _digest(roadnet_path)
    viewer_sha = _digest(viewer_path)
    network_manifest = {
        "controlled_signals": 53,
        "agent_ids": agent_ids,
        "artifacts": {
            "cityflow_roadnet": {
                "path": str(roadnet_path.relative_to(root)), "sha256": network_sha,
            },
            "viewer_network": {
                "path": str(viewer_path.relative_to(root)), "sha256": viewer_sha,
            },
        },
    }
    network_manifest_path = root / "release/network-manifest.json"
    _write(network_manifest_path, json.dumps(network_manifest))

    cases = []
    for index in range(21):
        demand_path = root / ("release/demand-train-%02d.json" % index)
        _write(demand_path, "train-%02d" % index)
        cases.append({
            "case_id": "train-%02d" % index, "split": "train",
            "scheduled_vehicles": 1000 + index,
            "demand_path": str(demand_path.relative_to(root)),
            "demand_sha256": _digest(demand_path),
        })
    for index in range(3):
        demand_path = root / ("release/demand-validation-%02d.json" % index)
        _write(demand_path, "validation-%02d" % index)
        cases.append({
            "case_id": "validation-%02d" % index, "split": "validation",
            "scheduled_vehicles": 2000 + index,
            "demand_path": str(demand_path.relative_to(root)),
            "demand_sha256": _digest(demand_path),
        })
    for regime_index, regime in enumerate(("normal", "am_peak", "pm_peak")):
        for demand_index in range(2):
            demand_path = root / (
                "release/demand-test-%s-%s.json" % (regime, demand_index))
            _write(demand_path, "test-%s-%s" % (regime, demand_index))
            cases.append({
                "case_id": "test-%s-%s" % (regime, demand_index),
                "split": "test", "regime": regime,
                "demand_seed": 200 + regime_index * 10 + demand_index,
                "simulator_seed": 300 + regime_index * 10 + demand_index,
                "scheduled_vehicles": 1000 + regime_index * 100 + demand_index,
                "horizon_steps": 10,
                "scheduled_vehicles": 3000 + regime_index * 10 + demand_index,
                "demand_path": str(demand_path.relative_to(root)),
                "demand_sha256": _digest(demand_path),
            })
    case_manifest = {"protocol_version": 2, "cases": cases}
    case_manifest_path = root / "release/case-manifest.json"
    _write(case_manifest_path, json.dumps(case_manifest))

    phase_sha = "b" * 64
    generator_sha = "c" * 64
    experiment_sha = "d" * 64
    checkpoints = []
    for controller in ("shared_ddqn_legacy", "neighbor_phase_ddqn"):
        for seed in range(11, 16):
            contract = _checkpoint_contract(
                network_sha, controller, phase_sha, generator_sha, experiment_sha)
            bundle = root / ("release/%s-%s" % (controller, seed))
            if controller == "shared_ddqn_legacy":
                model = SharedDQN(1, 3, hidden=64, seed=seed, dueling=True)
            else:
                model = PhaseScoringDDQN(
                    len(FEATURES), hidden=64, lr=1e-3, seed=seed)
            model.save_bundle(str(bundle), contract)
            path = bundle / "weights.npz"
            contract_path = bundle / "contract.json"
            checkpoints.append({
                "controller_id": controller,
                "learning_seed": seed,
                "path": str(path.relative_to(root)),
                "sha256": _digest(path),
                "contract_path": str(contract_path.relative_to(root)),
                "contract_file_sha256": _digest(contract_path),
                "validation_eligible": True,
                "checkpoint_contract": contract,
                "checkpoint_contract_sha256": _json_digest(contract),
            })
    controller_configs = {
        controller: {"controller_version": 2}
        for controller in (
            "tuned_fixed", "max_pressure", "hysteretic_mp",
            "shared_ddqn_legacy", "neighbor_phase_ddqn",
        )
    }
    controller_configs["tuned_fixed"]["green_duration"] = 30
    controller_configs["hysteretic_mp"].update({
        "min_hold_decisions": 3, "switch_threshold": 2.5,
    })
    controller_commands = {
        controller: ["python3", "scripts/evaluate_haichau_network.py"]
        for controller in controller_configs
    }
    rules = {
        "required_learning_seeds": [11, 12, 13, 14, 15],
        "required_regimes": ["normal", "am_peak", "pm_peak"],
        "minimum_learning_seeds": 5,
        "minimum_demand_units": 2,
        "bootstrap_seed": 20260908,
        "bootstrap_samples": 10000,
        "normal_point_limit": 0.0,
        "normal_ci_margin_fraction": 0.05,
        "peak_ci_upper_limit": 0.0,
        "completion_degradation_limit": 0.02,
    }
    protocol = {
        "network_manifest_path": str(network_manifest_path.relative_to(root)),
        "network_manifest_sha256": _digest(network_manifest_path),
        "case_manifest_path": str(case_manifest_path.relative_to(root)),
        "case_manifest_sha256": _digest(case_manifest_path),
        "network_sha256": network_sha,
        "viewer_network_sha256": viewer_sha,
        "phase_contract_sha256": phase_sha,
        "generator_config_sha256": generator_sha,
        "experiment_manifest_sha256": experiment_sha,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "runtime_digest": RUNTIME_DIGEST,
        "runtime_image": RUNTIME_IMAGE,
        "runtime_image_id": RUNTIME_DIGEST,
        "runtime_dockerfile_path": str(runtime_dockerfile.relative_to(root)),
        "runtime_dockerfile_sha256": _digest(runtime_dockerfile),
        "agent_ids": agent_ids,
        "resolved_config": {
            "network_path": str(roadnet_path.relative_to(root)),
            "phase_contract_path": "release/phase-contract.json",
            "phase_contract_sha256": phase_sha,
            "step_seconds": 1,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {
                "action_interval": 10, "yellow_time": 3,
                "min_green": 20, "maximum_red": 180,
            },
            "reward": {
                "queue_weight": 1.0, "downstream_block_weight": 0.1,
                "switch_penalty": 0.05,
            },
        },
        "controller_configs": controller_configs,
        "controller_commands": controller_commands,
        "checkpoints": checkpoints,
        "acceptance_rules": rules,
        "code_commit": code_commit,
    }
    _write(final / "frozen-protocol.json", json.dumps(protocol))

    expansion_manifest = bind_frozen_manifest(case_manifest, protocol)
    runs = expand_runs(
        expansion_manifest, rules["required_learning_seeds"],
        list(controller_configs))
    _write(final / "campaign-manifest.json", json.dumps({
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }))

    replay_nodes = dict((node_id, {"queue": 0, "phase": 0})
                        for node_id in agent_ids)

    def executor(run, run_dir):
        base_queue = 100.0
        if run["controller_id"] == "neighbor_phase_ddqn":
            base_queue = 110.0 if run["regime"] == "normal" else 90.0
        elif run["controller_id"] == "shared_ddqn_legacy":
            base_queue = 98.0
        elif run["controller_id"] in ("max_pressure", "hysteretic_mp"):
            base_queue = 95.0
        per_node = dict((node_id, 0.0) for node_id in agent_ids)
        metrics = {
            "case_id": run["case_id"], "regime": run["regime"],
            "controller_id": run["controller_id"],
            "learning_seed": run["learning_seed"],
            "demand_seed": run["demand_seed"],
            "simulator_seed": run["simulator_seed"],
            "scheduled_vehicles": run["scheduled_vehicles"],
            "network_sha256": run["network_sha256"],
            "viewer_network_sha256": run["viewer_network_sha256"],
            "demand_sha256": run["demand_sha256"],
            "demand_path": run["demand_path"],
            "runtime_digest": run["runtime_digest"],
            "runtime_image": run["runtime_image"],
            "runtime_image_id": run["runtime_image_id"],
            "runtime_dockerfile_path": run["runtime_dockerfile_path"],
            "runtime_dockerfile_sha256": run["runtime_dockerfile_sha256"],
            "code_commit": run["code_commit"],
            "checkpoint_sha256": run.get("checkpoint_sha256"),
            "checkpoint_contract_sha256": run.get("checkpoint_contract_sha256"),
            "completed_steps": 10, "observed_steps": 10, "observed_seconds": 10,
            "queue_integral_vehicle_seconds": base_queue,
            "queue_integral_vehicle_hours": base_queue / 3600,
            "pending_integral_vehicle_seconds": 0.0,
            "per_node_queue_integral_vehicle_seconds": per_node,
            "per_node_max_queue": per_node,
            "spillback_lane_seconds": {},
            "scheduled": run["scheduled_vehicles"],
            "inserted": run["scheduled_vehicles"],
            "departed": run["scheduled_vehicles"],
            "arrived": run["scheduled_vehicles"],
            "running": 0, "pending": 0, "removed": 0,
            "censored_or_unfinished": 0,
            "completion_denominator": "scheduled", "completion_rate": 1.0,
            "insertion_rate": 1.0,
            "completed_travel_time_count": run["scheduled_vehicles"],
            "phase_switches": 0, "intergreen_seconds": 0.0,
            "max_red_seconds": 0.0, "travel_time_completed_mean": 10.0,
            "travel_time_completed_median": 10.0,
            "travel_time_completed_p95": 10.0, "fresh_evaluation": True,
        }
        return {
            "resolved_config": run["resolved_config"], "metrics": metrics,
            "replay": {
                "sample_seconds": 5,
                "frames": [
                    {"t": time, "nodes": replay_nodes, "vehicles": []}
                    for time in (0, 5, 10)
                ],
                "metrics": {
                    "queue_integral_vehicle_seconds": base_queue,
                    "completion_rate": 1.0,
                    "arrived": run["scheduled_vehicles"],
                    "running": 0, "pending": 0,
                },
            },
            "stdout": "fixture", "stderr": "",
        }

    assert run_pending(final, executor)["failed"] == 0
    rows = []
    for run in runs:
        row = dict(run)
        row.update(json.loads(
            (final / "runs" / run["run_id"] / "metrics.json").read_text()))
        rows.append(row)
    aggregate = aggregate_campaign(
        rows, required_learning_seeds=rules["required_learning_seeds"],
        required_regimes=rules["required_regimes"],
        minimum_learning_seeds=rules["minimum_learning_seeds"],
        minimum_demand_units=rules["minimum_demand_units"],
        normal_point_limit=rules["normal_point_limit"],
        normal_ci_margin_fraction=rules["normal_ci_margin_fraction"],
        peak_ci_upper_limit=rules["peak_ci_upper_limit"],
        completion_degradation_limit=rules["completion_degradation_limit"],
    )
    summary = {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
            "evidence_namespace": "haichau_network_v2",
        },
        "summary": aggregate,
        "acceptance": evaluate_acceptance(aggregate),
    }
    _write(final / "summary.json", json.dumps(summary))

    thesis_path = root / "paper/thesis_danang.tex"
    pdf_path = root / "paper/thesis_danang.pdf"
    artifact_dir = root / "paper/generated/haichau_network"
    _write(thesis_path, "Frozen synthetic network demand result.")
    write_artifacts(
        summary, artifact_dir, "fixture-build", thesis_path=thesis_path)
    shutil.copyfile(artifact_dir / "paired-queue-difference.pdf", pdf_path)
    write_release_manifest(
        summary, artifact_dir, thesis_path, pdf_path, "fixture-release")

    fallbacks_dir = root / "release/fallbacks"
    fallbacks_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "color=c=black:s=32x24:d=0.2", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(fallbacks_dir / "demo-walkthrough.mp4"),
    ])
    shutil.copyfile(pdf_path, fallbacks_dir / "result-summary.pdf")
    shutil.copyfile(
        artifact_dir / "completion-rate.png",
        fallbacks_dir / "network-overview.png")
    selected = []
    for regime in ("normal", "am_peak", "pm_peak"):
        selected.append(next(run["run_id"] for run in runs if (
            run["regime"] == regime and run["controller_id"] == "tuned_fixed")))
        selected.append(next(run["run_id"] for run in runs if (
            run["regime"] == regime
            and run["controller_id"] == "neighbor_phase_ddqn"
            and run["learning_seed"] == 11)))
    export_bundle(
        final, root / "results/haichau_network_v2/demo", viewer_path, selected,
        {
            "demo-walkthrough.mp4": fallbacks_dir / "demo-walkthrough.mp4",
            "result-summary.pdf": fallbacks_dir / "result-summary.pdf",
            "network-overview.png": fallbacks_dir / "network-overview.png",
        },
    )

    release_files = (
        "results/haichau_network_v2/final/frozen-protocol.json",
        "results/haichau_network_v2/final/campaign-manifest.json",
        "results/haichau_network_v2/final/summary.json",
        "paper/generated/haichau_network/artifact-manifest.json",
        "paper/generated/haichau_network/thesis-release.json",
        "paper/thesis_danang.pdf",
        "results/haichau_network_v2/demo/manifest.json",
    )
    verified_commit = _commit(root, "frozen evidence")
    _write(root / "results/haichau_network_v2/verification/clean-checkout.json", json.dumps({
        "verification_version": 2,
        "passed": True, "verified_commit": verified_commit,
        "wall_time_seconds": 1,
        "artifact_sha256": dict((name, _digest(root / name)) for name in release_files),
    }))
    _commit(root, "clean-checkout record")
    return summary


def test_final_verifier_lists_missing_requirements(tmp_path):
    report = verify_project(tmp_path)
    assert report["complete"] is False
    assert "five_learning_seeds" in report["failed_gates"]
    assert "offline_demo" in report["failed_gates"]
    assert "network_53_signals" in report["failed_gates"]


def test_final_verifier_rejects_disjoint_placeholder_evidence(tmp_path):
    _write_placeholder_project(tmp_path)

    report = verify_project(tmp_path)

    assert report["complete"] is False
    assert "fresh_matched_runs" in report["failed_gates"]
    assert "hierarchical_statistics" in report["failed_gates"]
    assert "thesis_artifacts" in report["failed_gates"]


def test_injected_campaign_and_handwritten_clean_record_cannot_complete_release(tmp_path):
    summary = _write_bound_project(tmp_path)

    report = verify_project(tmp_path)

    assert report["complete"] is False
    assert report["gates"]["fresh_matched_runs"]["passed"] is False
    assert "trusted Docker executor" in report["gates"]["fresh_matched_runs"]["detail"]
    assert report["gates"]["clean_checkout"]["passed"] is False
    assert "attestation" in report["gates"]["clean_checkout"]["detail"]
    assert report["gates"]["acceptance_reported"]["passed"] is True
    assert report["gates"]["acceptance_reported"]["evidence"]["accepted"] is False
    assert summary["acceptance"]["accepted"] is False


def test_source_gate_checks_actual_ancestor_cleanliness_and_frozen_code(tmp_path):
    _write_bound_project(tmp_path)
    source = tmp_path / "src/changed_after_freeze.py"
    _write(source, "changed = True\n")
    _commit(tmp_path, "change source after freeze")

    report = verify_project(tmp_path)

    assert report["gates"]["source_revision"]["passed"] is False
    assert "code paths changed" in report["gates"]["source_revision"]["detail"]

    (tmp_path / "untracked.txt").write_text("dirty")
    report = verify_project(tmp_path)
    assert report["gates"]["source_revision"]["passed"] is False
    assert "dirty" in report["gates"]["source_revision"]["detail"]


def test_runtime_gate_rejects_self_declared_image_identity(tmp_path):
    _write_bound_project(tmp_path)
    path = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    protocol = json.loads(path.read_text())
    protocol["runtime_image_id"] = "sha256:" + "c" * 64
    path.write_text(json.dumps(protocol))

    report = verify_project(tmp_path)

    assert report["gates"]["runtime_pinned"]["passed"] is False
    assert "actual Docker image identity" in report["gates"]["runtime_pinned"]["detail"]


def test_mutating_self_declared_summary_cannot_change_frozen_result(tmp_path):
    _write_bound_project(tmp_path)
    path = tmp_path / "results/haichau_network_v2/final/summary.json"
    summary = json.loads(path.read_text())
    summary["acceptance"]["accepted"] = True
    path.write_text(json.dumps(summary))

    report = verify_project(tmp_path)

    assert report["gates"]["hierarchical_statistics"]["passed"] is False
    assert "recompute" in report["gates"]["hierarchical_statistics"]["detail"]


def test_rehashed_demo_replay_still_must_match_verified_run(tmp_path):
    _write_bound_project(tmp_path)
    demo = tmp_path / "results/haichau_network_v2/demo"
    manifest_path = demo / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    replay_path = demo / manifest["replays"][0]["path"]
    replay = json.loads(replay_path.read_text())
    replay["frames"][1]["nodes"]["N00"]["queue"] = 999
    replay_path.write_text(json.dumps(replay))
    manifest["files"][manifest["replays"][0]["path"]] = _digest(replay_path)
    manifest_path.write_text(json.dumps(manifest))

    report = verify_project(tmp_path)

    assert report["gates"]["offline_demo"]["passed"] is False
    assert "verified run" in report["gates"]["offline_demo"]["detail"]


def test_tampered_thesis_artifact_fails_even_if_file_still_exists(tmp_path):
    _write_bound_project(tmp_path)
    table = tmp_path / "paper/generated/haichau_network/haichau_network_results.tex"
    table.write_text("stale self-declared result")

    report = verify_project(tmp_path)

    assert report["gates"]["thesis_artifacts"]["passed"] is False
    assert "hash mismatch" in report["gates"]["thesis_artifacts"]["detail"]


def test_rehashed_pdf_signature_placeholder_is_not_a_usable_thesis(tmp_path):
    _write_bound_project(tmp_path)
    pdf = tmp_path / "paper/thesis_danang.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    release_path = tmp_path / "paper/generated/haichau_network/thesis-release.json"
    release = json.loads(release_path.read_text())
    release["pdf_sha256"] = _digest(pdf)
    release_path.write_text(json.dumps(release))

    report = verify_project(tmp_path)

    assert report["gates"]["thesis_artifacts"]["passed"] is False
    assert "parse" in report["gates"]["thesis_artifacts"]["detail"]


def test_rehashed_mp4_signature_placeholder_is_not_a_usable_fallback(tmp_path):
    _write_bound_project(tmp_path)
    demo = tmp_path / "results/haichau_network_v2/demo"
    manifest_path = demo / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    relative = manifest["fallbacks"]["demo-walkthrough.mp4"]
    fallback = demo / relative
    fallback.write_bytes(b"\x00\x00\x00\x18ftypisom")
    manifest["files"][relative] = _digest(fallback)
    manifest_path.write_text(json.dumps(manifest))

    report = verify_project(tmp_path)

    assert report["gates"]["offline_demo"]["passed"] is False
    assert "decode/parse" in report["gates"]["offline_demo"]["detail"]


def test_malformed_checkpoint_contract_fails_gate_without_crashing(tmp_path):
    _write_bound_project(tmp_path)
    path = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    protocol = json.loads(path.read_text())
    contract = protocol["checkpoints"][0]["checkpoint_contract"]
    contract["hidden_size"] = "not-a-number"
    protocol["checkpoints"][0]["checkpoint_contract_sha256"] = _json_digest(contract)
    path.write_text(json.dumps(protocol))

    report = verify_project(tmp_path)

    assert report["gates"]["five_learning_seeds"]["passed"] is False


@pytest.mark.parametrize("mutate", [
    lambda contract: contract.update({"obs_schema_version": 999}),
    lambda contract: contract.update({"feature_order": [42]}),
    lambda contract: contract.update({"normalization": {"other": 1.0}}),
    lambda contract: contract.update({"action_contract": {"type": "anything"}}),
    lambda contract: contract["network_compatibility"].pop(
        "phase_contract_sha256"),
])
def test_checkpoint_contract_validator_rejects_semantic_drift(mutate):
    protocol = {
        "network_sha256": "a" * 64,
        "phase_contract_sha256": "b" * 64,
        "generator_config_sha256": "c" * 64,
        "experiment_manifest_sha256": "d" * 64,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
    }
    contract = _checkpoint_contract("a" * 64)
    mutate(contract)

    assert _checkpoint_contract_valid(
        contract, protocol, "neighbor_phase_ddqn") is False


def test_checkpoint_gate_binds_protocol_contract_to_contract_file(tmp_path):
    _write_bound_project(tmp_path)
    protocol_path = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    protocol = json.loads(protocol_path.read_text())
    entry = protocol["checkpoints"][0]
    contract_path = tmp_path / entry["contract_path"]
    contract_path.write_text(json.dumps({"controller_family": "forged"}))
    entry["contract_file_sha256"] = _digest(contract_path)
    protocol_path.write_text(json.dumps(protocol))

    report = verify_project(tmp_path)

    assert report["gates"]["five_learning_seeds"]["passed"] is False


def test_checkpoint_gate_rejects_non_npz_weights_even_when_hash_bound(tmp_path):
    _write_bound_project(tmp_path)
    protocol_path = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    protocol = json.loads(protocol_path.read_text())
    entry = protocol["checkpoints"][0]
    weights_path = tmp_path / entry["path"]
    weights_path.write_text("not a NumPy checkpoint")
    entry["sha256"] = _digest(weights_path)
    protocol_path.write_text(json.dumps(protocol))

    report = verify_project(tmp_path)

    assert report["gates"]["five_learning_seeds"]["passed"] is False


def test_non_object_checkpoint_entry_fails_gate_without_crashing(tmp_path):
    _write_bound_project(tmp_path)
    path = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    protocol = json.loads(path.read_text())
    protocol["checkpoints"][0] = None
    path.write_text(json.dumps(protocol))

    report = verify_project(tmp_path)

    assert report["gates"]["five_learning_seeds"]["passed"] is False


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
