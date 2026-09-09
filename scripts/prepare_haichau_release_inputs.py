#!/usr/bin/env python3
"""Build hash-checked final-training inputs for the Hai Chau release freeze."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traffic_rl.research.final_residual_selector import validate_registered_spec
from traffic_rl.research.residual_release import FINAL_SEEDS
from traffic_rl.train.schedule_residual_trainer import validate_config as validate_residual_config
from traffic_rl.research.pilot_schedule_selector import (
    CONFIRMATORY_LEARNING_SEEDS, PRIMARY_LEARNED_CONTROLLER,
    validate_final_resolved_config, validate_final_schedule_selection)

LEARNING_CONTROLLERS = (
    PRIMARY_LEARNED_CONTROLLER,
)
CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    PRIMARY_LEARNED_CONTROLLER,
)
SEEDS = CONFIRMATORY_LEARNING_SEEDS
REQUIRED_ARTIFACTS = (
    "resolved-config.json", "baseline-tuning.json", "run-manifest.json",
)
EVALUATOR_COMMAND = ["python3", "scripts/evaluate_haichau_network.py"]


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


def _yaml(path, label):
    try:
        value = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is not valid YAML: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a YAML mapping" % label)
    return value


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
    if controller != PRIMARY_LEARNED_CONTROLLER:
        raise ValueError("final training controller differs from V3 selection")
    return "final-seed%d" % seed


def _read_final_run(root, training_root, controller, seed, manifest_hash,
                    selected_config):
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
    try:
        validate_final_resolved_config(resolved, selected_config, seed)
    except ValueError as exc:
        raise ValueError("final training resolved config drift: %s" % exc)
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


def build_release_inputs(project_root, manifest, training_root, output_dir,
                         pilot_schedule_selection):
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
    selection = validate_final_schedule_selection(root, pilot_schedule_selection)
    if selection["primary_learned_controller"] != PRIMARY_LEARNED_CONTROLLER:
        raise ValueError("V3 schedule selection learned controller is invalid")
    selected_config = selection["selected_config"]["config"]
    training_configs = {
        PRIMARY_LEARNED_CONTROLLER: selected_config,
    }
    training_config_bindings = {
        PRIMARY_LEARNED_CONTROLLER: {
            "path": selection["selected_config"]["path"],
            "sha256": selection["selected_config"]["sha256"],
        },
    }
    runs = []
    for controller in LEARNING_CONTROLLERS:
        for seed in SEEDS:
            runs.append((controller, seed, _read_final_run(
                root, training_path, controller, seed, manifest_hash,
                training_configs[controller])))
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
        "primary_learned_controller": PRIMARY_LEARNED_CONTROLLER,
        "confirmatory_learning_seeds": list(SEEDS),
        "pilot_schedule_selection": {
            key: value for key, value in selection.items()
            if key != "selected_config"
        },
        "training_config_bindings": training_config_bindings,
        "controller_configs": configs,
        "controller_commands": dict(
            (controller, list(EVALUATOR_COMMAND)) for controller in CONTROLLERS),
    }
    document["pilot_schedule_selection"]["selected_config"] = {
        key: value for key, value in selection["selected_config"].items()
        if key != "config"
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


def _no_test_reference(value):
    if isinstance(value, dict):
        return all((key in ("test_split_accessed", "eligible_for_test_evaluation")
                    or _no_test_reference(key)) and _no_test_reference(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return all(_no_test_reference(item) for item in value)
    if isinstance(value, str):
        return not any(token == "test" or token.startswith("testcase")
                       for token in value.lower().replace("\\", "/").replace("_", "-").split("-") if token)
    return True


def build_residual_release_inputs(project_root, manifest, output_dir,
                                  selector_spec):
    """Write freeze-ready residual bindings only after all selectors pass.

    This is intentionally preparation-only: it reads final selector evidence
    and never opens a test demand file or launches CityFlow.
    """
    root = Path(project_root).resolve()
    manifest_path = _project_file(root, manifest, "experiment manifest")
    source_manifest, resolved = _manifest_configuration(root, manifest_path)
    spec_path = _project_file(root, selector_spec, "final residual selector spec")
    registered = validate_registered_spec(root, spec_path)
    if tuple(registered["learning_seeds"]) != FINAL_SEEDS:
        raise ValueError("residual selector does not bind all five final seeds")
    spec = _yaml(spec_path, "final residual selector spec")
    selected_config_path = _project_file(
        root, spec.get("selected_config"), "selected residual config")
    selected_config = _yaml(selected_config_path, "selected residual config")
    if selected_config.get("controller_family") != "schedule_residual_ddqn":
        raise ValueError("selected residual config has the wrong controller family")

    checkpoints, decisions = [], {}
    for seed in FINAL_SEEDS:
        relative = spec["run_dir_template"].format(seed=seed)
        run_dir = (root / relative).resolve()
        try:
            run_dir.relative_to(root)
        except ValueError:
            raise ValueError("residual final run escapes project root")
        status_path = run_dir / "status.json"
        selection_path = run_dir / spec["selection_filename"]
        rerun_path = run_dir / spec["validation_rerun_filename"]
        status = _json(status_path, "residual final status")
        selection = _json(selection_path, "residual final selection")
        rerun = _json(rerun_path, "residual final validation rerun")
        if (status.get("status") != "complete"
                or status.get("eligible_for_test_evaluation") is not True
                or selection.get("status") != "selected"
                or selection.get("learning_seed") != seed
                or selection.get("test_split_accessed") is not False
                or rerun.get("test_split_accessed") is not False):
            raise ValueError("residual final selector is not eligible for seed %d" % seed)
        hashes = status.get("artifact_sha256")
        if (not isinstance(hashes, dict)
                or hashes.get(selection_path.name) != _sha256(selection_path)
                or hashes.get(rerun_path.name) != _sha256(rerun_path)):
            raise ValueError("residual final selector evidence hash drift")
        winner = selection.get("winner")
        artifacts = winner.get("checkpoint_artifacts", {}) if isinstance(winner, dict) else {}
        record = artifacts.get("checkpoint") if isinstance(artifacts, dict) else None
        if (not isinstance(record, dict) or winner.get("training_step") not in (4, 8, 12)
                or winner.get("checkpoint") != "step-%d" % winner["training_step"]):
            raise ValueError("residual final selected checkpoint is invalid")
        contract = run_dir / record.get("contract_path", "")
        weights = run_dir / record.get("weights_path", "")
        if (not contract.is_file() or not weights.is_file()
                or _sha256(contract) != record.get("contract_sha256")
                or _sha256(weights) != record.get("weights_sha256")):
            raise ValueError("residual final selected checkpoint hash drift")
        contract_doc = _json(contract, "residual selected checkpoint contract")
        if (contract_doc.get("controller_family") != "schedule_residual_ddqn"
                or contract_doc.get("learning_seed") != seed
                or contract_doc.get("training_step") != winner["training_step"]
                or contract_doc.get("mode") != "final"):
            raise ValueError("residual final selected checkpoint contract drift")
        checkpoints.append({
            "controller_id": "schedule_residual_ddqn", "learning_seed": seed,
            "path": _relative(root, weights), "sha256": _sha256(weights),
            "checkpoint_contract": contract_doc,
            "checkpoint_contract_sha256": _canonical_hash(contract_doc),
            "contract_path": _relative(root, contract),
            "contract_file_sha256": _sha256(contract),
            "source_run_dir": _relative(root, run_dir),
            "source_status_sha256": _sha256(status_path),
            "selection": {"path": _relative(root, selection_path),
                          "sha256": _sha256(selection_path)},
            "validation_rerun": {"path": _relative(root, rerun_path),
                                  "sha256": _sha256(rerun_path)},
        })
        decisions[str(seed)] = checkpoints[-1]["selection"]
    if not _no_test_reference({"selectors": decisions}):
        raise ValueError("test reference appears in residual selection evidence")
    # The residual trainer's reward is its explicit queue-integral objective;
    # these environment weights only retain the frozen metric plumbing.
    resolved.update({"step_seconds": 1.0,
                     "spillback_queue_threshold": resolved["normalization"]["capacity_norm"],
                     "reward": {"queue_weight": 1.0,
                                "downstream_block_weight": 0.1,
                                "switch_penalty": 0.05}})
    policy = {key: selected_config[key] for key in
              ("macro", "operational_mode", "critic_units")}
    document = {
        "release_adapter": "schedule_residual_final_v1",
        "resolved_config": resolved,
        "primary_learned_controller": "schedule_residual_ddqn",
        "confirmatory_learning_seeds": list(FINAL_SEEDS),
        "final_residual_selector": {"path": _relative(root, spec_path),
                                    "sha256": _sha256(spec_path),
                                    "decisions": decisions,
                                    "test_split_accessed": False},
        "training_config_bindings": {"schedule_residual_ddqn": {
            "path": _relative(root, selected_config_path),
            "sha256": _sha256(selected_config_path)}},
        "controller_configs": {
            "tuned_fixed": {"green_duration": 25},
            "max_pressure": {"controller_version": 2},
            "hysteretic_mp": {"min_hold_decisions": 3, "switch_threshold": 2.5},
            "schedule_residual_ddqn": policy,
        },
        "controller_commands": dict((controller, list(EVALUATOR_COMMAND)) for controller in (
            "tuned_fixed", "max_pressure", "hysteretic_mp", "schedule_residual_ddqn")),
        "checkpoints": checkpoints,
    }
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path = output_path.resolve()
    try:
        output_path.relative_to(root)
    except ValueError:
        raise ValueError("release output directory must remain inside project root")
    target = output_path / "residual-final-controller-configs.json"
    encoded = _encoded_json(document)
    _assert_write_once(target, encoded)
    _write_once(target, encoded)
    return {"controller_configs": _relative(root, target),
            "selected_checkpoints": len(checkpoints)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument(
        "--manifest", default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument(
        "--training-root", default="results/haichau_network_v2/training")
    parser.add_argument(
        "--output-dir", default="results/haichau_network_v2/release-inputs")
    parser.add_argument(
        "--pilot-schedule-selection",
        default="results/haichau_network_v2/training/pilot-v3-schedule-selection.json")
    parser.add_argument("--residual-final-selector")
    args = parser.parse_args(argv)
    try:
        if args.residual_final_selector:
            result = build_residual_release_inputs(
                args.project_root, args.manifest, args.output_dir,
                args.residual_final_selector)
        else:
            result = build_release_inputs(
                args.project_root, args.manifest, args.training_root, args.output_dir,
                args.pilot_schedule_selection)
    except ValueError as exc:
        print("release inputs refused: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
