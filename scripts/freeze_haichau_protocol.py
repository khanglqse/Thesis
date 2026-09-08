#!/usr/bin/env python3
"""Freeze the hash-bound input protocol for the Hai Chau final campaign.

This command deliberately prepares evidence only.  It does not train, evaluate,
or read a test metric.  The campaign runner consumes the resulting protocol.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from traffic_rl.eval.release_identity import inspect_runtime_image, verify_git_checkout
from traffic_rl.agents.dqn import SharedDQN
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.sim.phase_encoder import FEATURES


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINAL_RELATIVE = "results/haichau_network_v2/final"
LEARNING_CONTROLLERS = ("shared_ddqn_legacy", "neighbor_phase_ddqn")
CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)
LEARNING_SEEDS = (11, 12, 13, 14, 15)
REGIMES = ("normal", "am_peak", "pm_peak")
CHECKPOINT_FIELDS = frozenset((
    "obs_schema_version", "feature_order", "normalization", "hidden_size",
    "action_contract", "network_compatibility", "controller_family",
))
NEIGHBOR_ACTION_CONTRACT = {
    "type": "phase_rows",
    "version": 1,
    "mask_type": "boolean_selectable_green_rows",
    "padding_actions_selectable": False,
}
LEGACY_ACTION_CONTRACT = {
    "type": "fixed_vector", "version": 1,
    "mask_type": "boolean_phase_index",
    "padding_actions_selectable": False,
    "n_actions": 3,
}
REQUIRED_TRAINING_ARTIFACTS = (
    "checkpoint/weights.npz", "checkpoint/contract.json", "validation.json",
    "selection.json", "resolved-config.json", "baseline-tuning.json",
    "run-manifest.json",
)


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


def _relative_file(root, value, label):
    root = Path(root).resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    if not path.is_file():
        raise ValueError("%s is missing: %s" % (label, relative))
    return path, str(relative)


def _run(argv, root):
    completed = subprocess.run(
        list(argv), cwd=str(root), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, universal_newlines=True)
    if completed.returncode:
        raise ValueError("command failed (%s): %s" % (
            " ".join(argv), completed.stderr.strip()))
    return completed.stdout.strip()


def _current_clean_commit(root):
    head = _run(("git", "rev-parse", "HEAD"), root)
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("current Git HEAD is not a full commit")
    # Training artifacts are data inputs, not mutable release code.  All code
    # paths remain subject to verify_git_checkout's descendant/diff checks.
    verify_git_checkout(
        root, head,
        allowed_dirty_prefixes=("results/haichau_network_v2/training",))
    return head


def _assert_hash(path, expected, label):
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected or "")):
        raise ValueError("%s requires a SHA-256 hash" % label)
    actual = _sha256(path)
    if actual != expected:
        raise ValueError("%s hash drift" % label)
    return actual


def _contains_test_reference(value):
    if isinstance(value, dict):
        return any(
            ((key != "eligible_for_test_evaluation"
              and _contains_test_reference(key))
             or _contains_test_reference(item))
            for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_test_reference(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower().replace("\\", "/")
        tokens = [token for token in re.split(r"[/\s_.-]+", lowered) if token]
        return any(token == "test" or token.startswith("testcase")
                   for token in tokens)
    return False


def _checkpoint_contract(contract, controller, compatibility, normalization):
    if not isinstance(contract, dict) or not CHECKPOINT_FIELDS.issubset(contract):
        raise ValueError("checkpoint contract schema is incomplete")
    if not isinstance(contract["feature_order"], list) or not contract["feature_order"]:
        raise ValueError("checkpoint contract feature order is invalid")
    if contract["normalization"] != normalization:
        raise ValueError("checkpoint contract normalization is invalid")
    if not isinstance(contract["action_contract"], dict):
        raise ValueError("checkpoint contract action contract is invalid")
    hidden = contract["hidden_size"]
    if isinstance(hidden, bool) or not isinstance(hidden, int) or hidden <= 0:
        raise ValueError("checkpoint contract hidden size is invalid")
    compatible = contract["network_compatibility"]
    if not isinstance(compatible, dict) or compatible != compatibility:
        raise ValueError("checkpoint contract network compatibility drift")
    if contract["controller_family"] != controller:
        raise ValueError("checkpoint contract controller family drift")
    if controller == "neighbor_phase_ddqn" \
            and contract["feature_order"] != list(FEATURES):
        raise ValueError("neighbor checkpoint feature order drift")
    expected_action = (NEIGHBOR_ACTION_CONTRACT
                       if controller == "neighbor_phase_ddqn"
                       else LEGACY_ACTION_CONTRACT)
    if contract["action_contract"] != expected_action:
        raise ValueError("checkpoint action contract drift")
    aliases = (
        ("hidden", contract["hidden_size"]),
        ("network_sha256", compatible["network_sha256"]),
        ("count_norm", contract["normalization"]["count_norm"]),
        ("capacity_norm", contract["normalization"]["capacity_norm"]),
    )
    for legacy_name, canonical_value in aliases:
        if legacy_name not in contract or canonical_value is None:
            continue
        if contract[legacy_name] != canonical_value:
            raise ValueError("checkpoint contract alias drift: %s" % legacy_name)


def _load_checkpoint_bundle(directory, controller, contract):
    if controller == "neighbor_phase_ddqn":
        return PhaseScoringDDQN.load_bundle(str(directory), contract)
    if controller == "shared_ddqn_legacy":
        return SharedDQN.load_bundle(str(directory), contract)
    raise ValueError("unknown learned checkpoint controller")


def _release_cases(root, manifest):
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 30:
        raise ValueError("experiment manifest must contain exactly 30 cases")
    output = []
    ids = set()
    split_counts = dict((name, 0) for name in ("train", "validation", "test"))
    for source in cases:
        if not isinstance(source, dict):
            raise ValueError("experiment case must be an object")
        case_id = source.get("case_id")
        split = source.get("split")
        if not case_id or case_id in ids or split not in split_counts:
            raise ValueError("experiment case identity is invalid")
        demand_path, relative = _relative_file(root, source.get("flow_path"), "case flow")
        demand_sha = _assert_hash(demand_path, source.get("flow_sha256"), "case flow")
        case = {
            "case_id": case_id,
            "split": split,
            "demand_path": relative,
            "demand_sha256": demand_sha,
        }
        if split == "test":
            regime = source.get("scenario")
            if regime not in REGIMES:
                raise ValueError("test case regime is invalid")
            for source_key, target_key in (("demand_seed", "demand_seed"),
                                           ("sim_seed", "simulator_seed")):
                if source.get(source_key) is None:
                    raise ValueError("test case requires %s" % source_key)
                case[target_key] = source[source_key]
            case["regime"] = regime
            case["horizon_steps"] = 3600
        ids.add(case_id)
        split_counts[split] += 1
        output.append(case)
    if split_counts != {"train": 9, "validation": 6, "test": 15}:
        raise ValueError("experiment case split differs from the 30-case contract")
    return output


def _network_manifest(root, manifest, viewer_path, viewer_relative):
    network = manifest.get("network")
    if not isinstance(network, dict):
        raise ValueError("experiment network record is missing")
    agent_ids = network.get("agent_ids")
    if (network.get("controlled_signals") != 53 or not isinstance(agent_ids, list)
            or len(agent_ids) != 53 or len(set(agent_ids)) != 53):
        raise ValueError("experiment network must bind 53 unique signal IDs")
    roadnet_path, roadnet_relative = _relative_file(root, network.get("path"), "roadnet")
    network_sha = _assert_hash(roadnet_path, network.get("sha256"), "roadnet")
    viewer_sha = _sha256(viewer_path)
    record = {
        "schema_version": 1,
        "controlled_signals": 53,
        "agent_ids": agent_ids,
        "artifacts": {
            "cityflow_roadnet": {"path": roadnet_relative, "sha256": network_sha},
            "viewer_network": {"path": viewer_relative, "sha256": viewer_sha},
        },
    }
    return record, network_sha, viewer_sha, list(agent_ids)


def _experiment_compatibility(root, manifest):
    phase = manifest.get("phase_contract")
    if not isinstance(phase, dict):
        raise ValueError("experiment phase contract record is missing")
    phase_path, _ = _relative_file(root, phase.get("path"), "phase contract")
    phase_sha = _assert_hash(phase_path, phase.get("sha256"), "phase contract")
    generator_path, _ = _relative_file(
        root, manifest.get("generator_config_path"), "generator config")
    generator_sha = _assert_hash(
        generator_path, manifest.get("generator_config_sha256"), "generator config")
    network = manifest.get("network", {})
    return {
        "network_sha256": network.get("sha256"),
        "phase_contract_sha256": phase_sha,
        "generator_config_sha256": generator_sha,
        "manifest_sha256": _canonical_hash(manifest),
    }


def _controller_configuration(root, path):
    path, relative = _relative_file(root, path, "controller configuration")
    document = _json(path, "controller configuration")
    if not isinstance(document, dict):
        raise ValueError("controller configuration must be an object")
    configs = document.get("controller_configs")
    commands = document.get("controller_commands")
    resolved = document.get("resolved_config", {})
    if set(configs or ()) != set(CONTROLLERS):
        raise ValueError("controller configuration must define every controller")
    if set(commands or ()) != set(CONTROLLERS):
        raise ValueError("controller commands must define every controller")
    if not isinstance(resolved, dict):
        raise ValueError("resolved campaign configuration must be an object")
    for controller in CONTROLLERS:
        if not isinstance(configs[controller], dict) or not configs[controller]:
            raise ValueError("controller config is invalid: %s" % controller)
        command = commands[controller]
        if (not isinstance(command, list) or not command
                or any(not isinstance(token, str) or not token for token in command)):
            raise ValueError("controller command is invalid: %s" % controller)
    return document, relative, _sha256(path)


def _validate_selection_inputs(validation, selection, tuning, validation_ids):
    if _contains_test_reference(validation) or _contains_test_reference(selection) \
            or _contains_test_reference(tuning):
        raise ValueError("test metric appears in checkpoint selection evidence")
    if not isinstance(validation, dict) or not validation:
        raise ValueError("validation evidence is missing")
    selected = selection.get("selected_checkpoint") if isinstance(selection, dict) else None
    if not selected or selected not in validation:
        raise ValueError("selected checkpoint lacks validation evidence")
    selected_evidence = validation[selected]
    if not isinstance(selected_evidence, dict) or not selected_evidence.get("score"):
        raise ValueError("selected checkpoint validation score is missing")
    if selection.get("score") != selected_evidence.get("score"):
        raise ValueError("selection score drifts from validation evidence")
    for item in validation.values():
        if not isinstance(item, dict) or not isinstance(item.get("rows"), list):
            raise ValueError("validation checkpoint rows are missing")
        for row in item["rows"]:
            if not isinstance(row, dict) or row.get("case_id") not in validation_ids:
                raise ValueError("checkpoint selection uses a non-validation case")
    selection_cases = tuning.get("selection_cases", []) if isinstance(tuning, dict) else []
    if selection_cases and any(case_id not in validation_ids for case_id in selection_cases):
        raise ValueError("baseline tuning uses a non-validation case")


def _run_artifact_path(run_dir, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("status artifact path is invalid")
    candidate = (Path(run_dir) / relative).resolve()
    try:
        candidate.relative_to(Path(run_dir).resolve())
    except ValueError:
        raise ValueError("status artifact path escapes the training run")
    return candidate


def _checkpoint_entry(root, controller, seed, run_relative, compatibility,
                      normalization, validation_ids):
    run_path, normalized_relative = _relative_file(
        root, run_relative + "/status.json", "training artifact status")
    run_dir = run_path.parent
    status = _json(run_path, "training artifact status")
    if status.get("status") != "complete" or status.get("eligible_for_test_evaluation") is not True:
        raise ValueError("training artifact is not complete and validation-eligible")
    artifact_hashes = status.get("artifact_sha256")
    if not isinstance(artifact_hashes, dict):
        raise ValueError("training artifact hashes are missing")
    source_artifacts = {}
    for relative in REQUIRED_TRAINING_ARTIFACTS:
        path = _run_artifact_path(run_dir, relative)
        if relative not in artifact_hashes or not path.is_file():
            raise ValueError("final training artifact is missing: %s" % relative)
        source_artifacts[relative] = _assert_hash(
            path, artifact_hashes[relative], "final training artifact")
    for relative, expected in artifact_hashes.items():
        path = _run_artifact_path(run_dir, relative)
        if not path.is_file():
            raise ValueError("status references a missing training artifact")
        source_artifacts[relative] = _assert_hash(path, expected, "training artifact")
    run_manifest = _json(run_dir / "run-manifest.json", "training run manifest")
    if (run_manifest.get("controller_id") != controller
            or run_manifest.get("learning_seed") != seed):
        raise ValueError("training artifact controller/seed identity drift")
    resolved = _json(run_dir / "resolved-config.json", "resolved training config")
    if (resolved.get("mode") != "final" or resolved.get("learning_seed") != seed
            or resolved.get("network_sha256") != compatibility["network_sha256"]):
        raise ValueError("training artifact is not a final run for this network")
    run_config = resolved.get("run")
    if (not isinstance(run_config, dict)
            or int(run_config.get("episodes", 0)) <= 0
            or int(run_config.get("horizon_seconds", 0)) != 3600):
        raise ValueError("final training artifact must use the full 3600-second horizon")
    selection = _json(run_dir / "selection.json", "checkpoint selection")
    if (selection.get("status") != "eligible"
            or selection.get("eligible_for_test_evaluation") is not True
            or selection.get("score", {}).get("eligible") is not True):
        raise ValueError("checkpoint selection is not validation-eligible")
    validation = _json(run_dir / "validation.json", "validation evidence")
    tuning = _json(run_dir / "baseline-tuning.json", "baseline tuning")
    _validate_selection_inputs(validation, selection, tuning, validation_ids)
    contract = _json(run_dir / "checkpoint/contract.json", "checkpoint contract")
    _checkpoint_contract(contract, controller, compatibility, normalization)
    _load_checkpoint_bundle(run_dir / "checkpoint", controller, contract)
    contract_path = run_dir / "checkpoint/contract.json"
    weight_path = run_dir / "checkpoint/weights.npz"
    selected = selection["selected_checkpoint"]
    if (not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", selected)
            or selected in (".", "..")):
        raise ValueError("selected checkpoint identifier is unsafe")
    selected_dir = run_dir / "checkpoints" / selected
    selected_weights = selected_dir / "weights.npz"
    selected_contract_path = selected_dir / "contract.json"
    if not selected_weights.is_file() or not selected_contract_path.is_file():
        raise ValueError("selected checkpoint bundle is missing")
    if _sha256(selected_weights) != source_artifacts["checkpoint/weights.npz"]:
        raise ValueError("selected checkpoint weights differ from final checkpoint")
    selected_contract = _json(selected_contract_path, "selected checkpoint contract")
    if _canonical_hash(selected_contract) != _canonical_hash(contract):
        raise ValueError("selected checkpoint contract differs from final checkpoint")
    selected_prefix = "checkpoints/%s/" % selected
    source_artifacts[selected_prefix + "weights.npz"] = _sha256(selected_weights)
    source_artifacts[selected_prefix + "contract.json"] = _sha256(selected_contract_path)
    return {
        "controller_id": controller,
        "learning_seed": seed,
        "path": str(weight_path.relative_to(root)),
        "sha256": source_artifacts["checkpoint/weights.npz"],
        "validation_eligible": True,
        "checkpoint_contract": contract,
        "checkpoint_contract_sha256": _canonical_hash(contract),
        "contract_path": str(contract_path.relative_to(root)),
        "contract_file_sha256": source_artifacts["checkpoint/contract.json"],
        "source_run_dir": str(run_dir.relative_to(root)),
        "source_status_sha256": _sha256(run_path),
        "source_artifacts": source_artifacts,
    }


def _training_checkpoints(root, index_path, compatibility, normalization,
                          validation_ids):
    index_path, relative = _relative_file(root, index_path, "training index")
    index = _json(index_path, "training index")
    if set(index or ()) != set(LEARNING_CONTROLLERS):
        raise ValueError("training index must define both learned controllers")
    checkpoints = []
    for controller in LEARNING_CONTROLLERS:
        by_seed = index[controller]
        if not isinstance(by_seed, dict) or set(by_seed) != set(str(seed) for seed in LEARNING_SEEDS):
            raise ValueError("training index must define seeds 11--15 for %s" % controller)
        for seed in LEARNING_SEEDS:
            run_relative = by_seed[str(seed)]
            if not isinstance(run_relative, str) or not run_relative:
                raise ValueError("training index run path is invalid")
            checkpoints.append(_checkpoint_entry(
                root, controller, seed, run_relative, compatibility,
                normalization, validation_ids))
    return checkpoints, relative, _sha256(index_path)


def _runtime(root, image, dockerfile_path, runtime_inspector):
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", str(image or "")):
        raise ValueError("runtime image must be an immutable repo@sha256 reference")
    inspected = runtime_inspector(image)
    if (not isinstance(inspected, dict) or inspected.get("runtime_image") != image
            or image not in inspected.get("repo_digests", ())
            or not re.fullmatch(r"sha256:[0-9a-f]{64}",
                                str(inspected.get("runtime_image_id", "")))):
        raise ValueError("runtime image inspection is not immutable")
    dockerfile, relative = _relative_file(root, dockerfile_path, "runtime Dockerfile")
    from_lines = [line.strip() for line in dockerfile.read_text().splitlines()
                  if line.strip().upper().startswith("FROM ")]
    if not from_lines or from_lines[0].split()[1] != image:
        raise ValueError("runtime Dockerfile FROM does not use runtime image")
    return {
        "runtime_digest": image.rsplit("@", 1)[1],
        "runtime_image": image,
        "runtime_image_id": inspected["runtime_image_id"],
        "runtime_dockerfile_path": relative,
        "runtime_dockerfile_sha256": _sha256(dockerfile),
    }


def _acceptance_rules():
    return {
        "required_learning_seeds": list(LEARNING_SEEDS),
        "required_regimes": list(REGIMES),
        "minimum_learning_seeds": 5,
        "minimum_demand_units": 2,
        "bootstrap_seed": 20260908,
        "bootstrap_samples": 10000,
        "normal_point_limit": 0.0,
        "normal_ci_margin_fraction": 0.05,
        "peak_ci_upper_limit": 0.0,
        "completion_degradation_limit": 0.02,
    }


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def freeze_protocol(root, experiment_manifest, viewer_network, controller_configs,
                    training_index, runtime_image, runtime_dockerfile,
                    runtime_inspector=inspect_runtime_image):
    """Return and atomically persist one immutable frozen campaign protocol."""
    root = Path(root).resolve()
    final_dir = root / FINAL_RELATIVE
    if final_dir.exists():
        raise ValueError("refusing to overwrite an existing final protocol directory")
    code_commit = _current_clean_commit(root)
    manifest_path, manifest_relative = _relative_file(
        root, experiment_manifest, "experiment manifest")
    manifest = _json(manifest_path, "experiment manifest")
    if manifest.get("protocol_version") != 2:
        raise ValueError("experiment manifest protocol version is invalid")
    viewer_path, viewer_relative = _relative_file(root, viewer_network, "viewer network")
    network_manifest, network_sha, viewer_sha, agent_ids = _network_manifest(
        root, manifest, viewer_path, viewer_relative)
    compatibility = _experiment_compatibility(root, manifest)
    if compatibility["network_sha256"] != network_sha:
        raise ValueError("experiment network hash drift")
    preprocessing = manifest.get("preprocessing", {})
    try:
        normalization = {
            "count_norm": float(preprocessing["count_norm"]),
            "capacity_norm": float(preprocessing["capacity_norm"]),
        }
    except (KeyError, TypeError, ValueError):
        raise ValueError("experiment preprocessing normalization is invalid")
    if any(not math.isfinite(value) or value <= 0
           for value in normalization.values()):
        raise ValueError("experiment preprocessing normalization is invalid")
    cases = _release_cases(root, manifest)
    validation_ids = set(case["case_id"] for case in cases
                         if case["split"] == "validation")
    config, config_relative, config_sha = _controller_configuration(root, controller_configs)
    checkpoints, index_relative, index_sha = _training_checkpoints(
        root, training_index, compatibility, normalization, validation_ids)
    runtime = _runtime(root, runtime_image, runtime_dockerfile, runtime_inspector)
    case_manifest = {
        "schema_version": 1,
        "source_experiment_manifest_path": manifest_relative,
        "source_experiment_manifest_sha256": _sha256(manifest_path),
        "cases": cases,
    }
    protocol = {
        "protocol_version": 1,
        "evidence_namespace": "haichau_network_v2",
        "network_manifest_path": FINAL_RELATIVE + "/network-manifest.json",
        "case_manifest_path": FINAL_RELATIVE + "/case-manifest.json",
        "network_sha256": network_sha,
        "viewer_network_sha256": viewer_sha,
        "phase_contract_sha256": compatibility["phase_contract_sha256"],
        "generator_config_sha256": compatibility["generator_config_sha256"],
        "experiment_manifest_sha256": compatibility["manifest_sha256"],
        "normalization": normalization,
        "agent_ids": agent_ids,
        "code_commit": code_commit,
        "source_experiment_manifest_path": manifest_relative,
        "source_experiment_manifest_sha256": _sha256(manifest_path),
        "controller_config_path": config_relative,
        "controller_config_sha256": config_sha,
        "training_index_path": index_relative,
        "training_index_sha256": index_sha,
        "resolved_config": config["resolved_config"],
        "controller_configs": config["controller_configs"],
        "controller_commands": config["controller_commands"],
        "checkpoints": checkpoints,
        "acceptance_rules": _acceptance_rules(),
    }
    protocol.update(runtime)
    parent = final_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".freeze-", dir=str(parent)))
    try:
        network_path = temporary / "network-manifest.json"
        case_path = temporary / "case-manifest.json"
        _write_json(network_path, network_manifest)
        _write_json(case_path, case_manifest)
        protocol["network_manifest_sha256"] = _sha256(network_path)
        protocol["case_manifest_sha256"] = _sha256(case_path)
        _write_json(temporary / "frozen-protocol.json", protocol)
        os.rename(str(temporary), str(final_dir))
    except Exception:
        if temporary.exists():
            shutil.rmtree(str(temporary))
        raise
    return protocol


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True,
                        help="hash-bound 30-case experiment manifest")
    parser.add_argument("--viewer-network", required=True,
                        help="verified 53-signal viewer projection")
    parser.add_argument("--controller-configs", required=True,
                        help="JSON with resolved config, five configs and commands")
    parser.add_argument("--training-index", required=True,
                        help="JSON mapping both learned controllers and seeds 11--15")
    parser.add_argument("--runtime-image", required=True,
                        help="immutable repository@sha256 image reference")
    parser.add_argument("--runtime-dockerfile", default="docker/haichau-evaluation.Dockerfile")
    args = parser.parse_args(argv)
    protocol = freeze_protocol(
        PROJECT_ROOT, args.manifest, args.viewer_network, args.controller_configs,
        args.training_index, args.runtime_image, args.runtime_dockerfile)
    print(json.dumps({
        "status": "frozen",
        "path": FINAL_RELATIVE + "/frozen-protocol.json",
        "checkpoints": len(protocol["checkpoints"]),
        "code_commit": protocol["code_commit"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
