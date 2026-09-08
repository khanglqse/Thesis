import hashlib
import json
import platform
import subprocess

import pytest

import traffic_rl.eval.network_campaign as network_campaign
from traffic_rl.eval.network_campaign import (
    CONTROLLERS,
    bind_frozen_manifest,
    expand_runs,
    run_pending,
    verify_campaign,
)


def _manifest():
    return {
        "protocol_version": 2,
        "network_sha256": "a" * 64,
        "viewer_network_sha256": "a" * 64,
        "phase_contract_sha256": "9" * 64,
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "runtime_digest": "sha256:" + "b" * 64,
        "runtime_image": "cityflowproject/cityflow@sha256:" + "b" * 64,
        "runtime_image_id": "sha256:" + "b" * 64,
        "runtime_dockerfile_path": "docker/haichau-evaluation.Dockerfile",
        "runtime_dockerfile_sha256": "e" * 64,
        "code_commit": "1" * 40,
        "controlled_signals": 53,
        "agent_ids": ["N%02d" % index for index in range(53)],
        "default_horizon_steps": 3600,
        "resolved_config": {
            "network_path": "results/haichau_network_v2/network/roadnet.json",
            "phase_contract_path": (
                "results/haichau_network_v2/network/phase-contract.json"),
            "phase_contract_sha256": "9" * 64,
            "step_seconds": 1.0,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {
                "action_interval": 10, "yellow_time": 3,
                "min_green": 20, "maximum_red": 180,
            },
            "reward": {
                "queue_weight": 1.0, "downstream_block_weight": 0.1,
                "switch_penalty": 0.05,
            },
        },
        "controller_configs": {
            "tuned_fixed": {"green_duration": 30},
            "max_pressure": {"controller_version": 2},
            "hysteretic_mp": {
                "min_hold_decisions": 3, "switch_threshold": 2.5,
            },
            "shared_ddqn_legacy": {"controller_version": 2},
            "neighbor_phase_ddqn": {"controller_version": 2},
        },
        "controller_commands": dict(
            (controller, ["python3", "scripts/evaluate_haichau_network.py"])
            for controller in CONTROLLERS),
        "cases": [
            {
                "case_id": "test-normal-101",
                "split": "test",
                "regime": "normal",
                "demand_seed": 101,
                "simulator_seed": 201,
                "scheduled_vehicles": 1200,
                "demand_sha256": "c" * 64,
            },
            {
                "case_id": "test-pm-102",
                "split": "test",
                "regime": "pm_peak",
                "demand_seed": 102,
                "simulator_seed": 202,
                "scheduled_vehicles": 2400,
                "demand_sha256": "d" * 64,
            },
            {
                "case_id": "train-normal-1",
                "split": "train",
                "regime": "normal",
                "demand_seed": 1,
                "simulator_seed": 1,
                "demand_sha256": "e" * 64,
            },
        ],
    }


def test_frozen_protocol_resolves_a_command_for_every_controller():
    case_manifest = _manifest()
    case_manifest.pop("controller_commands")
    commands = dict(
        (controller, ["python3", "scripts/evaluate_haichau_network.py"])
        for controller in CONTROLLERS)
    protocol = dict(_manifest())
    protocol["controller_commands"] = commands

    frozen = bind_frozen_manifest(case_manifest, protocol)
    runs = expand_runs(frozen, [11], CONTROLLERS)

    selected = dict((run["controller_id"], run["command"]) for run in runs)
    assert set(selected) == set(CONTROLLERS)
    for controller in CONTROLLERS:
        assert selected[controller] == [
            "python3", "scripts/evaluate_haichau_network.py",
        ]


