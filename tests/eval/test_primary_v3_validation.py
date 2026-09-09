import hashlib
import json
import shutil

import pytest

import traffic_rl.eval.primary_v3_validation as primary_validation
from traffic_rl.eval.network_campaign import canonical_sha256
from traffic_rl.eval.primary_v3_validation import (
    PRIMARY_CONTROLLERS,
    validate_primary_v3_protocol,
    validate_primary_v3_reference,
)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protocol(root):
    case_path = root / "results/haichau_network_v2/final/case-manifest.json"
    cases = [{
        "case_id": "test_%02d" % index,
        "split": "test",
        "regime": ("normal", "am_peak", "pm_peak")[index // 5],
        "demand_seed": 100 + index,
        "simulator_seed": 200 + index,
        "scheduled_vehicles": 600,
        "horizon_steps": 3600,
        "demand_path": "flows/test-%02d.json" % index,
        "demand_sha256": "%064x" % (index + 1),
    } for index in range(15)]
    case_sha = _write(case_path, {"schema_version": 1, "cases": cases})
    checkpoints = []
    for seed in range(12, 17):
        run_dir = root / ("training/seed-%d" % seed)
        weights = run_dir / "checkpoint/weights.npz"
        digest = _write(weights, ("weights-%d" % seed).encode("ascii"))
        contract = {
            "controller_family": "neighbor_phase_ddqn",
            "training_step": 12,
        }
        contract_path = weights.parent / "contract.json"
        contract_file_sha = _write(contract_path, contract)
        source_artifacts = {
            "checkpoint/weights.npz": digest,
            "checkpoint/contract.json": contract_file_sha,
        }
        for name in ("validation.json", "selection.json", "resolved-config.json",
                     "baseline-tuning.json", "run-manifest.json"):
            source_artifacts[name] = _write(
                run_dir / name, {"seed": seed, "artifact": name})
        status_sha = _write(run_dir / "status.json", {
            "status": "complete",
            "eligible_for_test_evaluation": True,
            "artifact_sha256": source_artifacts,
        })
        checkpoints.append({
            "controller_id": "neighbor_phase_ddqn",
            "learning_seed": seed,
            "path": str(weights.relative_to(root)),
            "sha256": digest,
            "validation_eligible": True,
            "checkpoint_contract": contract,
            "checkpoint_contract_sha256": canonical_sha256(contract),
            "contract_path": str(contract_path.relative_to(root)),
            "contract_file_sha256": contract_file_sha,
            "source_run_dir": str(run_dir.relative_to(root)),
            "source_status_sha256": status_sha,
            "source_artifacts": source_artifacts,
        })
    protocol = {
        "protocol_version": 1,
        "evidence_namespace": "haichau_network_v2",
        "selection": {"path": "selection.json"},
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": [12, 13, 14, 15, 16],
        "acceptance_rules": {"required_learning_seeds": [12, 13, 14, 15, 16]},
        "case_manifest_path": str(case_path.relative_to(root)),
        "case_manifest_sha256": case_sha,
        "network_sha256": "1" * 64,
        "viewer_network_sha256": "2" * 64,
        "phase_contract_sha256": "3" * 64,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "runtime_digest": "sha256:" + "4" * 64,
        "runtime_image": "example/cityflow@sha256:" + "4" * 64,
        "runtime_image_id": "sha256:" + "5" * 64,
        "runtime_dockerfile_path": "docker/haichau-evaluation.Dockerfile",
        "runtime_dockerfile_sha256": "6" * 64,
        "code_commit": "7" * 40,
        "agent_ids": ["N%02d" % index for index in range(53)],
        "resolved_config": {
            "network_path": "network/roadnet.json",
            "phase_contract_path": "network/phase.json",
            "phase_contract_sha256": "3" * 64,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {"action_interval": 10, "min_green": 20,
                           "maximum_red": 180},
            "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.1,
                       "switch_penalty": 0.05},
        },
        "controller_configs": {
            "tuned_fixed": {"green_duration": 25},
            "max_pressure": {"controller_version": 2},
            "hysteretic_mp": {"min_hold_decisions": 2,
                              "switch_threshold": 1.0},
            "neighbor_phase_ddqn": {"controller_version": 3},
        },
        "controller_commands": dict(
            (controller, ["python3", "scripts/evaluate_haichau_network.py"])
            for controller in PRIMARY_CONTROLLERS),
        "checkpoints": checkpoints,
    }
    path = root / "results/haichau_network_v2/final/frozen-protocol.json"
    _write(path, protocol)
    return path, protocol


def _expected_runs(root, protocol):
    case_path = root / protocol["case_manifest_path"]
    case_document = json.loads(case_path.read_text())
    return primary_validation.expand_runs(
        primary_validation.bind_frozen_manifest(case_document, protocol),
        [12, 13, 14, 15, 16], PRIMARY_CONTROLLERS)


