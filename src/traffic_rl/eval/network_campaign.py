"""Resume-safe expansion and execution of matched Hai Chau evaluations."""

import datetime
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from traffic_rl.eval.release_identity import verify_git_checkout, verify_runtime


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
        "checkpoints": protocol.get("checkpoints", []),
    })
    return manifest


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_json_bytes(value))
    temporary.replace(path)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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
                              "simulator_seed", "demand_sha256"):
                    if case.get(field) is None:
                        raise ValueError("test case requires %s" % field)
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
                run["resolved_config"] = resolved
                command = manifest.get("controller_commands", {}).get(controller_id)
                if command:
                    run["command"] = [str(token).format(**run) for token in command]
                runs.append(run)
    return runs


def _docker_argv(run, project_root, run_dir):
    command = run.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError("run has no command; integrate the controller before execution")
    return [
        "docker", "run", "--rm", "--network", "none",
        "--cidfile", str(Path(run_dir).resolve() / ".docker-container-id"),
        "-v", "%s:/work" % Path(project_root).resolve(), "-w", "/work",
        run["runtime_image"],
    ] + [str(token) for token in command]


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
    try:
        completed = subprocess.run(
            argv, cwd=str(project_root), universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        container_id = cidfile.read_text().strip() if cidfile.is_file() else ""
    finally:
        if cidfile.exists():
            cidfile.unlink()
    if completed.returncode:
        raise RuntimeError("executor exited %s: %s" % (
            completed.returncode, completed.stderr.strip()))
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("executor must print a JSON result on its final line")
    result = json.loads(lines[-1])
    result["stdout"] = completed.stdout
    result["stderr"] = completed.stderr
    provenance = {
        "provenance_version": 1,
        "mode": "network_campaign_docker",
        "docker_argv": argv,
        "container_id": container_id,
        "exit_code": completed.returncode,
        "code_commit": run.get("code_commit"),
        "execution_head_commit": source["head_commit"],
        "runtime_image": runtime["runtime_image"],
        "runtime_image_id": runtime["runtime_image_id"],
        "runtime_digest": runtime["runtime_digest"],
        "stdout_sha256": hashlib.sha256(
            completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            completed.stderr.encode("utf-8")).hexdigest(),
    }
    return result, provenance


def _assert_git_ancestor(project_root, older, newer):
    if older == newer:
        return
    for argv in (("git", "cat-file", "-e", older + "^{commit}"),
                 ("git", "merge-base", "--is-ancestor", older, newer)):
        completed = subprocess.run(
            list(argv), cwd=str(project_root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        if completed.returncode:
            raise ValueError("trusted Docker execution Git commit is not an ancestor")


def _verify_execution_provenance(run_dir, status, expected_run, project_root,
                                 current_head=None):
    provenance = status.get("execution_provenance", {})
    if provenance.get("mode") != "network_campaign_docker" \
            or provenance.get("provenance_version") != 1:
        raise ValueError("release run requires the trusted Docker executor")
    expected_argv = _docker_argv(expected_run, project_root, run_dir)
    if provenance.get("docker_argv") != expected_argv:
        raise ValueError("trusted Docker executor argv differs from the frozen run")
    expected_identity = {
        "code_commit": expected_run.get("code_commit"),
        "runtime_image": expected_run.get("runtime_image"),
        "runtime_image_id": expected_run.get("runtime_image_id"),
        "runtime_digest": expected_run.get("runtime_digest"),
    }
    if any(provenance.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("trusted Docker executor identity differs from the frozen run")
    if provenance.get("exit_code") != 0:
        raise ValueError("trusted Docker executor did not exit successfully")
    if not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("container_id", ""))):
        raise ValueError("trusted Docker executor requires the Docker container ID")
    for name in ("stdout", "stderr"):
        if provenance.get(name + "_sha256") != _sha256(run_dir / (name + ".log")):
            raise ValueError("trusted Docker executor %s hash mismatch" % name)
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
            "runtime_digest", "runtime_dockerfile_sha256")):
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
        "pending_integral_vehicle_seconds", "per_node_queue_integral_vehicle_seconds",
        "per_node_max_queue", "spillback_lane_seconds", "scheduled", "inserted",
        "departed", "arrived", "running", "pending", "removed",
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
        "queue_integral_vehicle_hours", "pending_integral_vehicle_seconds",
        "scheduled", "inserted", "departed", "arrived", "running", "pending",
        "removed", "censored_or_unfinished", "phase_switches",
        "intergreen_seconds", "max_red_seconds", "completed_travel_time_count",
    )
    if any(not _finite(metrics[field]) or float(metrics[field]) < 0
           for field in finite_fields):
        raise ValueError("network metric scalars must be finite and non-negative")
    integer_fields = (
        "observed_steps", "scheduled", "inserted", "departed", "arrived",
        "running", "pending", "removed", "censored_or_unfinished",
        "phase_switches", "completed_travel_time_count",
    )
    if any(float(metrics[field]) != int(float(metrics[field]))
           for field in integer_fields):
        raise ValueError("network metric counters must be integers")
    expected_hours = float(metrics["queue_integral_vehicle_seconds"]) / 3600.0
    if abs(float(metrics["queue_integral_vehicle_hours"]) - expected_hours) > 1e-12:
        raise ValueError("network queue integral units are inconsistent")
    if metrics["completion_denominator"] != "scheduled":
        raise ValueError("network metric completion denominator must be scheduled")
    scheduled = int(metrics["scheduled"])
    inserted = int(metrics["inserted"])
    arrived = int(metrics["arrived"])
    running = int(metrics["running"])
    pending = int(metrics["pending"])
    removed = int(metrics["removed"])
    if inserted != int(metrics["departed"]):
        raise ValueError("network metric inserted/departed mismatch")
    if scheduled != inserted + pending or inserted != arrived + running + removed:
        raise ValueError("network metric vehicle accounting does not conserve")
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
            "simulator_seed", "network_sha256", "demand_sha256", "runtime_digest",
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
                    != "network_campaign_docker":
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
        run_dir = campaign_dir / "runs" / _safe_id(run["run_id"])
        run_dir.mkdir(parents=True, exist_ok=True)
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

        _write_json(status_path, {
            "status": "running", "started_at": _utc_now(),
        })
        try:
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
            _validate_result(run, result)
            _write_json(run_dir / "run-manifest.json", run)
            _write_json(run_dir / "resolved-config.json", result["resolved_config"])
            _write_json(run_dir / "metrics.json", result["metrics"])
            (run_dir / "stdout.log").write_text(str(result.get("stdout", "")))
            (run_dir / "stderr.log").write_text(str(result.get("stderr", "")))
            artifacts = list(_ARTIFACTS)
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
