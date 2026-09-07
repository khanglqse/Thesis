import pytest

from traffic_rl.eval import runner


def _manifest():
    return {
        "protocol_version": 1,
        "cases": [
            {"case_id": "train-normal", "split": "train", "demand_sha256": "a" * 64,
             "data_source_label": "synthetic", "source_id": "generator-v1"},
            {"case_id": "validation-peak", "split": "validation", "demand_sha256": "b" * 64,
             "data_source_label": "observed_aggregate", "source_id": "tran2025_3dqn_danang"},
            {"case_id": "test-peak", "split": "test", "demand_sha256": "c" * 64,
             "data_source_label": "observed_aggregate", "source_id": "held-out-day"},
        ],
        "runs": [{
            "run_id": "dqn-test-001", "case_id": "test-peak", "controller_id": "dqn-v1",
            "train_seed": 1, "demand_seed": 2, "sim_seed": 3,
        }],
    }


def test_protocol_accepts_disjoint_splits_and_explicit_seed_axes():
    validate = getattr(runner, "validate_experiment_manifest")
    result = validate(_manifest())
    assert result["case_counts"] == {"train": 1, "validation": 1, "test": 1}
    assert result["run_count"] == 1


def test_protocol_rejects_same_demand_artifact_across_validation_and_test():
    validate = getattr(runner, "validate_experiment_manifest")
    manifest = _manifest()
    manifest["cases"][2]["demand_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="demand artifact appears in multiple splits"):
        validate(manifest)


def test_protocol_rejects_run_without_independent_seed_axes():
    validate = getattr(runner, "validate_experiment_manifest")
    manifest = _manifest()
    del manifest["runs"][0]["demand_seed"]
    with pytest.raises(ValueError, match="demand_seed"):
        validate(manifest)


def test_protocol_rejects_observed_case_without_traceable_source():
    validate = getattr(runner, "validate_experiment_manifest")
    manifest = _manifest()
    manifest["cases"][1]["source_id"] = ""
    with pytest.raises(ValueError, match="source_id"):
        validate(manifest)
