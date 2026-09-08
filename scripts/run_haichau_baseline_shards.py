#!/usr/bin/env python3
"""Precompute the fixed-time validation grid in independently verified shards.

Each Docker process receives a read-only copy of the training configuration whose
only changed value is a subset of ``baseline.search_green_durations``.  The
launcher treats every pre-existing shard directory as ambiguous state: inspect it
before deleting it and starting a fresh immutable run.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from traffic_rl.train.network_trainer import (
    _search_space, _tuning_binding, _validate_precomputed_tuning,
    canonical_json_sha256, resolve_training_config)


PINNED_IMAGE_TAG = "traffic-rl-cityflow-research:v2"
PINNED_PLATFORM = "linux/amd64"
Shard = namedtuple("Shard", "index durations config artifact command stdout stderr")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is invalid: %s" % (label, exc))


def _read_yaml(path, label):
    try:
        value = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is invalid: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % label)
    return value


def _write_json(path, value, readonly=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary), str(path))
    if readonly:
        path.chmod(0o444)


def _write_yaml(path, value, readonly=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(yaml.safe_dump(
        value, default_flow_style=False, allow_unicode=False))
    os.replace(str(temporary), str(path))
    if readonly:
        path.chmod(0o444)


def _inside(root, path, label):
    root = Path(root).resolve()
    candidate = Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project root" % label)
    return candidate


def _container_path(root, path, label):
    candidate = _inside(root, path, label)
    return "/work/" + str(candidate.relative_to(Path(root).resolve()))


def _validation_cases(manifest):
    cases = [case for case in manifest.get("cases", [])
             if isinstance(case, dict) and case.get("split") == "validation"]
    if not cases:
        raise ValueError("experiment manifest has no validation cases")
    return cases


def _validate_runtime(manifest):
    runtime = manifest.get("runtime") if isinstance(manifest, dict) else None
    if not isinstance(runtime, dict):
        raise ValueError("experiment manifest runtime is required")
    if runtime.get("derived_image_tag") != PINNED_IMAGE_TAG:
        raise ValueError("experiment manifest does not use the pinned training image")
    if runtime.get("platform") != PINNED_PLATFORM:
        raise ValueError("experiment manifest does not use the pinned training platform")


def expected_binding(manifest, validation_cases, resolved_config):
    """Return the trainer's binding for a final-mode duration shard."""
    return _tuning_binding(
        manifest, validation_cases,
        int(resolved_config["run"]["horizon_seconds"]), resolved_config)


def _shard_config(config, durations):
    shard = copy.deepcopy(config)
    baseline = shard.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("training config baseline is required")
    baseline["search_green_durations"] = list(durations)
    return shard