def test_primary_protocol_invokes_authoritative_selection_validator_first(
        tmp_path, monkeypatch):
    path, protocol = _protocol(tmp_path)
    (tmp_path / protocol["case_manifest_path"]).unlink()
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: (_ for _ in ()).throw(
            ValueError("selected arm eligible:false")))

    with pytest.raises(ValueError, match="eligible:false"):
        validate_primary_v3_protocol(tmp_path, path)


def test_primary_validator_rejects_complete_looking_noncanonical_copy(
        tmp_path, monkeypatch):
    path, protocol = _protocol(tmp_path)
    canonical = path.parent
    _write(canonical / "campaign-manifest.json", {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": _expected_runs(tmp_path, protocol),
    })
    _write(canonical / "summary.json", {"complete": True})
    forged = tmp_path / "copied-primary/final"
    shutil.copytree(str(canonical), str(forged))
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: {"winner": {"arm": "schedule_bc_rehearsal"}})

    with pytest.raises(ValueError, match="canonical"):
        validate_primary_v3_reference(
            tmp_path, forged / "frozen-protocol.json")


@pytest.mark.parametrize("mutation,error", [
    ("ineligible", "validation-eligible"),
    ("missing", "checkpoint is missing"),
])
def test_primary_protocol_rejects_ineligible_or_missing_checkpoint(
        tmp_path, monkeypatch, mutation, error):
    path, protocol = _protocol(tmp_path)
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: {"winner": {"arm": "schedule_bc_rehearsal"}})
    if mutation == "ineligible":
        protocol["checkpoints"][0]["validation_eligible"] = False
    else:
        (tmp_path / protocol["checkpoints"][0]["path"]).unlink()
    _write(path, protocol)

    with pytest.raises(ValueError, match=error):
        validate_primary_v3_protocol(tmp_path, path)


def test_primary_reference_rejects_empty_campaign_before_campaign_verifier(
        tmp_path, monkeypatch):
    path, protocol = _protocol(tmp_path)
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: {"winner": {"arm": "schedule_bc_rehearsal"}})
    expected = _expected_runs(tmp_path, protocol)
    called = []
    monkeypatch.setattr(
        primary_validation, "verify_campaign",
        lambda *args, **kwargs: called.append(True))
    _write(path.parent / "campaign-manifest.json", {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": [],
    })

    with pytest.raises(ValueError, match="frozen protocol"):
        validate_primary_v3_reference(tmp_path, path)

    assert called == []


def test_primary_reference_rejects_incomplete_campaign_and_stale_summary(
        tmp_path, monkeypatch):
    path, protocol = _protocol(tmp_path)
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: {"winner": {"arm": "schedule_bc_rehearsal"}})
    expected = _expected_runs(tmp_path, protocol)
    _write(path.parent / "campaign-manifest.json", {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": expected,
    })
    _write(path.parent / "summary.json", {"stale": True})
    monkeypatch.setattr(
        primary_validation, "verify_campaign",
        lambda *args, **kwargs: {"complete": 119, "total": 120})

    with pytest.raises(ValueError, match="incomplete"):
        validate_primary_v3_reference(tmp_path, path)

    monkeypatch.setattr(
        primary_validation, "verify_campaign",
        lambda *args, **kwargs: {"complete": 120, "total": 120})
    monkeypatch.setattr(primary_validation, "_load_verified_rows", lambda *args: [])
    monkeypatch.setattr(primary_validation, "aggregate_campaign", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(primary_validation, "evaluate_acceptance", lambda value: {"accepted": True})

    with pytest.raises(ValueError, match="summary differs"):
        validate_primary_v3_reference(tmp_path, path)


def test_primary_reference_accepts_only_exact_completed_recomputed_release(
        tmp_path, monkeypatch):
    path, protocol = _protocol(tmp_path)
    monkeypatch.setattr(
        primary_validation, "validate_frozen_schedule_selection",
        lambda *args: {"winner": {"arm": "schedule_bc_rehearsal"}})
    expected = _expected_runs(tmp_path, protocol)
    _write(path.parent / "campaign-manifest.json", {
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": expected,
    })
    monkeypatch.setattr(
        primary_validation, "verify_campaign",
        lambda *args, **kwargs: {"complete": 120, "total": 120})
    monkeypatch.setattr(primary_validation, "_load_verified_rows", lambda *args: [])
    monkeypatch.setattr(primary_validation, "aggregate_campaign", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(primary_validation, "evaluate_acceptance", lambda value: {"accepted": True})
    summary = {
        "study_scope": {
            "controlled_signals": 53,
            "demand_label": "synthetic network demand constrained by Da Nang evidence",
            "evidence_namespace": "haichau_network_v2",
        },
        "summary": {"ok": True},
        "acceptance": {"accepted": True},
    }
    _write(path.parent / "summary.json", summary)

    result = validate_primary_v3_reference(tmp_path, path)

    assert result["run_count"] == 120
    assert result["controllers"] == list(PRIMARY_CONTROLLERS)
