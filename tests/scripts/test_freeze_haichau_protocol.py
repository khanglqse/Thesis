import hashlib
import json
import subprocess

import pytest

from scripts.freeze_haichau_protocol import (
    _canonical_hash, _contains_test_reference, freeze_protocol)
from scripts import verify_haichau_thesis
from traffic_rl.agents.dqn import SharedDQN
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.sim.phase_encoder import FEATURES


RUNTIME_DIGEST = "sha256:" + "a" * 64
RUNTIME_IMAGE = "registry.example/traffic-rl@" + RUNTIME_DIGEST
RUNTIME_IMAGE_ID = "sha256:" + "b" * 64
LEARNED = ("shared_ddqn_legacy", "neighbor_phase_ddqn")
CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)


@pytest.mark.parametrize("value", [
    "testcase-01", "results/test/case.json", "TEST-01", "test_normal_case",
])
def test_test_reference_detection_covers_ids_and_path_components(value):
    assert _contains_test_reference(value) is True


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    path.write_text(value)


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root)] + list(args), universal_newlines=True).strip()


def _commit(root):
    subprocess.check_call(["git", "init", "-q", str(root)])
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD")


def _contract(network_sha, phase_contract_sha, generator_config_sha,
              manifest_sha, controller_family):
    return {
        "obs_schema_version": 2,
        "feature_order": (list(FEATURES)
                          if controller_family == "neighbor_phase_ddqn"
                          else ["lane_count_0"]),
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "hidden_size": 128,
        "action_contract": ({
            "type": "phase_rows", "version": 1,
            "mask_type": "boolean_selectable_green_rows",
            "padding_actions_selectable": False,
        } if controller_family == "neighbor_phase_ddqn" else {
            "type": "fixed_vector", "version": 1,
            "mask_type": "boolean_phase_index",
            "padding_actions_selectable": False,
            "n_actions": 3,
        }),
        "network_compatibility": {
            "network_sha256": network_sha,
            "phase_contract_sha256": phase_contract_sha,
            "generator_config_sha256": generator_config_sha,
            "manifest_sha256": manifest_sha,
        },
        "controller_family": controller_family,
    }


def _training_artifact(root, controller, seed, network_sha, phase_contract_sha,
                       generator_config_sha, manifest_sha, validation_case,
                       include_test=False):
    relative = "release-training/%s/final-seed%d" % (controller, seed)
    run_dir = root / relative
    contract = _contract(
        network_sha, phase_contract_sha, generator_config_sha, manifest_sha,
        controller)
    if controller == "neighbor_phase_ddqn":
        model = PhaseScoringDDQN(len(FEATURES), hidden=128, lr=0.001, seed=seed)
    else:
        model = SharedDQN(1, 3, hidden=128, lr=0.001, seed=seed, dueling=True)
    model.save_bundle(str(run_dir / "checkpoint"), contract)
    model.save_bundle(str(run_dir / "checkpoints/step-80"), contract)
    validation = {
        "step-80": {
            "rows": [{"case_id": validation_case}],
            "score": {"eligible": True},
        }
    }
    if include_test:
        validation["step-80"]["rows"].append({"case_id": "test_normal_demand101"})
    _write(run_dir / "validation.json", validation)
    _write(run_dir / "selection.json", {
        "status": "eligible",
        "selected_checkpoint": "step-80",
        "eligible_for_test_evaluation": True,
        "score": {"eligible": True},
    })
    _write(run_dir / "resolved-config.json", {
        "mode": "final", "learning_seed": seed,
        "network_sha256": network_sha,
        "run": {"episodes": 80, "horizon_seconds": 3600},
    })
    _write(run_dir / "baseline-tuning.json", {
        "selection_cases": [validation_case],
    })
    _write(run_dir / "run-manifest.json", {
        "controller_id": controller,
        "learning_seed": seed,
    })
    artifacts = {}
    for name in (
            "checkpoint/weights.npz", "checkpoint/contract.json",
            "validation.json", "selection.json", "resolved-config.json",
            "baseline-tuning.json", "run-manifest.json"):
        artifacts[name] = _sha256(run_dir / name)
    _write(run_dir / "status.json", {
        "status": "complete", "eligible_for_test_evaluation": True,
        "artifact_sha256": artifacts,
    })
    return relative