def _build_shards(root, manifest_path, config_path, artifact_path,
                  work_dir, durations_per_shard):
    manifest = _read_json(manifest_path, "experiment manifest")
    _validate_runtime(manifest)
    config = _read_yaml(config_path, "training config")
    resolved = resolve_training_config(config, "final", 11)
    if not isinstance(manifest.get("simulation"), dict):
        raise ValueError("experiment manifest simulation is required")
    resolved["simulation"] = manifest["simulation"]
    durations = _search_space(resolved)["fixed_green_duration"]
    validation_cases = _validation_cases(manifest)
    binding = expected_binding(manifest, validation_cases, resolved)
    if durations_per_shard < 1:
        raise ValueError("durations per shard must be at least one")

    shard_root = Path(work_dir) / "shards"
    logs_root = Path(work_dir) / "logs"
    shards = []
    for index, start in enumerate(range(0, len(durations), durations_per_shard)):
        subset = durations[start:start + durations_per_shard]
        name = "%03d" % index
        # train_haichau_network writes runtime configs beside its artifact, so
        # each shard needs its own directory as well as its own YAML file.
        shard_dir = shard_root / name
        shard_config_path = shard_dir / "config.yaml"
        shard_artifact_path = shard_dir / "baseline-tuning.json"
        _write_yaml(shard_config_path, _shard_config(config, subset), readonly=True)
        _write_json(shard_dir / "shard.json", {
            "schema_version": 1,
            "index": index,
            "durations": subset,
            "source_config_sha256": _sha256(config_path),
            "shard_config_sha256": _sha256(shard_config_path),
            "manifest_sha256": canonical_json_sha256(manifest),
        }, readonly=True)
        command = (
            "docker", "run", "--rm", "--platform", PINNED_PLATFORM,
            "-v", "%s:/work" % Path(root).resolve(), "-w", "/work",
            PINNED_IMAGE_TAG, "python3", "scripts/train_haichau_network.py",
            "--mode", "final", "--learning-seed", "11",
            "--manifest", _container_path(root, manifest_path, "manifest"),
            "--config", _container_path(root, shard_config_path, "shard config"),
            "--precompute-baseline-tuning", _container_path(
                root, shard_artifact_path, "shard artifact"),
        )
        shards.append(Shard(
            index, subset, shard_config_path, shard_artifact_path, command,
            logs_root / (name + ".stdout.log"),
            logs_root / (name + ".stderr.log")))
    return manifest, config, resolved, validation_cases, binding, durations, shards


def _record(root, shard, state):
    root = Path(root).resolve()
    return {
        "index": shard.index,
        "durations": list(shard.durations),
        "config": str(shard.config.resolve().relative_to(root)),
        "artifact": str(shard.artifact.resolve().relative_to(root)),
        "stdout_log": str(shard.stdout.resolve().relative_to(root)),
        "stderr_log": str(shard.stderr.resolve().relative_to(root)),
        "command": list(shard.command),
        "state": state,
    }


def _execute_shard(root, shard, runner):
    shard.stdout.parent.mkdir(parents=True, exist_ok=True)
    with shard.stdout.open("w") as stdout, shard.stderr.open("w") as stderr:
        try:
            result = runner(list(shard.command), cwd=str(root), stdout=stdout,
                            stderr=stderr)
        except Exception as exc:
            return 1, "%s: %s" % (type(exc).__name__, exc)
    returncode = int(getattr(result, "returncode", 1))
    if returncode:
        return returncode, "shard command exited %d" % returncode
    if not shard.artifact.is_file():
        return 1, "shard artifact is missing"
    return 0, None


def _run_shards(root, shards, records, max_concurrency, runner, status_path,
                status):
    if max_concurrency < 1:
        raise ValueError("max concurrency must be at least one")
    active = {}
    pending = iter(zip(shards, records))
    failed = False
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        while not failed and len(active) < max_concurrency:
            try:
                shard, record = next(pending)
            except StopIteration:
                break
            record["state"] = "running"
            active[executor.submit(_execute_shard, root, shard, runner)] = record
        while active:
            done, unused = wait(active, return_when=FIRST_COMPLETED)
            del unused
            for future in done:
                record = active.pop(future)
                returncode, error = future.result()
                record["returncode"] = returncode
                record["state"] = "completed" if returncode == 0 else "failed"
                if error:
                    record["error"] = error
                if returncode:
                    failed = True
            _write_json(status_path, status)
            while not failed and len(active) < max_concurrency:
                try:
                    shard, record = next(pending)
                except StopIteration:
                    break
                record["state"] = "running"
                active[executor.submit(_execute_shard, root, shard, runner)] = record
    if failed:
        raise ValueError("one or more baseline tuning shards failed; inspect shard logs")


