#!/usr/bin/env python3
"""Build hash-checked final-training inputs for the Hai Chau release freeze."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


LEARNING_CONTROLLERS = (
    "shared_ddqn_legacy",
    "neighbor_phase_ddqn",
)
CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)
SEEDS = (11, 12, 13, 14, 15)
REQUIRED_ARTIFACTS = (
    "resolved-config.json", "baseline-tuning.json", "run-manifest.json",
)
EVALUATOR_COMMAND = ["python3", "scripts/evaluate_haichau_network.py"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json(path, label):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("%s is not valid JSON: %s" % (label, exc))


def _project_file(root, value, label):
    if not isinstance(value, str) or not value:
        raise ValueError("%s path is required" % label)
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside project root" % label)
    if not path.is_file():
        raise ValueError("%s is missing" % label)
    return path


def _relative(root, path):
    return str(Path(path).resolve().relative_to(root))


def _number(value, label, positive=False):
    if isinstance(value, bool):
        raise ValueError("%s must be numeric" % label)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be numeric" % label)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError("%s must be %s" % (
            label, "finite and positive" if positive else "finite"))
    return number


def _expected_directory(controller, seed):
    if controller == "neighbor_phase_ddqn":
        return "final-seed%d" % seed
    return "legacy-final-seed%d" % seed


def _read_final_run(root, training_root, controller, seed, manifest_hash):
    directory = training_root / _expected_directory(controller, seed)
    if not directory.is_dir():
        raise ValueError("final training directory is missing: %s" % (
            _relative(root, directory)))
    status_path = directory / "status.json"
    status = _json(status_path, "training status")
    if (status.get("status") != "complete"
            or status.get("eligible_for_test_evaluation") is not True):
        raise ValueError("final training is not complete and eligible: %s" % (
            _relative(root, directory)))
    hashes = status.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("training artifact hashes are missing")
    documents = {}
    for name in REQUIRED_ARTIFACTS:
        path = directory / name
        expected = hashes.get(name)
        if not path.is_file() or not isinstance(expected, str):
            raise ValueError("final training artifact is missing: %s" % name)
        if _sha256(path) != expected:
            raise ValueError("training artifact hash drift: %s" % name)
        documents[name] = _json(path, "training artifact %s" % name)
    run_manifest = documents["run-manifest.json"]
    if (run_manifest.get("controller_id") != controller
            or run_manifest.get("learning_seed") != seed
            or run_manifest.get("mode") != "final"):
        raise ValueError("final training identity drift")
    resolved = documents["resolved-config.json"]
    if (resolved.get("mode") != "final"
            or resolved.get("learning_seed") != seed):
        raise ValueError("final training resolved config drift")
    reward = resolved.get("reward")
    if not isinstance(reward, dict):
        raise ValueError("final training reward is missing")
    normalized_reward = dict(
        (field, _number(reward.get(field), "reward.%s" % field))
        for field in (
            "queue_weight", "downstream_block_weight", "switch_penalty"))
    tuning = documents["baseline-tuning.json"]
    if not isinstance(tuning, dict):
        raise ValueError("baseline tuning is invalid")
    tuning_hash = tuning.get("tuning_sha256")
    source_tuning = dict(tuning)
    source_tuning.pop("tuning_sha256", None)
    if (not isinstance(tuning_hash, str)
            or tuning_hash != _canonical_hash(source_tuning)):
        raise ValueError("baseline tuning hash drift")
    selected = tuning.get("selected") if isinstance(tuning, dict) else None
    if not isinstance(selected, dict):
        raise ValueError("baseline tuning selection is missing")
    duration = _number(
        selected.get("fixed_green_duration"), "selected fixed green duration",
        positive=True)
    binding = tuning.get("binding")
    if (not isinstance(binding, dict)
            or binding.get("manifest_sha256") != manifest_hash):
        raise ValueError("baseline tuning manifest hash drift")
    return {
        "path": _relative(root, directory),
        "reward": normalized_reward,
        "fixed_green_duration": duration,
    }


def _manifest_configuration(root, manifest_path):
    manifest = _json(manifest_path, "experiment manifest")
    if manifest.get("protocol_version") != 2:
        raise ValueError("experiment manifest must use protocol version 2")
    network = manifest.get("network")
    phase = manifest.get("phase_contract")
    preprocessing = manifest.get("preprocessing")
    simulation = manifest.get("simulation")
    if not isinstance(network, dict) or not isinstance(phase, dict):
        raise ValueError("experiment manifest network artifacts are missing")
    network_path = _project_file(root, network.get("path"), "network")
    phase_path = _project_file(root, phase.get("path"), "phase contract")
    if _sha256(network_path) != network.get("sha256"):
        raise ValueError("network hash drift")
    if _sha256(phase_path) != phase.get("sha256"):
        raise ValueError("phase contract hash drift")
    if not isinstance(preprocessing, dict) or not isinstance(simulation, dict):
        raise ValueError("experiment manifest evaluator configuration is missing")
    normalization = {
        "count_norm": _number(preprocessing.get("count_norm"), "count_norm", True),
        "capacity_norm": _number(preprocessing.get("capacity_norm"), "capacity_norm", True),
    }
    normalized_simulation = dict(
        (field, _number(simulation.get(field), "simulation.%s" % field, True))
        for field in ("action_interval", "yellow_time", "min_green", "maximum_red"))
    for field in ("action_interval", "yellow_time", "min_green", "maximum_red"):
        if normalized_simulation[field].is_integer():
            normalized_simulation[field] = int(normalized_simulation[field])
    return manifest, {
        "network_path": _relative(root, network_path),
        "phase_contract_path": _relative(root, phase_path),
        "phase_contract_sha256": phase["sha256"],
        "normalization": normalization,
        "simulation": normalized_simulation,
    }


def _encoded_json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _assert_write_once(path, encoded):
    if path.exists() and (not path.is_file() or path.read_text() != encoded):
        raise ValueError("refusing to replace existing release input: %s" % path)


def _write_once(path, encoded):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(encoded)
    temporary.replace(path)


def build_release_inputs(project_root, manifest, training_root, output_dir):
    """Validate final training artifacts and write freeze-ready input JSON."""
    root = Path(project_root).resolve()
    manifest_path = _project_file(root, manifest, "experiment manifest")
    training_path = Path(training_root)
    if not training_path.is_absolute():
        training_path = root / training_path
    training_path = training_path.resolve()
    try:
        training_path.relative_to(root)
    except ValueError:
        raise ValueError("training root must remain inside project root")
    manifest_document, resolved = _manifest_configuration(root, manifest_path)
    manifest_hash = _canonical_hash(manifest_document)
    runs = []
    for controller in LEARNING_CONTROLLERS:
        for seed in SEEDS:
            runs.append((controller, seed, _read_final_run(
                root, training_path, controller, seed, manifest_hash)))
    rewards = set(json.dumps(run[2]["reward"], sort_keys=True)
                  for run in runs)
    if len(rewards) != 1:
        raise ValueError("final training reward differs between runs")
    durations = set(run[2]["fixed_green_duration"] for run in runs)
    if len(durations) != 1:
        raise ValueError("selected fixed green duration differs between final runs")
    fixed_duration = next(iter(durations))
    resolved["reward"] = runs[0][2]["reward"]
    resolved["step_seconds"] = 1.0
    resolved["spillback_queue_threshold"] = resolved["normalization"]["capacity_norm"]
    index = dict((controller, {}) for controller in LEARNING_CONTROLLERS)
    for controller, seed, run in runs:
        index[controller][str(seed)] = run["path"]
    configs = dict((controller, {"controller_version": 2})
                   for controller in CONTROLLERS)
    configs["tuned_fixed"]["green_duration"] = fixed_duration
    configs["hysteretic_mp"].update({
        "min_hold_decisions": 3, "switch_threshold": 2.5,
    })
    document = {
        "resolved_config": resolved,
        "controller_configs": configs,
        "controller_commands": dict(
            (controller, list(EVALUATOR_COMMAND)) for controller in CONTROLLERS),
    }
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path = output_path.resolve()
    try:
        output_path.relative_to(root)
    except ValueError:
        raise ValueError("release output directory must remain inside project root")
    index_path = output_path / "training-index.json"
    config_path = output_path / "final-controller-configs.json"
    index_encoded = _encoded_json(index)
    config_encoded = _encoded_json(document)
    _assert_write_once(index_path, index_encoded)
    _assert_write_once(config_path, config_encoded)
    _write_once(index_path, index_encoded)
    _write_once(config_path, config_encoded)
    return {
        "training_index": _relative(root, index_path),
        "controller_configs": _relative(root, config_path),
        "fixed_green_duration": configs["tuned_fixed"]["green_duration"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument(
        "--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument(
        "--training-root", default="results/haichau_network_v2/training")
    parser.add_argument(
        "--output-dir", default="results/haichau_network_v2/release-inputs")
    args = parser.parse_args(argv)
    try:
        result = build_release_inputs(
            args.project_root, args.manifest, args.training_root, args.output_dir)
    except ValueError as exc:
        print("release inputs refused: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
