"""Resume-safe expansion and execution of matched Hai Chau evaluations."""

import datetime
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime


_DIRECT_SUBPROCESS_RUN = subprocess.run

CONTROLLERS = (
    "tuned_fixed", "max_pressure", "hysteretic_mp",
    "shared_ddqn_legacy", "neighbor_phase_ddqn",
)
DETERMINISTIC_CONTROLLERS = frozenset((
    "tuned_fixed", "max_pressure", "hysteretic_mp",
))
_ARTIFACTS = (
    "run-manifest.json", "resolved-config.json", "metrics.json",
    "stdout.log", "stderr.log",
)


def _safe_id(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")
    if not safe or safe in (".", ".."):
        raise ValueError("unsafe run identifier")
    return safe


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def canonical_sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bind_frozen_manifest(case_manifest, protocol):
    """Overlay release identities from a frozen protocol onto its case manifest."""
    manifest = dict(case_manifest)
    manifest.update({
        "network_sha256": protocol.get("network_sha256"),
        "viewer_network_sha256": protocol.get("viewer_network_sha256"),
        "phase_contract_sha256": protocol.get("phase_contract_sha256"),
        "normalization": protocol.get("normalization", {}),
        "runtime_digest": protocol.get("runtime_digest"),
        "runtime_image": protocol.get("runtime_image"),
        "runtime_image_id": protocol.get("runtime_image_id"),
        "runtime_dockerfile_path": protocol.get("runtime_dockerfile_path"),
        "runtime_dockerfile_sha256": protocol.get("runtime_dockerfile_sha256"),
        "code_commit": protocol.get("code_commit"),
        "controlled_signals": 53,
        "agent_ids": list(protocol.get("agent_ids", [])),
        "resolved_config": protocol.get("resolved_config", {}),
        "controller_configs": protocol.get("controller_configs", {}),
        "controller_commands": protocol.get("controller_commands", {}),
        "checkpoints": protocol.get("checkpoints", []),
    })
    return manifest


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_json_bytes(value))
    temporary.replace(path)