def _merge_shards(shards, binding, full_config, validation_cases, durations):
    candidates = {}
    for shard in shards:
        tuning = _read_json(shard.artifact, "shard tuning artifact")
        shard_config = _read_yaml(shard.config, "shard training config")
        shard_resolved = resolve_training_config(shard_config, "final", 11)
        shard_resolved["simulation"] = full_config["simulation"]
        # This checks the SHA, every row, and that this artifact contains only
        # the duration subset assigned to its immutable config.
        try:
            _validate_precomputed_tuning(
                tuning, binding, shard_resolved, validation_cases)
        except ValueError as exc:
            raise ValueError("shard binding or artifact validation failed: %s" % exc)
        if tuning.get("binding") != binding:
            raise ValueError("shard baseline tuning binding drift")
        for candidate in tuning["candidates"]:
            duration = candidate["fixed_green_duration"]
            if duration in candidates:
                raise ValueError("duplicate fixed-green duration across shards")
            candidates[duration] = candidate
    if set(candidates) != set(durations) or len(candidates) != len(durations):
        raise ValueError("shard candidates do not cover the full configured search space")
    ordered = [candidates[duration] for duration in durations]
    selected = min(ordered, key=lambda row: (
        row["mean_queue_integral_vehicle_seconds"],
        row["fixed_green_duration"]))
    merged = {
        "schema_version": 1,
        "method": "validation_grid_search",
        "search_space": {"fixed_green_duration": list(durations)},
        "selected": {"fixed_green_duration": selected["fixed_green_duration"]},
        "candidates": ordered,
        "binding": binding,
    }
    merged["tuning_sha256"] = canonical_json_sha256(merged)
    _validate_precomputed_tuning(merged, binding, full_config, validation_cases)
    return merged


def run_precompute_shards(root, manifest_path, config_path, artifact_path,
                          max_concurrency=2, durations_per_shard=1,
                          runner=subprocess.run):
    """Run a fresh shard set, verify it, and atomically publish one artifact."""
    root = Path(root).resolve()
    manifest_path = _inside(root, manifest_path, "manifest")
    config_path = _inside(root, config_path, "training config")
    artifact_path = _inside(root, artifact_path, "baseline tuning artifact")
    if artifact_path.exists():
        raise ValueError("refusing to overwrite existing baseline tuning artifact")
    work_dir = root / ".baseline-tuning-shards" / artifact_path.stem
    if work_dir.exists():
        raise ValueError("partial shard state exists; inspect or remove it before retrying")
    work_dir.mkdir(parents=True)
    status_path = work_dir / "status.json"
    try:
        (manifest, unused_config, full_config, validation_cases, binding,
         durations, shards) = _build_shards(
             root, manifest_path, config_path, artifact_path, work_dir,
             int(durations_per_shard))
        del manifest, unused_config
        records = [_record(root, shard, "pending") for shard in shards]
        status = {
            "schema_version": 1,
            "status": "running",
            "max_concurrency": int(max_concurrency),
            "durations_per_shard": int(durations_per_shard),
            "baseline_artifact": str(artifact_path.relative_to(root)),
            "full_search_space": {"fixed_green_duration": list(durations)},
            "jobs": records,
        }
        _write_json(status_path, status)
        _run_shards(root, shards, records, int(max_concurrency), runner,
                    status_path, status)
        merged = _merge_shards(
            shards, binding, full_config, validation_cases, durations)
        _write_json(artifact_path, merged)
        status["status"] = "complete"
        status["tuning_sha256"] = merged["tuning_sha256"]
        status["baseline_artifact_sha256"] = _sha256(artifact_path)
        _write_json(status_path, status)
        return status
    except Exception as exc:
        failure = {"schema_version": 1, "status": "failed", "error": str(exc)}
        if status_path.exists():
            prior = _read_json(status_path, "shard status")
            prior.update(failure)
            failure = prior
        _write_json(status_path, failure)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--config", default="configs/haichau_training_v2.yaml")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--durations-per-shard", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        result = run_precompute_shards(
            PROJECT_ROOT, PROJECT_ROOT / args.manifest, PROJECT_ROOT / args.config,
            PROJECT_ROOT / args.artifact, args.max_concurrency,
            args.durations_per_shard)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
