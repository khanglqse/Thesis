"""Resume-safe expansion and execution of matched Hai Chau evaluations."""

import datetime
import hashlib
import json
import re
from pathlib import Path


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
                    "demand_sha256": case["demand_sha256"],
                    "runtime_digest": manifest.get("runtime_digest"),
                    "evidence_namespace": "haichau_network_v2",
                    "fresh_evaluation": True,
                }
                command = manifest.get("controller_commands", {}).get(controller_id)
                if command:
                    run["command"] = [str(token).format(**run) for token in command]
                runs.append(run)
    return runs


def _verify_complete(run_dir, status):
    hashes = status.get("artifact_sha256", {})
    if set(hashes) != set(_ARTIFACTS):
        raise ValueError("complete run has an incomplete artifact hash set")
    for name in _ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            raise ValueError("complete run is missing artifact: %s" % name)
        if _sha256(path) != hashes[name]:
            raise ValueError("artifact hash mismatch: %s" % path)


def _validate_result(run, result):
    for field in ("resolved_config", "metrics"):
        if not isinstance(result.get(field), dict):
            raise ValueError("executor result requires %s" % field)
    metrics = result["metrics"]
    if metrics.get("case_id") != run["case_id"]:
        raise ValueError("case mismatch")
    if metrics.get("controller_id") != run["controller_id"]:
        raise ValueError("controller mismatch")
    if int(metrics.get("completed_steps", -1)) != run["horizon_steps"]:
        raise ValueError("horizon mismatch")
    if metrics.get("fresh_evaluation") is not True:
        raise ValueError("fresh evaluation provenance is required")
    source = str(metrics.get("source_run_dir", ""))
    normalized = source.replace("\\", "/").lower()
    if "results/haichau" in normalized \
            and "results/haichau_network_v2" not in normalized:
        raise ValueError("legacy Hai Chau evidence cannot enter the fresh campaign")


def verify_campaign(campaign_dir):
    campaign_dir = Path(campaign_dir)
    manifest_path = campaign_dir / "campaign-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("campaign-manifest.json is missing")
    campaign = json.loads(manifest_path.read_text())
    runs = campaign.get("runs", [])
    for run in runs:
        run_dir = campaign_dir / "runs" / _safe_id(run["run_id"])
        status_path = run_dir / "status.json"
        if not status_path.is_file():
            raise ValueError("run status is missing: %s" % run["run_id"])
        status = json.loads(status_path.read_text())
        if status.get("status") != "complete":
            raise ValueError("run is not complete: %s" % run["run_id"])
        _verify_complete(run_dir, status)
        metrics = json.loads((run_dir / "metrics.json").read_text())
        _validate_result(run, {
            "resolved_config": json.loads(
                (run_dir / "resolved-config.json").read_text()),
            "metrics": metrics,
        })
    return {"complete": len(runs), "total": len(runs)}


def run_pending(campaign_dir, executor):
    """Run incomplete bundles and verify immutable completed bundles."""
    campaign_dir = Path(campaign_dir)
    manifest_path = campaign_dir / "campaign-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("campaign-manifest.json is missing")
    campaign = json.loads(manifest_path.read_text())
    if campaign.get("evidence_namespace") != "haichau_network_v2":
        raise ValueError("campaign evidence_namespace must be haichau_network_v2")
    runs = campaign.get("runs", [])
    counts = {"completed": 0, "failed": 0, "skipped": 0, "total": len(runs)}
    for run in runs:
        run_dir = campaign_dir / "runs" / _safe_id(run["run_id"])
        run_dir.mkdir(parents=True, exist_ok=True)
        status_path = run_dir / "status.json"
        if status_path.is_file():
            status = json.loads(status_path.read_text())
            if status.get("status") == "complete":
                _verify_complete(run_dir, status)
                counts["skipped"] += 1
                continue

        _write_json(status_path, {
            "status": "running", "started_at": _utc_now(),
        })
        try:
            result = executor(dict(run), run_dir)
            _validate_result(run, result)
            _write_json(run_dir / "run-manifest.json", run)
            _write_json(run_dir / "resolved-config.json", result["resolved_config"])
            _write_json(run_dir / "metrics.json", result["metrics"])
            (run_dir / "stdout.log").write_text(str(result.get("stdout", "")))
            (run_dir / "stderr.log").write_text(str(result.get("stderr", "")))
            hashes = dict((name, _sha256(run_dir / name)) for name in _ARTIFACTS)
            _write_json(status_path, {
                "status": "complete",
                "completed_at": _utc_now(),
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
