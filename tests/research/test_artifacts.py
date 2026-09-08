import json

import pytest


def test_sha256_helpers_are_stable_and_canonical(tmp_path):
    from traffic_rl.research.artifacts import canonical_sha256, sha256_file

    path = tmp_path / "value.json"
    path.write_text('{"b":2,"a":1}\n')
    assert sha256_file(path) == "21e15bd7f77a30fef3f21276e3d98cb363575f826663a994911cb1bc95674f01"
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_verify_artifact_rejects_hash_drift(tmp_path):
    from traffic_rl.research.artifacts import sha256_file, verify_artifact

    (tmp_path / "a.json").write_text('{"x":1}\n')
    record = {"path": "a.json", "sha256": sha256_file(tmp_path / "a.json")}
    assert verify_artifact(tmp_path, record) == tmp_path / "a.json"
    (tmp_path / "a.json").write_text('{"x":2}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_artifact(tmp_path, record)


def test_verify_artifact_rejects_unsafe_or_malformed_records(tmp_path):
    from traffic_rl.research.artifacts import verify_artifact

    with pytest.raises(ValueError, match="relative path"):
        verify_artifact(tmp_path, {"path": "../escape", "sha256": "0" * 64})
    with pytest.raises(ValueError, match="sha256"):
        verify_artifact(tmp_path, {"path": "a.json", "sha256": "nope"})


def test_split_validator_rejects_reused_demand_seed():
    from traffic_rl.research.artifacts import validate_disjoint_splits

    cases = [
        {"split": "train", "demand_seed": 11, "flow_sha256": "a" * 64},
        {"split": "test", "demand_seed": 11, "flow_sha256": "b" * 64},
    ]
    with pytest.raises(ValueError, match="multiple splits"):
        validate_disjoint_splits(cases)


def test_split_validator_requires_nonempty_splits_and_unique_flow_hashes():
    from traffic_rl.research.artifacts import validate_disjoint_splits

    cases = [
        {"split": "train", "demand_seed": 11, "flow_sha256": "a" * 64},
        {"split": "validation", "demand_seed": 31, "flow_sha256": "b" * 64},
        {"split": "test", "demand_seed": 101, "flow_sha256": "c" * 64},
    ]
    assert validate_disjoint_splits(cases) == {"test": 1, "train": 1, "validation": 1}

    cases[-1]["flow_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="flow hash.*multiple splits"):
        validate_disjoint_splits(cases)

    with pytest.raises(ValueError, match="non-empty"):
        validate_disjoint_splits(cases[:2])


def test_split_validator_rejects_route_family_hash_across_splits():
    from traffic_rl.research.artifacts import validate_disjoint_splits

    cases = [
        {"split": "train", "demand_seed": 11, "flow_sha256": "a" * 64,
         "route_family_hashes": ["1" * 64]},
        {"split": "validation", "demand_seed": 31, "flow_sha256": "b" * 64,
         "route_family_hashes": ["2" * 64]},
        {"split": "test", "demand_seed": 101, "flow_sha256": "c" * 64,
         "route_family_hashes": ["1" * 64]},
    ]
    with pytest.raises(ValueError, match="route family hash.*multiple splits"):
        validate_disjoint_splits(cases)
