"""Hashing and validation helpers for immutable research artifacts."""

import hashlib
import json
import re
from pathlib import Path


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_SPLITS = ("train", "validation", "test")


def sha256_file(path):
    """Return the SHA-256 hex digest of a file's exact bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value):
    """Hash a JSON-compatible value using stable key and whitespace rules."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_artifact(root, record):
    """Verify a repository-relative artifact record and return its path."""
    relative = Path(record.get("path", ""))
    expected = record.get("sha256", "")
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("artifact path must be a safe relative path")
    if not isinstance(expected, str) or not _SHA256_RE.match(expected):
        raise ValueError("artifact sha256 must be 64 lowercase hex characters")
    path = Path(root) / relative
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError("hash mismatch: %s" % record.get("path"))
    return path


def validate_disjoint_splits(cases):
    """Require train/validation/test cases and prevent cross-split reuse."""
    counts = {split: 0 for split in _REQUIRED_SPLITS}
    seed_splits = {}
    hash_splits = {}
    route_family_splits = {}
    for case in cases:
        split = case.get("split")
        if split not in counts:
            raise ValueError("unknown split: %s" % split)
        counts[split] += 1
        demand_seed = case.get("demand_seed")
        seed_splits.setdefault(demand_seed, set()).add(split)
        flow_hash = case.get("flow_sha256")
        if flow_hash is not None:
            hash_splits.setdefault(flow_hash, set()).add(split)
        for route_hash in case.get("route_family_hashes", []):
            route_family_splits.setdefault(route_hash, set()).add(split)

    for seed, splits in seed_splits.items():
        if len(splits) > 1:
            raise ValueError("demand seed %s appears in multiple splits" % seed)
    for flow_hash, splits in hash_splits.items():
        if len(splits) > 1:
            raise ValueError("flow hash %s appears in multiple splits" % flow_hash)
    for route_hash, splits in route_family_splits.items():
        if len(splits) > 1:
            raise ValueError(
                "route family hash %s appears in multiple splits" % route_hash
            )
    if any(count == 0 for count in counts.values()):
        raise ValueError("train, validation and test splits must each be non-empty")
    return {split: counts[split] for split in sorted(counts)}