def _fixture(root):
    agent_ids = ["N%02d" % number for number in range(53)]
    roadnet = root / "release/roadnet.json"
    viewer = root / "release/viewer.json"
    _write(roadnet, {"intersections": agent_ids})
    _write(viewer, {"nodes": agent_ids})
    network_sha = _sha256(roadnet)
    phase_contract = root / "release/phase-contract.json"
    generator_config = root / "release/generator-config.json"
    _write(phase_contract, {"phase_contract": 1})
    _write(generator_config, {"generator_config": 1})
    cases = []
    for split, count in (("train", 9), ("validation", 6), ("test", 15)):
        for number in range(count):
            scenario = ("normal", "am_peak", "pm_peak")[number % 3]
            flow = root / ("release/%s-%02d.json" % (split, number))
            _write(flow, "%s-%02d" % (split, number))
            cases.append({
                "case_id": "%s_%s_%02d" % (split, scenario, number),
                "split": split,
                "scenario": scenario,
                "demand_seed": 100 + number,
                "sim_seed": 200 + number,
                "flow_path": str(flow.relative_to(root)),
                "flow_sha256": _sha256(flow),
                "scheduled_vehicles": 1000 + number,
            })
    manifest = {
        "protocol_version": 2,
        "network": {
            "controlled_signals": 53, "agent_ids": agent_ids,
            "path": str(roadnet.relative_to(root)), "sha256": network_sha,
        },
        "phase_contract": {
            "path": str(phase_contract.relative_to(root)),
            "sha256": _sha256(phase_contract),
        },
        "generator_config_path": str(generator_config.relative_to(root)),
        "generator_config_sha256": _sha256(generator_config),
        "runtime": {"base_image_digest": RUNTIME_DIGEST},
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
        "cases": cases,
    }
    manifest_path = root / "release/experiment-manifest.json"
    _write(manifest_path, manifest)
    manifest_sha = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    validation_case = next(case["case_id"] for case in cases
                           if case["split"] == "validation")
    dockerfile = root / "docker/haichau-evaluation.Dockerfile"
    _write(dockerfile, "FROM %s\n" % RUNTIME_IMAGE)
    controller_configs = dict(
        (controller, {"controller_version": 2}) for controller in CONTROLLERS)
    controller_configs["tuned_fixed"]["green_duration"] = 30
    controller_configs["hysteretic_mp"].update({
        "min_hold_decisions": 3, "switch_threshold": 2.5,
    })
    config = {
        "resolved_config": {
            "network_path": str(roadnet.relative_to(root)),
            "phase_contract_path": str(phase_contract.relative_to(root)),
            "phase_contract_sha256": _sha256(phase_contract),
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
        "controller_commands": dict(
            (controller, ["python3", "scripts/evaluate_haichau_network.py"])
            for controller in CONTROLLERS),
    }
    config_path = root / "release/controller-configs.json"
    _write(config_path, config)
    index = dict((controller, {}) for controller in LEARNED)
    for controller in LEARNED:
        for seed in range(11, 16):
            index[controller][str(seed)] = _training_artifact(
                root, controller, seed, network_sha,
                manifest["phase_contract"]["sha256"],
                manifest["generator_config_sha256"], manifest_sha,
                validation_case)
    index_path = root / "release/training-index.json"
    _write(index_path, index)
    commit = _commit(root)
    return {
        "agent_ids": agent_ids,
        "commit": commit,
        "config": config_path,
        "dockerfile": dockerfile,
        "index": index_path,
        "manifest": manifest_path,
        "network_sha": network_sha,
        "phase_contract_sha": manifest["phase_contract"]["sha256"],
        "generator_config_sha": manifest["generator_config_sha256"],
        "manifest_sha": manifest_sha,
        "roadnet": roadnet,
        "viewer": viewer,
    }


def _runtime(image):
    assert image == RUNTIME_IMAGE
    return {
        "runtime_image": RUNTIME_IMAGE,
        "runtime_image_id": RUNTIME_IMAGE_ID,
        "repo_digests": [RUNTIME_IMAGE],
    }


def _add_precomputed_tuning_provenance(root, relative):
    run_dir = root / relative
    tuning_path = run_dir / "baseline-tuning.json"
    manifest = json.loads((root / "release/experiment-manifest.json").read_text())
    validation_cases = [case for case in manifest["cases"]
                        if case["split"] == "validation"]
    resolved_path = run_dir / "resolved-config.json"
    resolved = json.loads(resolved_path.read_text())
    resolved["baseline"] = {
        "controller": "validation_tuned_fixed",
        "search_green_durations": [30],
    }
    resolved["simulation"] = {"action_interval": 10}
    _write(resolved_path, resolved)
    tuning = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "search_space": {"fixed_green_duration": [30]},
        "selected": {"fixed_green_duration": 30},
        "candidates": [{
            "fixed_green_duration": 30,
            "mean_queue_integral_vehicle_seconds": 100.0,
            "rows": [{
                "case_id": case["case_id"],
                "scenario": case["scenario"],
                "queue_integral_vehicle_seconds": 100.0,
                "completion_rate": 1.0,
            } for case in validation_cases],
        }],
        "binding": {
            "manifest_sha256": _canonical_hash(manifest),
            "network_sha256": manifest["network"]["sha256"],
            "generator_config_sha256": manifest["generator_config_sha256"],
            "runtime": manifest["runtime"],
            "validation_case_hashes": dict(
                (case["case_id"], case["flow_sha256"])
                for case in validation_cases),
            "horizon_seconds": 3600,
            "action_interval": 10,
            "queue_objective": {
                "schema_version": 2,
                "network_queue": "per_step_waiting",
                "entry_pending": "due_not_inserted",
                "future_departures": "unreleased_excluded",
            },
        },
    }
    tuning["tuning_sha256"] = _canonical_hash(tuning)
    _write(tuning_path, tuning)
    provenance_path = run_dir / "baseline-tuning-provenance.json"
    _write(provenance_path, {
        "schema_version": 1,
        "strategy": "precomputed_baseline_tuning",
        "source_kind": "file",
        "source_path": "cache/baseline-tuning.json",
        "source_artifact_sha256": "f" * 64,
        "copied_artifact_path": "baseline-tuning.json",
        "copied_artifact_sha256": _sha256(tuning_path),
        "tuning_sha256": tuning["tuning_sha256"],
    })
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"] = {
        "mode": "precomputed",
        "tuning_sha256": tuning["tuning_sha256"],
        "copied_artifact_path": "baseline-tuning.json",
        "copied_artifact_sha256": _sha256(tuning_path),
        "provenance_path": "baseline-tuning-provenance.json",
        "provenance_sha256": _sha256(provenance_path),
    }
    _write(run_manifest_path, run_manifest)
    for contract_path in (run_dir / "checkpoint/contract.json",
                          run_dir / "checkpoints/step-80/contract.json"):
        contract = json.loads(contract_path.read_text())
        contract["baseline_tuning_provenance_sha256"] = run_manifest[
            "baseline_tuning"]["provenance_sha256"]
        contract["baseline_tuning_artifact_sha256"] = run_manifest[
            "baseline_tuning"]["copied_artifact_sha256"]
        _write(contract_path, contract)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
    status["artifact_sha256"]["resolved-config.json"] = _sha256(resolved_path)
    status["artifact_sha256"]["checkpoint/contract.json"] = _sha256(
        run_dir / "checkpoint/contract.json")
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    status["artifact_sha256"]["baseline-tuning-provenance.json"] = _sha256(
        provenance_path)
    _write(status_path, status)