def test_frozen_controller_command_rejects_arguments_owned_by_runner():
    manifest = _manifest()
    manifest["controller_commands"]["tuned_fixed"] += [
        "--run-manifest", "other.json"]

    with pytest.raises(ValueError, match="evaluator entrypoint"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expansion_rejects_incomplete_evaluator_configuration():
    manifest = _manifest()
    manifest["resolved_config"].pop("phase_contract_path")

    with pytest.raises(ValueError, match="phase_contract_path"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expansion_rejects_runtime_config_drift_from_frozen_protocol():
    manifest = _manifest()
    manifest["resolved_config"]["phase_contract_sha256"] = "8" * 64

    with pytest.raises(ValueError, match="phase contract differs"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expansion_requires_and_binds_scheduled_vehicle_count():
    manifest = _manifest()
    run = expand_runs(manifest, [11], ["tuned_fixed"])[0]

    assert run["scheduled_vehicles"] == 1200
    assert run["resolved_config"]["scheduled_vehicles"] == 1200

    manifest["cases"][0].pop("scheduled_vehicles")
    with pytest.raises(ValueError, match="scheduled_vehicles"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expansion_preserves_common_and_controller_runtime_configuration():
    run = expand_runs(_manifest(), [11], ["hysteretic_mp"])[0]

    assert run["resolved_config"]["network_path"].endswith("roadnet.json")
    assert run["resolved_config"]["normalization"] == {
        "count_norm": 20.0, "capacity_norm": 40.0,
    }
    assert run["resolved_config"]["simulation"]["maximum_red"] == 180
    assert run["resolved_config"]["reward"]["switch_penalty"] == 0.05
    assert run["resolved_config"]["min_hold_decisions"] == 3


def test_run_manifest_is_materialized_before_executor(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def inspecting_executor(received, run_dir):
        manifest_path = run_dir / "run-manifest.json"
        assert json.loads(manifest_path.read_text()) == received
        assert (run_dir / "runtime-configs").is_dir()
        return _executor(run, run_dir)

    result = run_pending(tmp_path, inspecting_executor)

    assert result["completed"] == 1
    manifest_path = tmp_path / "runs" / run["run_id"] / "run-manifest.json"
    assert json.loads(manifest_path.read_text()) == run


def test_all_run_manifests_exist_before_docker_runtime_inspection(
        tmp_path, monkeypatch):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    campaign_dir = tmp_path / "results" / "final"
    _write_campaign(campaign_dir, runs)

    def assert_inputs_exist(*args, **kwargs):
        for run in runs:
            run_dir = campaign_dir / "runs" / run["run_id"]
            assert json.loads(
                (run_dir / "run-manifest.json").read_text()) == run
            assert (run_dir / "runtime-configs").is_dir()
        return {"head_commit": runs[0]["code_commit"]}

    monkeypatch.setattr(network_campaign, "verify_git_checkout", assert_inputs_exist)
    monkeypatch.setattr(network_campaign, "verify_runtime", assert_inputs_exist)
    monkeypatch.setattr(
        network_campaign, "_trusted_docker_executor",
        lambda run, run_dir, project_root, source, runtime: (
            _executor(run, run_dir), {"mode": "test"}))

    result = run_pending(campaign_dir, project_root=tmp_path)

    assert result["completed"] == 2


def test_executor_cannot_change_its_hash_bound_run_manifest(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def mutating_executor(received, run_dir):
        (run_dir / "run-manifest.json").write_text("{}\n")
        return _executor(received, run_dir)

    result = run_pending(tmp_path, mutating_executor)

    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["status"] == "failed"
    assert "changed during execution" in status["error"]


def test_docker_command_routes_materialized_manifest_and_runtime_directory(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    run_dir = tmp_path / "results" / "final" / "runs" / run["run_id"]
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "run-manifest.json"
    network_campaign._write_json(manifest_path, run)

    argv = network_campaign._docker_argv(run, tmp_path, run_dir)

    assert argv[-4:] == [
        "--run-manifest",
        "/work/results/final/runs/%s/run-manifest.json" % run["run_id"],
        "--runtime-dir",
        "/work/results/final/runs/%s/runtime-configs" % run["run_id"],
    ]


def _write_campaign(path, runs):
    path.mkdir(parents=True, exist_ok=True)
    (path / "campaign-manifest.json").write_text(json.dumps({
        "campaign_version": 2,
        "evidence_namespace": "haichau_network_v2",
        "runs": runs,
    }))


def _executor(run, run_dir):
    nodes = dict((node_id, 0.0) for node_id in run["agent_ids"])
    return {
        "resolved_config": run["resolved_config"],
        "metrics": {
            "case_id": run["case_id"],
            "regime": run["regime"],
            "controller_id": run["controller_id"],
            "learning_seed": run["learning_seed"],
            "demand_seed": run["demand_seed"],
            "simulator_seed": run["simulator_seed"],
            "scheduled_vehicles": run["scheduled_vehicles"],
            "network_sha256": run["network_sha256"],
            "viewer_network_sha256": run["viewer_network_sha256"],
            "demand_sha256": run["demand_sha256"],
            "demand_path": run["demand_path"],
            "runtime_digest": run["runtime_digest"],
            "runtime_image": run["runtime_image"],
            "runtime_image_id": run["runtime_image_id"],
            "runtime_dockerfile_path": run["runtime_dockerfile_path"],
            "runtime_dockerfile_sha256": run["runtime_dockerfile_sha256"],
            "code_commit": run["code_commit"],
            "checkpoint_sha256": run.get("checkpoint_sha256"),
            "checkpoint_contract_sha256": run.get("checkpoint_contract_sha256"),
            "completed_steps": run["horizon_steps"],
            "observed_steps": run["horizon_steps"],
            "observed_seconds": run["horizon_steps"],
            "queue_integral_vehicle_seconds": 123.0,
            "queue_integral_vehicle_hours": 123.0 / 3600,
            "pending_integral_vehicle_seconds": 0.0,
            "per_node_queue_integral_vehicle_seconds": nodes,
            "per_node_max_queue": nodes,
            "spillback_lane_seconds": {},
            "scheduled": run["scheduled_vehicles"],
            "inserted": 0,
            "departed": 0,
            "arrived": 0,
            "running": 0,
            "pending": run["scheduled_vehicles"],
            "removed": 0,
            "censored_or_unfinished": run["scheduled_vehicles"],
            "completion_denominator": "scheduled",
            "completion_rate": 0.0,
            "insertion_rate": 0.0,
            "completed_travel_time_count": 0,
            "phase_switches": 0,
            "intergreen_seconds": 0.0,
            "max_red_seconds": 0.0,
            "travel_time_completed_mean": None,
            "travel_time_completed_median": None,
            "travel_time_completed_p95": None,
            "fresh_evaluation": True,
        },
        "stdout": "fresh run\n",
        "stderr": "",
    }


def test_deterministic_baseline_is_not_multiplied_by_learning_seed():
    runs = expand_runs(_manifest(), [11, 12, 13, 14, 15], ["tuned_fixed"])
    assert len(runs) == 2
    assert all(run["learning_seed"] is None for run in runs)


def test_learning_controller_crosses_test_cases_with_learning_seeds():
    runs = expand_runs(
        _manifest(), [11, 12], ["tuned_fixed", "neighbor_phase_ddqn"])
    assert len(runs) == 6
    learned = [run for run in runs
               if run["controller_id"] == "neighbor_phase_ddqn"]
    assert {run["learning_seed"] for run in learned} == {11, 12}
    assert all(run["fresh_evaluation"] is True for run in runs)
    assert all(run["evidence_namespace"] == "haichau_network_v2" for run in runs)


def test_expansion_requires_frozen_code_and_runtime_identity():
    manifest = _manifest()
    manifest.pop("code_commit")
    with pytest.raises(ValueError, match="code_commit"):
        expand_runs(manifest, [11], ["tuned_fixed"])


def test_expanded_run_freezes_resolved_config_and_checkpoint_contract():
    manifest = _manifest()
    manifest["controller_configs"] = {
        "neighbor_phase_ddqn": {"gamma": 0.95, "hidden_size": 64},
    }
    manifest["checkpoints"] = [{
        "controller_id": "neighbor_phase_ddqn",
        "learning_seed": 11,
        "path": "checkpoints/seed-11.npz",
        "sha256": "f" * 64,
        "checkpoint_contract": {"obs_schema_version": 2},
    }]

    run = expand_runs(manifest, [11], ["neighbor_phase_ddqn"])[0]

    assert run["resolved_config"]["gamma"] == 0.95
    assert run["resolved_config"]["simulator_seed"] == 201
    assert run["checkpoint_sha256"] == "f" * 64
    assert len(run["checkpoint_contract_sha256"]) == 64
    assert run["code_commit"] == "1" * 40
    assert run["resolved_config"]["code_commit"] == "1" * 40
    assert run["runtime_image"].endswith(run["runtime_digest"])


def test_resume_rechecks_hash_before_skipping(tmp_path):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    _write_campaign(tmp_path, runs)
    first = run_pending(tmp_path, _executor)
    assert first == {"completed": 2, "failed": 0, "skipped": 0, "total": 2}

    metrics_path = tmp_path / "runs" / runs[0]["run_id"] / "metrics.json"
    metrics_path.write_text("corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_pending(tmp_path, _executor)


def test_resume_and_verify_reject_relabelled_complete_run(tmp_path):
    runs = expand_runs(_manifest(), [11], ["tuned_fixed"])
    _write_campaign(tmp_path, runs)
    assert run_pending(tmp_path, _executor)["completed"] == 2

    runs[0]["demand_sha256"] = "9" * 64
    runs[0]["simulator_seed"] = 999
    _write_campaign(tmp_path, runs)

    with pytest.raises(ValueError, match="run spec"):
        run_pending(tmp_path, _executor)
    with pytest.raises(ValueError, match="run spec"):
        verify_campaign(tmp_path)


def test_completed_run_status_binds_code_and_runtime_identity(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])
    assert run_pending(tmp_path, _executor)["completed"] == 1

    status_path = tmp_path / "runs" / run["run_id"] / "status.json"
    status = json.loads(status_path.read_text())
    assert status["code_commit"] == run["code_commit"]
    assert status["runtime_image"] == run["runtime_image"]
    assert status["runtime_image_id"] == run["runtime_image_id"]

    status["code_commit"] = "2" * 40
    status_path.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="status code/runtime identity"):
        verify_campaign(tmp_path)


def test_release_verification_rejects_injected_executor_even_if_it_claims_docker(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def untrusted_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["execution_provenance"] = {
            "mode": "verified_docker", "exit_code": 0,
            "runtime_image_id": run["runtime_image_id"],
        }
        return result

    assert run_pending(tmp_path, untrusted_executor)["completed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["execution_provenance"]["mode"] == "injected"
    with pytest.raises(ValueError, match="trusted Docker executor"):
        verify_campaign(tmp_path, require_release_provenance=True)


def test_hand_edited_docker_status_requires_a_real_retained_container(
        tmp_path, monkeypatch):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    run["command"] = ["python3", "evaluate.py", "--run-id", run["run_id"]]
    _write_campaign(tmp_path, [run])
    result = _executor(run, tmp_path)
    assert run_pending(tmp_path, lambda unused_run, unused_dir: result)["completed"] == 1
    run_dir = tmp_path / "runs" / run["run_id"]
    stdout = json.dumps({
        "resolved_config": result["resolved_config"],
        "metrics": result["metrics"],
    }) + "\n"
    (run_dir / "stdout.log").write_text(stdout)
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["artifact_sha256"]["stdout.log"] = hashlib.sha256(
        stdout.encode()).hexdigest()
    status["execution_provenance"] = {
        "provenance_version": 2,
        "mode": "retained_docker_container",
        "docker_argv": network_campaign._docker_argv(run, tmp_path, run_dir),
        "container_id": "c" * 64,
        "exit_code": 0,
        "code_commit": run["code_commit"],
        "execution_head_commit": run["code_commit"],
        "runtime_image": run["runtime_image"],
        "runtime_image_id": run["runtime_image_id"],
        "runtime_digest": run["runtime_digest"],
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
    }
    monkeypatch.setattr(
        network_campaign.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("verifier used injected subprocess.run"))

    with pytest.raises(ValueError, match="Docker"):
        network_campaign._verify_execution_provenance(
            run_dir, status, run, tmp_path, run["code_commit"])


def test_docker_launch_is_detached_and_keeps_cli_diagnostics_out_of_container_logs(
        tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    run["command"] = ["python3", "evaluate.py"]
    run_dir = tmp_path / "results" / "run"
    run_dir.mkdir(parents=True)
    network_campaign._write_json(run_dir / "run-manifest.json", run)

    argv = network_campaign._docker_argv(run, tmp_path, run_dir)
    diagnostics = network_campaign._docker_cli_diagnostics(
        "WARNING: image platform linux/amd64 differs from host linux/arm64/v8\n",
        "")

    assert "--detach" in argv
    assert diagnostics == {
        "schema_version": 1,
        "docker_run_stderr": (
            "WARNING: image platform linux/amd64 differs from host linux/arm64/v8\n"
        ),
        "docker_wait_stderr": "",
    }


@pytest.mark.docker_host
def test_live_platform_warning_is_separate_and_retained_logs_reverify(tmp_path):
    image = (
        "traffic-rl-cityflow-research@sha256:"
        "8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"
    )
    image_id = (
        "sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run = {
        "command": [
            "python3", "-c",
            "import json,sys; print('container-stderr', file=sys.stderr); "
            "print(json.dumps({'probe': True}))",
        ],
        "code_commit": "1" * 40,
        "runtime_image": image,
        "runtime_image_id": image_id,
        "runtime_digest": image.split("@", 1)[1],
    }
    source = {"code_commit": run["code_commit"], "head_commit": run["code_commit"]}
    runtime = dict((key, run[key]) for key in (
        "runtime_image", "runtime_image_id", "runtime_digest"))
    network_campaign._write_json(run_dir / "run-manifest.json", run)
    container_id = None
    try:
        result, provenance = network_campaign._trusted_docker_executor(
            run, run_dir, tmp_path, source, runtime)
        container_id = provenance["container_id"]
        (run_dir / "stdout.log").write_text(result["stdout"])
        (run_dir / "stderr.log").write_text(result["stderr"])

        assert result["stderr"] == "container-stderr\n"
        assert "container-stderr" not in result["docker_cli_diagnostics"][
            "docker_run_stderr"]
        if platform.machine().lower() in ("arm64", "aarch64"):
            assert "platform" in result["docker_cli_diagnostics"][
                "docker_run_stderr"].lower()
            assert "linux/amd64" in result["docker_cli_diagnostics"][
                "docker_run_stderr"]
        receipt = network_campaign._retained_container_receipt(
            run, run_dir, tmp_path, container_id)
        assert receipt["stderr_sha256"] == hashlib.sha256(
            b"container-stderr\n").hexdigest()

        cli_stderr = result["docker_cli_diagnostics"]["docker_run_stderr"]
        (run_dir / "stderr.log").write_text(
            (cli_stderr or "synthetic CLI diagnostic\n") + result["stderr"])
        with pytest.raises(ValueError, match="stderr differs"):
            network_campaign._retained_container_receipt(
                run, run_dir, tmp_path, container_id)
    finally:
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, check=False)


def test_incomplete_network_metric_schema_is_never_marked_complete(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def incomplete_executor(run, run_dir):
        return {
            "resolved_config": run["resolved_config"],
            "metrics": {
                "case_id": run["case_id"],
                "regime": run["regime"],
                "controller_id": run["controller_id"],
                "learning_seed": run["learning_seed"],
                "demand_seed": run["demand_seed"],
                "simulator_seed": run["simulator_seed"],
                "scheduled_vehicles": run["scheduled_vehicles"],
                "network_sha256": run["network_sha256"],
                "viewer_network_sha256": run["viewer_network_sha256"],
                "demand_sha256": run["demand_sha256"],
                "demand_path": run["demand_path"],
                "runtime_digest": run["runtime_digest"],
                "runtime_image": run["runtime_image"],
                "runtime_image_id": run["runtime_image_id"],
                "runtime_dockerfile_path": run["runtime_dockerfile_path"],
                "runtime_dockerfile_sha256": run["runtime_dockerfile_sha256"],
                "code_commit": run["code_commit"],
                "checkpoint_sha256": run.get("checkpoint_sha256"),
                "checkpoint_contract_sha256": run.get(
                    "checkpoint_contract_sha256"),
                "completed_steps": run["horizon_steps"],
                "fresh_evaluation": True,
            },
        }

    result = run_pending(tmp_path, incomplete_executor)

    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["status"] == "failed"
    assert "network metric" in status["error"]


def test_metrics_scheduled_count_must_match_frozen_case(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def wrong_scheduled_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"]["scheduled"] -= 1
        result["metrics"]["pending"] -= 1
        result["metrics"]["censored_or_unfinished"] -= 1
        return result

    result = run_pending(tmp_path, wrong_scheduled_executor)

    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert "scheduled_vehicles" in status["error"]


def test_incomplete_run_is_rebuilt_and_only_then_marked_complete(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])
    stale = tmp_path / "runs" / run["run_id"]
    stale.mkdir(parents=True)
    (stale / "status.json").write_text(json.dumps({"status": "running"}))
    (stale / "metrics.json").write_text("stale")

    result = run_pending(tmp_path, _executor)

    assert result["completed"] == 1
    status = json.loads((stale / "status.json").read_text())
    assert status["status"] == "complete"
    assert set(status["artifact_sha256"]) == {
        "run-manifest.json", "resolved-config.json", "metrics.json",
        "stdout.log", "stderr.log",
    }
    assert json.loads((stale / "metrics.json").read_text())["fresh_evaluation"] is True


@pytest.mark.parametrize("values", [(-1.0, 1.0, 1.0), (2.0, 3.0, 2.0)])
def test_invalid_completed_travel_aggregates_are_never_complete(tmp_path, values):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def invalid_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"].update({
            "inserted": 1, "departed": 1, "arrived": 1,
            "pending": run["scheduled_vehicles"] - 1,
            "censored_or_unfinished": run["scheduled_vehicles"] - 1,
            "completed_travel_time_count": 1,
            "completion_rate": 1.0 / run["scheduled_vehicles"],
            "insertion_rate": 1.0 / run["scheduled_vehicles"],
            "travel_time_completed_mean": values[0],
            "travel_time_completed_median": values[1],
            "travel_time_completed_p95": values[2],
        })
        return result

    assert run_pending(tmp_path, invalid_executor)["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert "travel-time" in status["error"]


def test_horizon_mismatch_records_failure_without_complete_status(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])

    def short_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"]["completed_steps"] -= 1
        return result

    result = run_pending(tmp_path, short_executor)

    assert result == {"completed": 0, "failed": 1, "skipped": 0, "total": 1}
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert status["status"] == "failed"
    assert "horizon" in status["error"]


def test_campaign_rejects_legacy_source_rows(tmp_path):
    run = expand_runs(_manifest(), [11], ["tuned_fixed"])[0]
    _write_campaign(tmp_path, [run])

    def legacy_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["metrics"]["source_run_dir"] = "results/haichau_rush/evaluation"
        return result

    result = run_pending(tmp_path, legacy_executor)
    assert result["failed"] == 1
    status = json.loads(
        (tmp_path / "runs" / run["run_id"] / "status.json").read_text())
    assert "legacy" in status["error"]


def test_executor_replay_is_part_of_the_immutable_hash_set(tmp_path):
    run = expand_runs(_manifest(), [11], ["neighbor_phase_ddqn"])[0]
    _write_campaign(tmp_path, [run])

    def replay_executor(run, run_dir):
        result = _executor(run, run_dir)
        result["replay"] = {
            "sample_seconds": 5,
            "frames": [{"t": 0, "nodes": {}}, {"t": 5, "nodes": {}}],
            "metrics": {"queue_integral_vehicle_seconds": 123.0},
        }
        return result

    assert run_pending(tmp_path, replay_executor)["completed"] == 1
    run_dir = tmp_path / "runs" / run["run_id"]
    status = json.loads((run_dir / "status.json").read_text())
    assert "replay.json" in status["artifact_sha256"]
    assert (run_dir / "replay.json").is_file()
