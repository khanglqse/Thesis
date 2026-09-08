#!/usr/bin/env python3
"""Launch five hash-checked Hai Chau V3 confirmatory training runs.

The launcher deliberately never resumes a partially written training directory.
Delete or repair that directory after inspection, then rerun this command.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traffic_rl.research.pilot_schedule_selector import (
    CONFIRMATORY_LEARNING_SEEDS, FINAL_CHECKPOINTS,
    PRIMARY_LEARNED_CONTROLLER,
    validate_final_resolved_config, validate_final_schedule_selection)
CONTROLLERS = (PRIMARY_LEARNED_CONTROLLER,)
SEEDS = CONFIRMATORY_LEARNING_SEEDS
PINNED_IMAGE_TAG = "traffic-rl-cityflow-research:v2"
PINNED_PLATFORM = "linux/amd64"
REQUIRED_ARTIFACTS = (
    "baseline-tuning.json",
    "baseline-tuning-provenance.json",
    "checkpoint/contract.json",
    "checkpoint/weights.npz",
    "replay-coverage.json",
    "resolved-config.json",
    "run-manifest.json",
    "selection.json",
    "summary.json",
    "train-log.json",
    "validation.json",
) + tuple(
    "checkpoints/%s/%s" % (checkpoint, name)
    for checkpoint in FINAL_CHECKPOINTS
    for name in ("contract.json", "weights.npz"))
Job = namedtuple("Job", "controller seed output command")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
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
        raise ValueError("%s must be a mapping" % label)
    return value


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _inside(root, path, label):
    root = Path(root).resolve()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project root" % label)
    return resolved


def _container_path(root, path, label):
    resolved = _inside(root, path, label)
    return "/work/" + str(resolved.relative_to(Path(root).resolve()))


def _output_name(controller, seed):
    if controller != PRIMARY_LEARNED_CONTROLLER:
        raise ValueError("final training controller differs from V3 selection")
    return "final-seed%d" % seed


def _artifact_path(run_dir, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("status artifact path is invalid")
    candidate = (Path(run_dir) / relative).resolve()
    try:
        candidate.relative_to(Path(run_dir).resolve())
    except ValueError:
        raise ValueError("status artifact path escapes the training run")
    return candidate


def _verified_artifacts(run_dir, status):
    hashes = status.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("training status has no artifact hashes")
    for relative in REQUIRED_ARTIFACTS:
        if relative not in hashes:
            raise ValueError("training status is missing %s" % relative)
    for relative, expected in hashes.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected or "")):
            raise ValueError("training status has an invalid artifact hash")
        artifact = _artifact_path(run_dir, relative)
        if not artifact.is_file():
            raise ValueError("training artifact is missing: %s" % relative)
        if _sha256(artifact) != expected:
            raise ValueError("training artifact hash mismatch: %s" % relative)


def inspect_existing_job(job, baseline_artifact, training_config):
    """Return pending or skipped; reject every non-verified existing output."""
    run_dir = Path(job.output)
    if not run_dir.exists():
        return "pending"
    if not run_dir.is_dir():
        raise ValueError("training output is not a directory: %s" % run_dir)
    status_path = run_dir / "status.json"
    if not status_path.is_file():
        raise ValueError("existing output is not a fully verified completed run: %s" % run_dir)
    status = _read_json(status_path, "training status")
    if (status.get("status") != "complete"
            or status.get("eligible_for_test_evaluation") is not True):
        raise ValueError("existing output is not a fully verified completed run: %s" % run_dir)
    _verified_artifacts(run_dir, status)
    resolved = _read_json(run_dir / "resolved-config.json", "resolved training config")
    selected = _read_yaml(training_config, "selected training config")
    validate_final_resolved_config(resolved, selected, job.seed)
    run_manifest = _read_json(run_dir / "run-manifest.json", "training run manifest")
    if (run_manifest.get("controller_id") != job.controller
            or run_manifest.get("learning_seed") != job.seed):
        raise ValueError("completed output has the wrong controller/seed identity")
    expected_baseline = _sha256(baseline_artifact)
    tuning = run_manifest.get("baseline_tuning")
    provenance = _read_json(run_dir / "baseline-tuning-provenance.json",
                            "baseline tuning provenance")
    if (not isinstance(tuning, dict) or tuning.get("mode") != "precomputed"
            or provenance.get("source_artifact_sha256") != expected_baseline):
        raise ValueError("completed output does not use the supplied baseline artifact")
    return "skipped"


def _training_config_path(root, training_config):
    path = _inside(root, training_config, "selected V3 training config")
    return path, _read_yaml(path, "selected V3 training config")


def validate_schedule_training_config(root, schedule_selection, training_config):
    """Bind the sole learned controller config to the immutable V3 decision."""
    root = Path(root).resolve()
    selection = validate_final_schedule_selection(root, schedule_selection)
    config_path, config = _training_config_path(root, training_config)
    if (selection["primary_learned_controller"] != PRIMARY_LEARNED_CONTROLLER
            or config_path != root / selection["selected_config"]["path"]
            or _sha256(config_path) != selection["selected_config"]["sha256"]
            or config != selection["selected_config"]["config"]):
        raise ValueError("final training config differs from V3 schedule selection")
    return selection, {
        "path": str(config_path.relative_to(root)),
        "sha256": _sha256(config_path),
    }


def build_jobs(root, manifest_path, baseline_artifact, training_dir,
               training_config):
    root = Path(root).resolve()
    manifest_path = _inside(root, manifest_path, "manifest")
    baseline_artifact = _inside(root, baseline_artifact, "baseline artifact")
    training_dir = _inside(root, training_dir, "training directory")
    training_config, _ = _training_config_path(root, training_config)
    if not baseline_artifact.is_file():
        raise ValueError("shared precomputed baseline artifact is required")
    manifest = _read_json(manifest_path, "experiment manifest")
    runtime = manifest.get("runtime") if isinstance(manifest, dict) else None
    if not isinstance(runtime, dict):
        raise ValueError("experiment manifest runtime is required")
    if runtime.get("derived_image_tag") != PINNED_IMAGE_TAG:
        raise ValueError("experiment manifest does not use the pinned training image")
    if runtime.get("platform") != PINNED_PLATFORM:
        raise ValueError("experiment manifest does not use the pinned training platform")
    jobs = []
    for controller in CONTROLLERS:
        for seed in SEEDS:
            output = training_dir / _output_name(controller, seed)
            command = (
                "docker", "run", "--rm", "--platform", PINNED_PLATFORM,
                "-v", "%s:/work" % root, "-w", "/work", PINNED_IMAGE_TAG,
                "python3", "scripts/train_haichau_network.py", "--mode", "final",
                "--learning-seed", str(seed), "--controller-family", controller,
                "--manifest", _container_path(root, manifest_path, "manifest"),
                "--config", _container_path(
                    root, training_config, "selected training config"),
                "--output", _container_path(root, output, "training output"),
                "--baseline-tuning-artifact", _container_path(
                    root, baseline_artifact, "baseline artifact"),
            )
            jobs.append(Job(controller, seed, output, command))
    return jobs


def _job_record(root, job, state):
    logs = Path("results") / "haichau_network_v2" / "training" / "final-campaign-logs"
    prefix = "%s-seed%d" % (job.controller, job.seed)
    return {
        "controller_family": job.controller,
        "learning_seed": job.seed,
        "output_dir": str(Path(job.output).resolve().relative_to(Path(root).resolve())),
        "state": state,
        "command": list(job.command),
        "stdout_log": str(logs / (prefix + ".stdout.log")),
        "stderr_log": str(logs / (prefix + ".stderr.log")),
    }


def _execute_job(root, job, record, baseline_artifact, training_config, runner):
    stdout = Path(root) / record["stdout_log"]
    stderr = Path(root) / record["stderr_log"]
    stdout.parent.mkdir(parents=True, exist_ok=True)
    with stdout.open("w") as out, stderr.open("w") as err:
        try:
            result = runner(list(job.command), cwd=str(root), stdout=out, stderr=err)
        except Exception as exc:
            return 1, "%s: %s" % (type(exc).__name__, exc)
    if result.returncode:
        return int(result.returncode), "training command exited %d" % result.returncode
    try:
        if inspect_existing_job(job, baseline_artifact, training_config) != "skipped":
            raise ValueError("training output is not a fully verified completed run")
    except ValueError as exc:
        return 1, str(exc)
    return 0, None


def run_campaign(root, manifest_path, baseline_artifact, training_dir,
                 status_path, training_config, max_concurrency=2,
                 runner=subprocess.run, schedule_selection=None):
    if max_concurrency < 1:
        raise ValueError("max concurrency must be at least one")
    if schedule_selection is None:
        raise ValueError("pilot V3 schedule selection is required for final training")
    root = Path(root).resolve()
    baseline_artifact = _inside(root, baseline_artifact, "baseline artifact")
    config_path, _ = _training_config_path(root, training_config)
    selection, config_binding = validate_schedule_training_config(
        root, schedule_selection, training_config)
    jobs = build_jobs(
        root, manifest_path, baseline_artifact, training_dir, training_config)
    records = []
    pending = []
    for job in jobs:
        state = inspect_existing_job(
            job, baseline_artifact, config_path)
        record = _job_record(root, job, state)
        records.append(record)
        if state == "pending":
            pending.append((job, record))
    status_path = _inside(root, status_path, "campaign status")
    campaign = {
        "schema_version": 1,
        "status": "running",
        "max_concurrency": max_concurrency,
        "baseline_artifact": str(baseline_artifact.relative_to(root)),
        "baseline_artifact_sha256": _sha256(baseline_artifact),
        "primary_learned_controller": PRIMARY_LEARNED_CONTROLLER,
        "confirmatory_learning_seeds": list(SEEDS),
        "training_config_binding": config_binding,
        "jobs": records,
    }
    campaign["pilot_schedule_selection"] = {
        key: value for key, value in selection.items()
        if key != "selected_config"
    }
    campaign["pilot_schedule_selection"]["selected_config"] = {
        key: value for key, value in selection["selected_config"].items()
        if key != "config"
    }
    _write_json(status_path, campaign)
    failure = False
    active = {}
    iterator = iter(pending)
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        while not failure and len(active) < max_concurrency:
            try:
                job, record = next(iterator)
            except StopIteration:
                break
            record["state"] = "running"
            active[executor.submit(
                _execute_job, root, job, record, baseline_artifact,
                config_path, runner)] = record
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                record = active.pop(future)
                returncode, error = future.result()
                record["returncode"] = returncode
                record["state"] = "completed" if returncode == 0 else "failed"
                if error:
                    record["error"] = error
                if returncode:
                    failure = True
            _write_json(status_path, campaign)
            while not failure and len(active) < max_concurrency:
                try:
                    job, record = next(iterator)
                except StopIteration:
                    break
                record["state"] = "running"
                active[executor.submit(
                    _execute_job, root, job, record, baseline_artifact,
                    config_path, runner)] = record
    campaign["status"] = "failed" if failure else "complete"
    _write_json(status_path, campaign)
    return campaign


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-tuning-artifact", required=True)
    parser.add_argument(
        "--config", default="configs/haichau_training_v3_final_selected.yaml",
        help="config emitted by the V3 schedule pilot selector")
    parser.add_argument(
        "--pilot-schedule-selection",
        default="results/haichau_network_v2/training/pilot-v3-schedule-selection.json",
        help="immutable V3 schedule pilot decision required before final training")
    parser.add_argument("--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--training-dir", default="results/haichau_network_v2/training")
    parser.add_argument("--status", default="results/haichau_network_v2/training/final-campaign-status.json")
    parser.add_argument("--max-concurrency", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        result = run_campaign(
            PROJECT_ROOT, PROJECT_ROOT / args.manifest,
            PROJECT_ROOT / args.baseline_tuning_artifact,
            PROJECT_ROOT / args.training_dir, PROJECT_ROOT / args.status,
            PROJECT_ROOT / args.config,
            max_concurrency=args.max_concurrency,
            schedule_selection=PROJECT_ROOT / args.pilot_schedule_selection)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
