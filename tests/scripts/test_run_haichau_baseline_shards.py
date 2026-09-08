import json
import subprocess
import sys

import pytest
import yaml

from scripts import run_haichau_baseline_shards
from traffic_rl.train.network_trainer import canonical_json_sha256, resolve_training_config


def _manifest():
    return {
        "network": {"sha256": "network" * 8},
        "generator_config_sha256": "generator" * 8,
        "runtime": {
            "derived_image_tag": "traffic-rl-cityflow-research:v2",
            "platform": "linux/amd64",
        },
        "simulation": {"action_interval": 10},
        "cases": [
            {"case_id": "normal", "split": "validation", "scenario": "normal",
             "flow_sha256": "normal" * 8},
            {"case_id": "peak", "split": "validation", "scenario": "am_peak",
             "flow_sha256": "peak" * 8},
        ],
    }


def _config():
    return {
        "baseline": {"controller": "validation_tuned_fixed",
                     "search_green_durations": [20, 25, 30, 35]},
        "tiers": {"final": {"episodes": 1, "horizon_seconds": 120,
                            "eval_every": 1}},
    }


def _write_inputs(root):
    manifest = root / "manifest.json"
    config = root / "config.yaml"
    manifest.write_text(json.dumps(_manifest()))
    config.write_text(yaml.safe_dump(_config()))
    return manifest, config


def test_cli_runs_from_a_checkout_without_an_installed_package():
    result = subprocess.run(
        [sys.executable, "scripts/run_haichau_baseline_shards.py", "--help"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    assert result.returncode == 0
    assert "--durations-per-shard" in result.stdout


def _runner(root, bad_binding=False):
    def run(command, cwd=None, stdout=None, stderr=None):
        config_arg = command[command.index("--config") + 1]
        artifact_arg = command[command.index("--precompute-baseline-tuning") + 1]
        config_path = root / config_arg[len("/work/"):]
        artifact_path = root / artifact_arg[len("/work/"):]
        manifest = json.loads((root / "manifest.json").read_text())
        config = yaml.safe_load(config_path.read_text())
        resolved = resolve_training_config(config, "final", 11)
        resolved["simulation"] = manifest["simulation"]
        validation = [case for case in manifest["cases"]
                      if case["split"] == "validation"]
        binding = run_haichau_baseline_shards.expected_binding(
            manifest, validation, resolved)
        if bad_binding:
            binding = dict(binding, horizon_seconds=999)
        candidates = []
        for duration in config["baseline"]["search_green_durations"]:
            rows = [{"case_id": case["case_id"], "scenario": case["scenario"],
                     "queue_integral_vehicle_seconds": float(duration),
                     "completion_rate": 1.0,
                     "insertion_rate": 1.0} for case in validation]
            candidates.append({
                "fixed_green_duration": duration,
                "mean_queue_integral_vehicle_seconds": float(duration),
                "rows": rows,
            })
        payload = {
            "schema_version": 1,
            "method": "validation_grid_search",
            "search_space": {"fixed_green_duration": list(
                config["baseline"]["search_green_durations"])},
            "selected": {"fixed_green_duration": min(
                config["baseline"]["search_green_durations"])},
            "candidates": candidates,
            "binding": binding,
        }
        payload["tuning_sha256"] = canonical_json_sha256(payload)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(payload))

        class Result:
            returncode = 0
        return Result()
    return run


def test_run_precompute_shards_merges_durations_in_full_configured_order(tmp_path):
    manifest, config = _write_inputs(tmp_path)
    artifact = tmp_path / "final-baseline-tuning.json"

    result = run_haichau_baseline_shards.run_precompute_shards(
        tmp_path, manifest, config, artifact, max_concurrency=2,
        durations_per_shard=2, runner=_runner(tmp_path))

    merged = json.loads(artifact.read_text())
    assert [candidate["fixed_green_duration"] for candidate in merged["candidates"]] == [
        20, 25, 30, 35]
    assert merged["selected"] == {"fixed_green_duration": 20}
    assert merged["tuning_sha256"] == canonical_json_sha256(
        dict((key, value) for key, value in merged.items()
             if key != "tuning_sha256"))
    assert result["status"] == "complete"
    for job in result["jobs"]:
        assert job["command"][:5] == ["docker", "run", "--rm", "--platform", "linux/amd64"]
        assert "traffic-rl-cityflow-research:v2" in job["command"]
        assert "--config" in job["command"]
        assert "--precompute-baseline-tuning" in job["command"]
    assert (tmp_path / ".baseline-tuning-shards" / "final-baseline-tuning" /
            "status.json").is_file()
    shard_config = tmp_path / ".baseline-tuning-shards" / "final-baseline-tuning" / "shards" / "000" / "config.yaml"
    assert yaml.safe_load(shard_config.read_text())["baseline"]["search_green_durations"] == [20, 25]
    assert shard_config.stat().st_mode & 0o222 == 0


def test_run_precompute_shards_persists_running_state_before_starting_shard(tmp_path):
    manifest, config = _write_inputs(tmp_path)
    artifact = tmp_path / "final-baseline-tuning.json"
    status_path = (tmp_path / ".baseline-tuning-shards" /
                   "final-baseline-tuning" / "status.json")
    observed_states = []
    complete_runner = _runner(tmp_path)

    def runner(command, cwd=None, stdout=None, stderr=None):
        config_arg = command[command.index("--config") + 1]
        shard_index = int(config_arg.split("/")[-2])
        status = json.loads(status_path.read_text())
        observed_states.append(status["jobs"][shard_index]["state"])
        return complete_runner(command, cwd=cwd, stdout=stdout, stderr=stderr)

    run_haichau_baseline_shards.run_precompute_shards(
        tmp_path, manifest, config, artifact, max_concurrency=1,
        durations_per_shard=2, runner=runner)

    assert observed_states == ["running", "running"]


def test_run_precompute_shards_rejects_existing_artifact_or_partial_workdir(tmp_path):
    manifest, config = _write_inputs(tmp_path)
    artifact = tmp_path / "final-baseline-tuning.json"
    artifact.write_text("already present")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        run_haichau_baseline_shards.run_precompute_shards(
            tmp_path, manifest, config, artifact, runner=_runner(tmp_path))

    artifact.unlink()
    partial = tmp_path / ".baseline-tuning-shards" / "final-baseline-tuning"
    partial.mkdir(parents=True)
    with pytest.raises(ValueError, match="partial shard state"):
        run_haichau_baseline_shards.run_precompute_shards(
            tmp_path, manifest, config, artifact, runner=_runner(tmp_path))


def test_run_precompute_shards_rejects_binding_drift_without_writing_merged_artifact(tmp_path):
    manifest, config = _write_inputs(tmp_path)
    artifact = tmp_path / "final-baseline-tuning.json"

    with pytest.raises(ValueError, match="binding"):
        run_haichau_baseline_shards.run_precompute_shards(
            tmp_path, manifest, config, artifact, durations_per_shard=1,
            runner=_runner(tmp_path, bad_binding=True))

    assert not artifact.exists()