def _materialize_run_manifest(run_dir, run):
    """Create one run input once and refuse any pre-execution drift."""
    path = Path(run_dir) / "run-manifest.json"
    expected = _json_bytes(run)
    if path.exists():
        if not path.is_file() or path.read_bytes() != expected:
            raise ValueError("run spec differs from existing run-manifest.json")
    else:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(expected)
        temporary.replace(path)
    return _sha256(path)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _positive_config(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("resolved_config %s must be positive" % label)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("resolved_config %s must be positive" % label)


def _validate_resolved_config(config, controller_id, manifest):
    if not isinstance(config, dict):
        raise ValueError("resolved_config must be an object")
    for field in ("network_path", "phase_contract_path"):
        if not isinstance(config.get(field), str) or not config[field]:
            raise ValueError("resolved_config %s is required" % field)
    if not re.fullmatch(r"[0-9a-f]{64}", str(
            config.get("phase_contract_sha256", ""))):
        raise ValueError("resolved_config phase_contract_sha256 is invalid")
    if config["phase_contract_sha256"] != manifest.get(
            "phase_contract_sha256"):
        raise ValueError("resolved_config phase contract differs from frozen protocol")
    normalization = config.get("normalization")
    simulation = config.get("simulation")
    reward = config.get("reward")
    if not isinstance(normalization, dict):
        raise ValueError("resolved_config normalization must be an object")
    if normalization != manifest.get("normalization"):
        raise ValueError("resolved_config normalization differs from frozen protocol")
    if not isinstance(simulation, dict):
        raise ValueError("resolved_config simulation must be an object")
    if not isinstance(reward, dict):
        raise ValueError("resolved_config reward must be an object")
    for field in ("count_norm", "capacity_norm"):
        _positive_config(normalization.get(field), "normalization.%s" % field)
    for field in ("action_interval", "min_green", "maximum_red"):
        _positive_config(simulation.get(field), "simulation.%s" % field)
    for field in ("queue_weight", "downstream_block_weight", "switch_penalty"):
        try:
            number = float(reward[field])
        except (KeyError, TypeError, ValueError):
            raise ValueError("resolved_config reward.%s must be numeric" % field)
        if not math.isfinite(number):
            raise ValueError("resolved_config reward.%s must be numeric" % field)
    if controller_id == "tuned_fixed":
        _positive_config(config.get("green_duration"), "green_duration")
    if controller_id == "hysteretic_mp":
        _positive_config(config.get("min_hold_decisions"), "min_hold_decisions")
        try:
            threshold = float(config.get("switch_threshold"))
        except (TypeError, ValueError):
            raise ValueError("resolved_config switch_threshold must be numeric")
        if not math.isfinite(threshold):
            raise ValueError("resolved_config switch_threshold must be numeric")


def expand_runs(manifest, learning_seeds, controller_ids):
    """Expand only frozen test cases, preserving the correct seed unit."""
    identity_patterns = {
        "network_sha256": r"[0-9a-f]{64}",
        "viewer_network_sha256": r"[0-9a-f]{64}",
        "runtime_digest": r"sha256:[0-9a-f]{64}",
        "runtime_image_id": r"sha256:[0-9a-f]{64}",
        "runtime_dockerfile_sha256": r"[0-9a-f]{64}",
        "code_commit": r"[0-9a-f]{40}",
    }
    for field, pattern in identity_patterns.items():
        if not re.fullmatch(pattern, str(manifest.get(field, ""))):
            raise ValueError("frozen manifest requires valid %s" % field)
    image = str(manifest.get("runtime_image", ""))
    if not image.endswith("@" + manifest["runtime_digest"]):
        raise ValueError("frozen manifest runtime_image must contain runtime_digest")
    if not manifest.get("runtime_dockerfile_path"):
        raise ValueError("frozen manifest requires runtime_dockerfile_path")
    unknown = sorted(set(controller_ids) - set(CONTROLLERS))
    if unknown:
        raise ValueError("unknown controllers: %s" % ", ".join(unknown))
    commands = manifest.get("controller_commands")
    if (not isinstance(commands, dict)
            or not set(controller_ids).issubset(set(commands))):
        raise ValueError("frozen manifest must define each selected controller command")
    for controller_id in controller_ids:
        command = commands[controller_id]
        if command != ["python3", "scripts/evaluate_haichau_network.py"]:
            raise ValueError(
                "controller command must be the frozen evaluator entrypoint: %s" %
                controller_id)
    cases = [case for case in manifest.get("cases", [])
             if case.get("split") == "test"]
    if not cases:
        raise ValueError("manifest has no test cases")
    horizon_default = manifest.get("default_horizon_steps")
    runs = []
    seen_ids = set()
    for controller_id in controller_ids:
        seeds = [None] if controller_id in DETERMINISTIC_CONTROLLERS else learning_seeds
        if not seeds:
            raise ValueError("learning controller requires learning seeds")
        for seed in seeds:
            for case in cases:
                horizon = case.get("horizon_steps", horizon_default)
                for field in ("case_id", "regime", "demand_seed",
                              "simulator_seed", "scheduled_vehicles",
                              "demand_sha256"):
                    if case.get(field) is None:
                        raise ValueError("test case requires %s" % field)
                scheduled_vehicles = case["scheduled_vehicles"]
                if isinstance(scheduled_vehicles, bool):
                    raise ValueError("test case requires positive scheduled_vehicles")
                try:
                    scheduled_vehicles = int(scheduled_vehicles)
                except (TypeError, ValueError):
                    raise ValueError("test case requires positive scheduled_vehicles")
                if scheduled_vehicles <= 0 \
                        or scheduled_vehicles != case["scheduled_vehicles"]:
                    raise ValueError("test case requires positive scheduled_vehicles")
                if not horizon or int(horizon) <= 0:
                    raise ValueError("test case requires positive horizon_steps")
                suffix = "det" if seed is None else "ls%s" % seed
                run_id = _safe_id("%s__%s__%s" % (
                    controller_id, case["case_id"], suffix))
                if run_id in seen_ids:
                    raise ValueError("duplicate run_id: %s" % run_id)
                seen_ids.add(run_id)
                run = {
                    "run_id": run_id,
                    "case_id": case["case_id"],
                    "regime": case["regime"],
                    "controller_id": controller_id,
                    "learning_seed": seed,
                    "demand_seed": case["demand_seed"],
                    "simulator_seed": case["simulator_seed"],
                    "scheduled_vehicles": scheduled_vehicles,
                    "horizon_steps": int(horizon),
                    "network_sha256": manifest.get("network_sha256"),
                    "viewer_network_sha256": manifest.get(
                        "viewer_network_sha256", manifest.get("network_sha256")),
                    "demand_sha256": case["demand_sha256"],
                    "demand_path": case.get("demand_path"),
                    "runtime_digest": manifest.get("runtime_digest"),
                    "runtime_image": manifest.get("runtime_image"),
                    "runtime_image_id": manifest.get("runtime_image_id"),
                    "runtime_dockerfile_path": manifest.get(
                        "runtime_dockerfile_path"),
                    "runtime_dockerfile_sha256": manifest.get(
                        "runtime_dockerfile_sha256"),
                    "code_commit": manifest.get("code_commit"),
                    "evidence_namespace": "haichau_network_v2",
                    "fresh_evaluation": True,
                    "controlled_signals": manifest.get("controlled_signals", 53),
                    "agent_ids": list(manifest.get("agent_ids", [])),
                }
                resolved = dict(manifest.get("resolved_config", {}))
                controller_config = manifest.get("controller_configs", {}).get(
                    controller_id, {})
                if not isinstance(controller_config, dict):
                    raise ValueError("controller config must be an object")
                resolved.update(controller_config)
                identity = dict((field, run[field]) for field in (
                    "case_id", "regime", "controller_id", "learning_seed",
                    "demand_seed", "simulator_seed", "horizon_steps",
                    "scheduled_vehicles",
                    "network_sha256", "demand_sha256", "runtime_digest",
                    "runtime_image", "runtime_image_id",
                    "runtime_dockerfile_path", "runtime_dockerfile_sha256",
                    "code_commit", "viewer_network_sha256",
                    "demand_path",
                ))
                resolved.update(identity)
                matches = [entry for entry in manifest.get("checkpoints", [])
                           if entry.get("controller_id") == controller_id
                           and entry.get("learning_seed") == seed]
                if len(matches) > 1:
                    raise ValueError("checkpoint identity is duplicated")
                if matches:
                    checkpoint = matches[0]
                    contract = checkpoint.get("checkpoint_contract")
                    if not isinstance(contract, dict) or not contract:
                        raise ValueError("checkpoint contract must be a non-empty object")
                    run.update({
                        "checkpoint_path": checkpoint.get("path"),
                        "checkpoint_sha256": checkpoint.get("sha256"),
                        "checkpoint_contract": contract,
                        "checkpoint_contract_sha256": canonical_sha256(contract),
                    })
                    resolved["checkpoint"] = dict((field, run[field]) for field in (
                        "checkpoint_path", "checkpoint_sha256",
                        "checkpoint_contract", "checkpoint_contract_sha256",
                    ))
                _validate_resolved_config(resolved, controller_id, manifest)
                run["resolved_config"] = resolved
                command = commands[controller_id]
                run["command"] = list(command)
                runs.append(run)
    return runs


def _container_evaluator_argv(run, project_root, run_dir):
    command = run.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError("run has no command; integrate the controller before execution")
    project_root = Path(project_root).resolve()
    manifest_path = Path(run_dir).resolve() / "run-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("run-manifest.json must exist before Docker execution")
    try:
        manifest_relative = manifest_path.relative_to(project_root)
    except ValueError:
        raise ValueError("run manifest must remain inside project root")
    runtime_path = Path(run_dir).resolve() / "runtime-configs"
    runtime_relative = runtime_path.relative_to(project_root)
    return [str(token) for token in command] + [
        "--run-manifest", "/work/" + manifest_relative.as_posix(),
        "--runtime-dir", "/work/" + runtime_relative.as_posix(),
    ]


def _docker_argv(run, project_root, run_dir):
    project_root = Path(project_root).resolve()
    return [
        "docker", "run", "--detach", "--network", "none",
        "--cidfile", str(Path(run_dir).resolve() / ".docker-container-id"),
        "-v", "%s:/work" % project_root, "-w", "/work",
        run["runtime_image"],
    ] + _container_evaluator_argv(run, project_root, run_dir)


def _docker_cli_diagnostics(run_stderr, wait_stderr):
    """Keep Docker client/daemon stderr distinct from container stderr."""
    return {
        "schema_version": 1,
        "docker_run_stderr": str(run_stderr),
        "docker_wait_stderr": str(wait_stderr),
    }


def _direct_command(argv, cwd):
    try:
        completed = _DIRECT_SUBPROCESS_RUN(
            list(argv), cwd=str(cwd), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
    except OSError as exc:
        raise ValueError("direct Docker verification is unavailable: %s" % exc)
    return completed


def _retained_container_evidence(run, run_dir, project_root, container_id,
                                 compare_artifacts=True):
    completed = _direct_command(
        ("docker", "container", "inspect", container_id), project_root)
    if completed.returncode:
        raise ValueError("retained Docker container is unavailable: %s" %
                         completed.stderr.strip())
    try:
        record = json.loads(completed.stdout)[0]
        config = record["Config"]
        host = record["HostConfig"]
        state = record["State"]
    except (IndexError, KeyError, TypeError, ValueError):
        raise ValueError("retained Docker container inspection is invalid")
    mount = [item for item in record.get("Mounts", [])
             if item.get("Destination") == "/work"]
    expected_source = str(Path(project_root).resolve())
    if record.get("Id") != container_id \
            or record.get("Image") != run.get("runtime_image_id") \
            or config.get("Image") != run.get("runtime_image") \
            or config.get("Cmd") != _container_evaluator_argv(
                run, project_root, run_dir) \
            or config.get("WorkingDir") != "/work" \
            or host.get("NetworkMode") != "none" \
            or state.get("Status") != "exited" \
            or state.get("ExitCode") != 0 \
            or len(mount) != 1 \
            or str(Path(mount[0].get("Source", "")).resolve()) != expected_source \
            or mount[0].get("RW") is not True:
        raise ValueError("retained Docker container identity/config/status differs")
    logs = _direct_command(("docker", "logs", container_id), project_root)
    if logs.returncode:
        raise ValueError("retained Docker container logs are unavailable")
    stdout_path = Path(run_dir) / "stdout.log"
    stderr_path = Path(run_dir) / "stderr.log"
    if compare_artifacts and stdout_path.is_file() \
            and _sha256_bytes(logs.stdout.encode("utf-8")) \
            != _sha256(stdout_path):
        raise ValueError("retained Docker stdout differs from run artifact")
    if compare_artifacts and stderr_path.is_file() \
            and _sha256_bytes(logs.stderr.encode("utf-8")) \
            != _sha256(stderr_path):
        raise ValueError("retained Docker stderr differs from run artifact")
    receipt = {
        "container_id": record["Id"],
        "image_id": record["Image"],
        "image_reference": config["Image"],
        "command": config["Cmd"],
        "working_directory": config["WorkingDir"],
        "network_mode": host["NetworkMode"],
        "exit_code": state["ExitCode"],
        "status": state["Status"],
        "mount_source": mount[0]["Source"],
        "mount_destination": mount[0]["Destination"],
        "stdout_sha256": _sha256_bytes(logs.stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(logs.stderr.encode("utf-8")),
    }
    return receipt, logs.stdout, logs.stderr


def _retained_container_receipt(run, run_dir, project_root, container_id):
    receipt, unused_stdout, unused_stderr = _retained_container_evidence(
        run, run_dir, project_root, container_id)
    return receipt


def _trusted_docker_executor(run, run_dir, project_root, source, runtime):
    """Execute one release run through the library-owned immutable Docker path."""
    project_root = Path(project_root).resolve()
    if source.get("code_commit") != run.get("code_commit"):
        raise ValueError("executor Git identity differs from frozen run")
    if any(runtime.get(field) != run.get(field) for field in (
            "runtime_image", "runtime_image_id", "runtime_digest")):
        raise ValueError("executor Docker identity differs from frozen run")
    cidfile = Path(run_dir).resolve() / ".docker-container-id"
    if cidfile.exists():
        cidfile.unlink()
    argv = _docker_argv(run, project_root, run_dir)
    run_manifest_sha256 = _sha256(Path(run_dir) / "run-manifest.json")
    try:
        launched = _DIRECT_SUBPROCESS_RUN(
            argv, cwd=str(project_root), universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        container_id = cidfile.read_text().strip() if cidfile.is_file() else ""
    finally:
        if cidfile.exists():
            cidfile.unlink()
    if launched.returncode:
        raise RuntimeError("executor exited %s: %s" % (
            launched.returncode, launched.stderr.strip()))
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise ValueError("Docker did not retain a valid container ID")
    launched_ids = [line.strip() for line in launched.stdout.splitlines()
                    if line.strip()]
    if launched_ids != [container_id]:
        raise ValueError("Docker run output differs from its retained container ID")
    wait_argv = ["docker", "wait", container_id]
    waited = _direct_command(wait_argv, project_root)
    if waited.returncode:
        raise RuntimeError("Docker wait exited %s: %s" % (
            waited.returncode, waited.stderr.strip()))
    if waited.stdout.strip() != "0":
        raise RuntimeError("container exited %s" % waited.stdout.strip())
    receipt, container_stdout, container_stderr = _retained_container_evidence(
        run, run_dir, project_root, container_id, compare_artifacts=False)
    lines = [line for line in container_stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("executor must print a JSON result on its final line")
    result = json.loads(lines[-1])
    result["stdout"] = container_stdout
    result["stderr"] = container_stderr
    diagnostics = _docker_cli_diagnostics(launched.stderr, waited.stderr)
    result["docker_cli_diagnostics"] = diagnostics
    provenance = {
        "provenance_version": 3,
        "mode": "retained_docker_container",
        "docker_argv": argv,
        "docker_wait_argv": wait_argv,
        "container_id": container_id,
        "exit_code": int(waited.stdout.strip()),
        "code_commit": run.get("code_commit"),
        "execution_head_commit": source["head_commit"],
        "runtime_image": runtime["runtime_image"],
        "runtime_image_id": runtime["runtime_image_id"],
        "runtime_digest": runtime["runtime_digest"],
        "scheduled_vehicles": run.get("scheduled_vehicles"),
        "run_manifest_sha256": run_manifest_sha256,
        "stdout_sha256": receipt["stdout_sha256"],
        "stderr_sha256": receipt["stderr_sha256"],
        "docker_run_stdout_sha256": _sha256_bytes(
            launched.stdout.encode("utf-8")),
        "docker_wait_stdout_sha256": _sha256_bytes(
            waited.stdout.encode("utf-8")),
        "docker_cli_diagnostics_sha256": _sha256_bytes(
            _json_bytes(diagnostics)),
        "container_receipt_sha256": canonical_sha256(receipt),
    }
    return result, provenance


def _assert_git_ancestor(project_root, older, newer):
    if older == newer:
        return
    for argv in (("git", "cat-file", "-e", older + "^{commit}"),
                 ("git", "merge-base", "--is-ancestor", older, newer)):
        completed = _DIRECT_SUBPROCESS_RUN(
            list(argv), cwd=str(project_root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        if completed.returncode:
            raise ValueError("trusted Docker execution Git commit is not an ancestor")


def _verify_execution_provenance(run_dir, status, expected_run, project_root,
                                 current_head=None):
    provenance = status.get("execution_provenance", {})
    if provenance.get("mode") != "retained_docker_container" \
            or provenance.get("provenance_version") != 3:
        raise ValueError("release run requires the trusted Docker executor")
    expected_argv = _docker_argv(expected_run, project_root, run_dir)
    if provenance.get("docker_argv") != expected_argv:
        raise ValueError("trusted Docker executor argv differs from the frozen run")
    if provenance.get("run_manifest_sha256") != _sha256(
            Path(run_dir) / "run-manifest.json"):
        raise ValueError("trusted Docker run manifest hash differs")
    if provenance.get("docker_wait_argv") != [
            "docker", "wait", provenance.get("container_id")]:
        raise ValueError("trusted Docker wait argv differs from its container")
    expected_identity = {
        "code_commit": expected_run.get("code_commit"),
        "runtime_image": expected_run.get("runtime_image"),
        "runtime_image_id": expected_run.get("runtime_image_id"),
        "runtime_digest": expected_run.get("runtime_digest"),
        "scheduled_vehicles": expected_run.get("scheduled_vehicles"),
    }
    if any(provenance.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("trusted Docker executor identity differs from the frozen run")
    if provenance.get("exit_code") != 0:
        raise ValueError("trusted Docker executor did not exit successfully")
    if not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("container_id", ""))):
        raise ValueError("trusted Docker executor requires the Docker container ID")
    if provenance.get("docker_run_stdout_sha256") != _sha256_bytes(
            (provenance["container_id"] + "\n").encode("utf-8")) \
            or provenance.get("docker_wait_stdout_sha256") != _sha256_bytes(b"0\n"):
        raise ValueError("trusted Docker launch/wait output differs")
    receipt = _retained_container_receipt(
        expected_run, run_dir, project_root, provenance["container_id"])
    if provenance.get("container_receipt_sha256") != canonical_sha256(receipt):
        raise ValueError("retained Docker container receipt differs from status")
    for name in ("stdout", "stderr"):
        if provenance.get(name + "_sha256") != _sha256(run_dir / (name + ".log")):
            raise ValueError("trusted Docker executor %s hash mismatch" % name)
    diagnostics_path = run_dir / "docker-cli-diagnostics.json"
    if status.get("artifact_sha256", {}).get(
            "docker-cli-diagnostics.json") != (
                _sha256(diagnostics_path) if diagnostics_path.is_file() else None) \
            or not diagnostics_path.is_file() \
            or provenance.get("docker_cli_diagnostics_sha256") \
            != _sha256(diagnostics_path):
        raise ValueError("trusted Docker CLI diagnostics hash mismatch")
    try:
        diagnostics = json.loads(diagnostics_path.read_text())
    except ValueError:
        raise ValueError("trusted Docker CLI diagnostics are invalid")
    if not isinstance(diagnostics, dict) or set(diagnostics) != {
            "schema_version", "docker_run_stderr", "docker_wait_stderr"} \
            or diagnostics.get("schema_version") != 1 \
            or not isinstance(diagnostics.get("docker_run_stderr"), str) \
            or not isinstance(diagnostics.get("docker_wait_stderr"), str):
        raise ValueError("trusted Docker CLI diagnostics are invalid")
    lines = [line for line in (run_dir / "stdout.log").read_text().splitlines()
             if line.strip()]
    try:
        emitted = json.loads(lines[-1])
    except (IndexError, ValueError):
        raise ValueError("trusted Docker stdout does not end with its JSON result")
    for key, artifact in (("resolved_config", "resolved-config.json"),
                          ("metrics", "metrics.json")):
        if emitted.get(key) != json.loads((run_dir / artifact).read_text()):
            raise ValueError("trusted Docker stdout %s differs from artifact" % key)
    replay_path = run_dir / "replay.json"
    if replay_path.is_file() and emitted.get("replay") != json.loads(replay_path.read_text()):
        raise ValueError("trusted Docker stdout replay differs from artifact")
    execution_head = str(provenance.get("execution_head_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", execution_head):
        raise ValueError("trusted Docker executor requires its Git head commit")
    _assert_git_ancestor(project_root, expected_run["code_commit"], execution_head)
    if current_head:
        _assert_git_ancestor(project_root, execution_head, current_head)


def _verify_complete(run_dir, status, expected_run,
                     require_release_provenance=False, project_root=None,
                     current_head=None):
    if status.get("run_spec_sha256") != canonical_sha256(expected_run):
        raise ValueError("complete run spec digest does not match campaign")
    if any(status.get(field) != expected_run.get(field) for field in (
            "code_commit", "runtime_image", "runtime_image_id",
            "runtime_digest", "runtime_dockerfile_sha256",
            "scheduled_vehicles")):
        raise ValueError("complete status code/runtime identity does not match campaign")
    hashes = status.get("artifact_sha256", {})
    if not set(_ARTIFACTS).issubset(set(hashes)):
        raise ValueError("complete run has an incomplete artifact hash set")
    for name in hashes:
        if Path(name).name != name:
            raise ValueError("artifact name must not contain a path")
        path = run_dir / name
        if not path.is_file():
            raise ValueError("complete run is missing artifact: %s" % name)
        if _sha256(path) != hashes[name]:
            raise ValueError("artifact hash mismatch: %s" % path)
    run_manifest = json.loads((run_dir / "run-manifest.json").read_text())
    if run_manifest != expected_run:
        raise ValueError("run spec differs from run-manifest.json")
    resolved = json.loads((run_dir / "resolved-config.json").read_text())
    if resolved != expected_run.get("resolved_config"):
        raise ValueError("resolved config differs from frozen run spec")
    metrics = json.loads((run_dir / "metrics.json").read_text())
    _validate_result(expected_run, {"resolved_config": resolved, "metrics": metrics})
    if require_release_provenance:
        _verify_execution_provenance(
            run_dir, status, expected_run, project_root or run_dir, current_head)


def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _validate_network_metrics(run, metrics):
    required = (
        "observed_steps", "observed_seconds",
        "queue_integral_vehicle_seconds", "queue_integral_vehicle_hours",
        "network_queue_integral_vehicle_seconds",
        "pending_integral_vehicle_seconds", "per_node_queue_integral_vehicle_seconds",
        "per_node_max_queue", "spillback_lane_seconds", "scheduled", "due",
        "unreleased", "inserted", "departed", "arrived", "running", "pending", "removed",
        "censored_or_unfinished", "completion_denominator", "completion_rate",
        "insertion_rate", "completed_travel_time_count", "phase_switches",
        "intergreen_seconds", "max_red_seconds", "travel_time_completed_mean",
        "travel_time_completed_median", "travel_time_completed_p95",
    )
    missing = [field for field in required if field not in metrics]
    if missing:
        raise ValueError("network metric schema is incomplete: %s" % ", ".join(missing))
    finite_fields = (
        "observed_steps", "observed_seconds", "queue_integral_vehicle_seconds",
        "queue_integral_vehicle_hours", "network_queue_integral_vehicle_seconds",
        "pending_integral_vehicle_seconds",
        "scheduled", "due", "unreleased", "inserted", "departed", "arrived", "running", "pending",
        "removed", "censored_or_unfinished", "phase_switches",
        "intergreen_seconds", "max_red_seconds", "completed_travel_time_count",
    )
    if any(not _finite(metrics[field]) or float(metrics[field]) < 0
           for field in finite_fields):
        raise ValueError("network metric scalars must be finite and non-negative")
    integer_fields = (
        "observed_steps", "scheduled", "due", "unreleased", "inserted", "departed", "arrived",
        "running", "pending", "removed", "censored_or_unfinished",
        "phase_switches", "completed_travel_time_count",
    )
    if any(float(metrics[field]) != int(float(metrics[field]))
           for field in integer_fields):
        raise ValueError("network metric counters must be integers")
    expected_hours = float(metrics["queue_integral_vehicle_seconds"]) / 3600.0
    if abs(float(metrics["queue_integral_vehicle_hours"]) - expected_hours) > 1e-12:
        raise ValueError("network queue integral units are inconsistent")
    expected_total = (float(metrics["network_queue_integral_vehicle_seconds"])
                      + float(metrics["pending_integral_vehicle_seconds"]))
    if abs(float(metrics["queue_integral_vehicle_seconds"]) - expected_total) > 1e-9:
        raise ValueError("primary queue integral must include pending demand")
    if metrics["completion_denominator"] != "scheduled":
        raise ValueError("network metric completion denominator must be scheduled")
    scheduled = int(metrics["scheduled"])
    if scheduled != int(run["scheduled_vehicles"]):
        raise ValueError(
            "network metric scheduled differs from frozen scheduled_vehicles")
    inserted = int(metrics["inserted"])
    due = int(metrics["due"])
    unreleased = int(metrics["unreleased"])
    arrived = int(metrics["arrived"])
    running = int(metrics["running"])
    pending = int(metrics["pending"])
    removed = int(metrics["removed"])
    if inserted != int(metrics["departed"]):
        raise ValueError("network metric inserted/departed mismatch")
    if (scheduled != due + unreleased or due != inserted + pending
            or inserted != arrived + running + removed):
        raise ValueError("network metric vehicle accounting does not conserve")
    if due != scheduled or unreleased != 0:
        raise ValueError("full-horizon run must release all scheduled vehicles")
    if int(metrics["censored_or_unfinished"]) != pending + running + removed:
        raise ValueError("network metric censored count does not conserve")
    completion = metrics["completion_rate"]
    insertion = metrics["insertion_rate"]
    expected_completion = float(arrived) / scheduled if scheduled else None
    expected_insertion = float(inserted) / scheduled if scheduled else None
    if completion != expected_completion or insertion != expected_insertion:
        raise ValueError("network metric rates do not match vehicle accounting")
    if int(metrics["completed_travel_time_count"]) != arrived:
        raise ValueError("network metric travel-time count must equal arrivals")
    travel_fields = (
        "travel_time_completed_mean", "travel_time_completed_median",
        "travel_time_completed_p95",
    )
    if arrived and any(not _finite(metrics[field]) or float(metrics[field]) < 0
                       for field in travel_fields):
        raise ValueError(
            "completed travel-time statistics must be finite and non-negative")
    if arrived and float(metrics["travel_time_completed_p95"]) < float(
            metrics["travel_time_completed_median"]):
        raise ValueError("completed travel-time p95 must not be below the median")
    if not arrived and any(metrics[field] is not None for field in travel_fields):
        raise ValueError("empty completed travel-time statistics must be null")
    agent_ids = set(run.get("agent_ids", []))
    if run.get("controlled_signals") != 53 or len(agent_ids) != 53:
        raise ValueError("run spec must identify exactly 53 controlled signal IDs")
    for field in ("per_node_queue_integral_vehicle_seconds", "per_node_max_queue"):
        values = metrics[field]
        if not isinstance(values, dict) or set(values) != agent_ids:
            raise ValueError("network metric %s must cover all 53 signals" % field)
        if any(not _finite(value) or float(value) < 0 for value in values.values()):
            raise ValueError("network per-node metrics must be finite and non-negative")
    spillback = metrics["spillback_lane_seconds"]
    if not isinstance(spillback, dict) or any(
            not _finite(value) or float(value) < 0 for value in spillback.values()):
        raise ValueError("network spillback metrics must be finite and non-negative")


def _validate_result(run, result):
    for field in ("resolved_config", "metrics"):
        if not isinstance(result.get(field), dict):
            raise ValueError("executor result requires %s" % field)
    metrics = result["metrics"]
    if result["resolved_config"] != run.get("resolved_config"):
        raise ValueError("resolved config mismatch")
    for field in (
            "case_id", "regime", "controller_id", "learning_seed", "demand_seed",
            "simulator_seed", "scheduled_vehicles", "network_sha256",
            "demand_sha256", "runtime_digest",
            "runtime_image", "runtime_image_id", "runtime_dockerfile_path",
            "runtime_dockerfile_sha256", "code_commit", "viewer_network_sha256",
            "demand_path",
            "checkpoint_sha256", "checkpoint_contract_sha256"):
        if metrics.get(field) != run.get(field):
            raise ValueError("%s mismatch" % field)
    if int(metrics.get("completed_steps", -1)) != run["horizon_steps"]:
        raise ValueError("horizon mismatch")
    if metrics.get("fresh_evaluation") is not True:
        raise ValueError("fresh evaluation provenance is required")
    source = str(metrics.get("source_run_dir", ""))
    normalized = source.replace("\\", "/").lower()
    if "results/haichau" in normalized \
            and "results/haichau_network_v2" not in normalized:
        raise ValueError("legacy Hai Chau evidence cannot enter the fresh campaign")
    if metrics.get("observed_steps") != run["horizon_steps"]:
        raise ValueError("network metric observed horizon mismatch")
    _validate_network_metrics(run, metrics)


def verify_campaign(campaign_dir, require_release_provenance=False, project_root=None):
    campaign_dir = Path(campaign_dir)
    manifest_path = campaign_dir / "campaign-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("campaign-manifest.json is missing")
    campaign = json.loads(manifest_path.read_text())
    runs = campaign.get("runs", [])
    current_head = None
    if require_release_provenance:
        if not runs:
            raise ValueError("release campaign contains no runs")
        for run in runs:
            status_path = campaign_dir / "runs" / _safe_id(run["run_id"]) / "status.json"
            if not status_path.is_file() or json.loads(status_path.read_text()).get(
                    "execution_provenance", {}).get("mode") \
                    != "retained_docker_container":
                raise ValueError("release run requires the trusted Docker executor")
        project_root = Path(project_root or campaign_dir).resolve()
        try:
            campaign_relative = str(campaign_dir.resolve().relative_to(project_root))
        except ValueError:
            raise ValueError("release campaign directory must remain inside project root")
        source = verify_git_checkout(
            project_root, runs[0].get("code_commit"),
            allowed_dirty_prefixes=(campaign_relative,))
        verify_runtime(project_root, runs[0])
        current_head = source["head_commit"]
    for run in runs:
        run_dir = campaign_dir / "runs" / _safe_id(run["run_id"])
        status_path = run_dir / "status.json"
        if not status_path.is_file():
            raise ValueError("run status is missing: %s" % run["run_id"])
        status = json.loads(status_path.read_text())
        if status.get("status") != "complete":
            raise ValueError("run is not complete: %s" % run["run_id"])
        _verify_complete(run_dir, status, run, require_release_provenance,
                         project_root or campaign_dir, current_head)
    return {"complete": len(runs), "total": len(runs)}


def run_pending(campaign_dir, executor=None, project_root=None):
    """Run incomplete bundles and verify immutable completed bundles."""
    campaign_dir = Path(campaign_dir)
    manifest_path = campaign_dir / "campaign-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("campaign-manifest.json is missing")
    campaign = json.loads(manifest_path.read_text())
    if campaign.get("evidence_namespace") != "haichau_network_v2":
        raise ValueError("campaign evidence_namespace must be haichau_network_v2")
    runs = campaign.get("runs", [])
    prepared = {}
    for run in runs:
        run_dir = campaign_dir / "runs" / _safe_id(run["run_id"])
        run_dir.mkdir(parents=True, exist_ok=True)
        run_manifest_sha256 = _materialize_run_manifest(run_dir, run)
        (run_dir / "runtime-configs").mkdir(exist_ok=True)
        prepared[run["run_id"]] = (run_dir, run_manifest_sha256)
    source = runtime = None
    if executor is None:
        project_root = Path(project_root or campaign_dir).resolve()
        try:
            campaign_relative = str(campaign_dir.resolve().relative_to(project_root))
        except ValueError:
            raise ValueError("release campaign directory must remain inside project root")
        if not runs:
            raise ValueError("release campaign contains no runs")
        source = verify_git_checkout(
            project_root, runs[0].get("code_commit"),
            allowed_dirty_prefixes=(campaign_relative,))
        runtime = verify_runtime(project_root, runs[0])
    counts = {"completed": 0, "failed": 0, "skipped": 0, "total": len(runs)}
    for run in runs:
        run_dir, run_manifest_sha256 = prepared[run["run_id"]]
        status_path = run_dir / "status.json"
        if status_path.is_file():
            status = json.loads(status_path.read_text())
            if status.get("status") == "complete":
                _verify_complete(
                    run_dir, status, run, executor is None,
                    project_root or campaign_dir,
                    source["head_commit"] if source else None)
                counts["skipped"] += 1
                continue

        try:
            _write_json(status_path, {
                "status": "running", "started_at": _utc_now(),
                "run_manifest_sha256": run_manifest_sha256,
            })
            if executor is None:
                result, provenance = _trusted_docker_executor(
                    dict(run), run_dir, project_root, source, runtime)
            else:
                result = executor(dict(run), run_dir)
                provenance = {
                    "provenance_version": 1,
                    "mode": "injected",
                    "release_eligible": False,
                }
            if _sha256(run_dir / "run-manifest.json") != run_manifest_sha256:
                raise ValueError("run-manifest.json changed during execution")
            _validate_result(run, result)
            _write_json(run_dir / "resolved-config.json", result["resolved_config"])
            _write_json(run_dir / "metrics.json", result["metrics"])
            (run_dir / "stdout.log").write_text(str(result.get("stdout", "")))
            (run_dir / "stderr.log").write_text(str(result.get("stderr", "")))
            artifacts = list(_ARTIFACTS)
            if "docker_cli_diagnostics" in result:
                diagnostics = result["docker_cli_diagnostics"]
                if not isinstance(diagnostics, dict) \
                        or diagnostics != _docker_cli_diagnostics(
                        diagnostics.get("docker_run_stderr", ""),
                        diagnostics.get("docker_wait_stderr", "")):
                    raise ValueError("Docker CLI diagnostics are invalid")
                _write_json(run_dir / "docker-cli-diagnostics.json", diagnostics)
                artifacts.append("docker-cli-diagnostics.json")
            if "replay" in result:
                if not isinstance(result["replay"], dict):
                    raise ValueError("executor replay must be a JSON object")
                _write_json(run_dir / "replay.json", result["replay"])
                artifacts.append("replay.json")
            hashes = dict((name, _sha256(run_dir / name)) for name in artifacts)
            _write_json(status_path, {
                "status": "complete",
                "completed_at": _utc_now(),
                "run_spec_sha256": canonical_sha256(run),
                "code_commit": run.get("code_commit"),
                "runtime_image": run.get("runtime_image"),
                "runtime_image_id": run.get("runtime_image_id"),
                "runtime_digest": run.get("runtime_digest"),
                "runtime_dockerfile_sha256": run.get(
                    "runtime_dockerfile_sha256"),
                "scheduled_vehicles": run.get("scheduled_vehicles"),
                "execution_provenance": provenance,
                "artifact_sha256": hashes,
            })
            counts["completed"] += 1
        except Exception as exc:
            _write_json(status_path, {
                "status": "failed", "failed_at": _utc_now(),
                "error": str(exc),
            })
            counts["failed"] += 1
    return counts