def _refresh_precomputed_tuning_hashes(run_dir):
    tuning_path = run_dir / "baseline-tuning.json"
    tuning = json.loads(tuning_path.read_text())
    tuning["tuning_sha256"] = _canonical_hash(
        dict((key, value) for key, value in tuning.items()
             if key != "tuning_sha256"))
    _write(tuning_path, tuning)
    provenance_path = run_dir / "baseline-tuning-provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["copied_artifact_sha256"] = _sha256(tuning_path)
    provenance["tuning_sha256"] = tuning["tuning_sha256"]
    _write(provenance_path, provenance)
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"]["tuning_sha256"] = tuning["tuning_sha256"]
    run_manifest["baseline_tuning"]["copied_artifact_sha256"] = _sha256(
        tuning_path)
    run_manifest["baseline_tuning"]["provenance_sha256"] = _sha256(
        provenance_path)
    _write(run_manifest_path, run_manifest)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["baseline-tuning.json"] = _sha256(tuning_path)
    status["artifact_sha256"]["baseline-tuning-provenance.json"] = _sha256(
        provenance_path)
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    _write(status_path, status)


def test_freeze_audits_hash_bound_precomputed_baseline_provenance(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["11"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "add cache provenance")

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    checkpoint = next(item for item in protocol["checkpoints"]
                      if item["controller_id"] == "neighbor_phase_ddqn"
                      and item["learning_seed"] == 11)
    assert "baseline-tuning-provenance.json" in checkpoint["source_artifacts"]


def test_freeze_rejects_precomputed_baseline_provenance_hash_drift(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["11"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    run_dir = tmp_path / relative
    run_manifest_path = run_dir / "run-manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text())
    run_manifest["baseline_tuning"]["provenance_sha256"] = "0" * 64
    _write(run_manifest_path, run_manifest)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["run-manifest.json"] = _sha256(run_manifest_path)
    _write(status_path, status)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "drift cache provenance")

    with pytest.raises(ValueError, match="provenance hash drift"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_revalidates_precomputed_baseline_binding(tmp_path):
    fixture = _fixture(tmp_path)
    relative = json.loads(fixture["index"].read_text())["neighbor_phase_ddqn"]["11"]
    _add_precomputed_tuning_provenance(tmp_path, relative)
    run_dir = tmp_path / relative
    tuning_path = run_dir / "baseline-tuning.json"
    tuning = json.loads(tuning_path.read_text())
    del tuning["binding"]
    _write(tuning_path, tuning)
    _refresh_precomputed_tuning_hashes(run_dir)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove cache binding")

    with pytest.raises(ValueError, match="binding"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_writes_hash_bound_protocol_from_all_final_eligible_cells(tmp_path):
    fixture = _fixture(tmp_path)

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    output = tmp_path / "results/haichau_network_v2/final/frozen-protocol.json"
    assert json.loads(output.read_text()) == protocol
    assert protocol["code_commit"] == fixture["commit"]
    assert protocol["agent_ids"] == fixture["agent_ids"]
    assert protocol["network_sha256"] == fixture["network_sha"]
    assert protocol["phase_contract_sha256"] == fixture["phase_contract_sha"]
    assert protocol["generator_config_sha256"] == fixture["generator_config_sha"]
    assert protocol["experiment_manifest_sha256"] == fixture["manifest_sha"]
    assert protocol["runtime_image_id"] == RUNTIME_IMAGE_ID
    assert set(protocol["controller_configs"]) == set(CONTROLLERS)
    assert len(protocol["checkpoints"]) == 10
    assert all(entry["validation_eligible"] for entry in protocol["checkpoints"])
    assert all("validation.json" in entry["source_artifacts"]
               for entry in protocol["checkpoints"])
    assert all(entry["contract_path"].endswith("checkpoint/contract.json")
               for entry in protocol["checkpoints"])
    assert all(entry["contract_file_sha256"] == _sha256(
        tmp_path / entry["contract_path"])
               for entry in protocol["checkpoints"])
    assert protocol["acceptance_rules"]["required_learning_seeds"] == [11, 12, 13, 14, 15]
    assert protocol["case_manifest_sha256"] == _sha256(
        tmp_path / protocol["case_manifest_path"])
    assert protocol["network_manifest_sha256"] == _sha256(
        tmp_path / protocol["network_manifest_path"])
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "freeze protocol")
    assert verify_haichau_thesis._network_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._case_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._checkpoint_gate(tmp_path, protocol)["passed"] is True
    assert verify_haichau_thesis._acceptance_rules(protocol)["bootstrap_samples"] == 10000


def test_freeze_requires_and_preserves_scheduled_vehicle_counts(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = json.loads(fixture["manifest"].read_text())
    expected = dict((case["case_id"], case["scheduled_vehicles"])
                    for case in manifest["cases"])

    protocol = freeze_protocol(
        tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
        fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
        runtime_inspector=_runtime)

    release_manifest = json.loads(
        (tmp_path / protocol["case_manifest_path"]).read_text())
    assert dict((case["case_id"], case["scheduled_vehicles"])
                for case in release_manifest["cases"]) == expected


def test_freeze_rejects_case_without_scheduled_vehicle_count(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = json.loads(fixture["manifest"].read_text())
    del manifest["cases"][0]["scheduled_vehicles"]
    _write(fixture["manifest"], manifest)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "remove scheduled vehicle count")

    with pytest.raises(ValueError, match="scheduled_vehicles"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_overwrite_or_any_test_case_in_selection_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    relative = index["neighbor_phase_ddqn"]["11"]
    validation = tmp_path / relative / "validation.json"
    document = json.loads(validation.read_text())
    document["step-80"]["rows"].append({"case_id": "test_normal_demand00"})
    _write(validation, document)
    status = tmp_path / relative / "status.json"
    status_doc = json.loads(status.read_text())
    status_doc["artifact_sha256"]["validation.json"] = _sha256(validation)
    _write(status, status_doc)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "inject test evidence")

    with pytest.raises(ValueError, match="test.*selection"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_requires_the_selected_checkpoint_bundle_to_match_final_checkpoint(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["shared_ddqn_legacy"]["11"]
    (run_dir / "checkpoints/step-80/weights.npz").unlink()
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "remove selected checkpoint")

    with pytest.raises(ValueError, match="selected checkpoint"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_a_short_horizon_disguised_as_final_training(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["12"]
    resolved = run_dir / "resolved-config.json"
    document = json.loads(resolved.read_text())
    document["run"]["horizon_seconds"] = 120
    _write(resolved, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["resolved-config.json"] = _sha256(resolved)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "short final run")

    with pytest.raises(ValueError, match="full 3600-second horizon"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_status_artifact_paths_that_escape_the_training_run(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["13"]
    status = run_dir / "status.json"
    document = json.loads(status.read_text())
    escaped = tmp_path / "release/experiment-manifest.json"
    document["artifact_sha256"]["../../../release/experiment-manifest.json"] = _sha256(escaped)
    _write(status, document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "escape training status")

    with pytest.raises(ValueError, match="escapes the training run"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_test_metric_keys_in_checkpoint_selection_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["shared_ddqn_legacy"]["14"]
    validation = run_dir / "validation.json"
    document = json.loads(validation.read_text())
    document["step-80"]["test_metrics"] = {"queue_integral": 1.0}
    _write(validation, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["validation.json"] = _sha256(validation)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "inject test metric key")

    with pytest.raises(ValueError, match="test metric.*selection"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


def test_freeze_refuses_conflicting_legacy_contract_aliases(tmp_path):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["15"]
    contract = run_dir / "checkpoint/contract.json"
    document = json.loads(contract.read_text())
    document["hidden"] = 64
    _write(contract, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["checkpoint/contract.json"] = _sha256(contract)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "conflicting old checkpoint alias")

    with pytest.raises(ValueError, match="alias drift"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)


@pytest.mark.parametrize(
    "mutate, error",
        [
            (lambda contract: contract["action_contract"].update({"version": 2}),
             "action contract drift"),
            (lambda contract: contract.update(
                {"feature_order": ["forged_%d" % index for index in range(12)]}),
             "feature order drift"),
            (lambda contract: contract["normalization"].update(
                {"count_norm": 99.0}),
             "normalization is invalid"),
            (lambda contract: contract["network_compatibility"].update(
            {"phase_contract_sha256": "0" * 64}),
         "network compatibility drift"),
    ],
)
def test_freeze_requires_exact_neighbor_contract(tmp_path, mutate, error):
    fixture = _fixture(tmp_path)
    index = json.loads(fixture["index"].read_text())
    run_dir = tmp_path / index["neighbor_phase_ddqn"]["11"]
    contract = run_dir / "checkpoint/contract.json"
    document = json.loads(contract.read_text())
    mutate(document)
    _write(contract, document)
    status = run_dir / "status.json"
    status_document = json.loads(status.read_text())
    status_document["artifact_sha256"]["checkpoint/contract.json"] = _sha256(contract)
    _write(status, status_document)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "mutate neighbor contract")

    with pytest.raises(ValueError, match=error):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)

    final = tmp_path / "results/haichau_network_v2/final"
    final.mkdir(parents=True)
    _write(final / "frozen-protocol.json", "{}")
    with pytest.raises(ValueError, match="overwrite"):
        freeze_protocol(
            tmp_path, fixture["manifest"], fixture["viewer"], fixture["config"],
            fixture["index"], RUNTIME_IMAGE, fixture["dockerfile"],
            runtime_inspector=_runtime)
