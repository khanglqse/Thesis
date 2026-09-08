import copy
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from traffic_rl.eval.capacity_calibration import (
    execute_campaign,
    prepare_campaign,
)
from traffic_rl.research.artifacts import canonical_sha256
from traffic_rl.research.capacity_decision import (
    _load_prepare,
    apply_capacity_decision,
)


def test_capacity_decision_module_exposes_bridge_entry_point():
    module = Path(__file__).parents[2] / "src/traffic_rl/research/capacity_decision.py"

    assert module.is_file()
    namespace = {}
    exec(compile(module.read_text(), str(module), "exec"), namespace)
    assert callable(namespace["apply_capacity_decision"])


def test_load_prepare_imports_the_project_script_without_project_root_on_sys_path(tmp_path):
    script = tmp_path / "scripts/prepare_haichau_network_v2.py"
    script.parent.mkdir()
    script.write_text("def prepare(*args, **kwargs):\n    return 'loaded'\n")

    prepare = _load_prepare(tmp_path)

    assert prepare() == "loaded"


def _commit(root, message):
    subprocess.check_call(["git", "-C", str(root), "add", "."])
    subprocess.check_call(["git", "-C", str(root), "commit", "-qm", message])


def _metrics(run):
    scheduled = int(run["scheduled_vehicles"])
    scenario = run["scenario"]
    inserted = scheduled
    completion = {"normal": 0.80, "am_peak": 0.70, "pm_peak": 0.60}[scenario]
    arrived = min(inserted, int(round(scheduled * completion)))
    queue = 200.0 if scenario == "pm_peak" else 100.0
    return {
        "observed_steps": 3600, "observed_seconds": 3600,
        "scheduled": scheduled, "due": scheduled, "unreleased": 0,
        "inserted": inserted, "departed": inserted, "arrived": arrived,
        "running": inserted - arrived, "pending": 0, "removed": 0,
        "completion_rate": float(arrived) / scheduled,
        "insertion_rate": 1.0,
        "network_queue_integral_vehicle_seconds": queue,
        "pending_integral_vehicle_seconds": 0.0,
        "queue_integral_vehicle_seconds": queue,
        "queue_integral_vehicle_hours": queue / 3600.0,
        "per_node_queue_integral_vehicle_seconds": {"A": queue},
        "per_node_max_queue": {"A": 10.0},
        "spillback_lane_seconds": {},
    }


def _passing_executor(project_root, run, run_dir):
    metrics = _metrics(run)
    return metrics, [{"step": 3600, "metrics": metrics}]


def _stage_d_project(tmp_path, scales=(0.25, 0.30)):
    # Reuse the calibration fixture because it intentionally names a missing
    # test flow; successful decision validation proves the bridge never opens it.
    from tests.eval.test_capacity_calibration import _project

    root, manifest_path, training_path = _project(tmp_path)
    generator = root / "inputs/generator.yaml"
    generator.write_text(
        "dataset_id: fixture\nroute_count: 1\nreference_interval_seconds: 72.0\n")
    (root / "scripts/prepare_haichau_network_v2.py").write_text("# fixture preparer\n")
    manifest = json.loads(manifest_path.read_text())
    from traffic_rl.research.artifacts import sha256_file
    manifest["generator_config_sha256"] = sha256_file(generator)
    manifest_path.write_text(json.dumps(manifest))
    _commit(root, "add reference interval")
    stage = root / "diagnostics/stage-d"
    prepare_campaign(root, manifest_path, training_path, stage, "stage-d",
                     chosen_scales=list(scales))
    summary = execute_campaign(root, stage, run_executor=_passing_executor)
    assert summary["stage_gates"]["highest_passing_scale"] == max(scales)
    _commit(root, "record stage d")
    return root, stage, generator


def test_validate_only_recomputes_complete_evidence_and_selects_highest_passing_scale(tmp_path):
    root, stage, config = _stage_d_project(tmp_path)

    decision = apply_capacity_decision(
        root, stage, config, validate_only=True)

    assert decision["selected_scale"] == "0.30"
    assert decision["reference_interval"]["exact_fraction"] == "240/1"
    assert decision["reference_interval"]["yaml_decimal"] == "240"
    assert decision["evidence"]["campaign_sha256"]
    assert decision["evidence"]["summary_sha256"]
    assert len(decision["evidence"]["results"]) == 24
    assert decision["decision_identity_sha256"] == canonical_sha256({
        key: value for key, value in decision.items()
        if key != "decision_identity_sha256"
    })


def test_validation_rejects_summary_gate_tampering(tmp_path):
    root, stage, config = _stage_d_project(tmp_path)
    summary_path = stage / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["stage_gates"]["highest_passing_scale"] = 0.25
    summary_path.write_text(json.dumps(summary))

    with pytest.raises(ValueError, match="summary sha256|recomputed stage gates"):
        apply_capacity_decision(root, stage, config, validate_only=True)


def test_validation_rejects_missing_expected_stage_d_run_even_with_rehashed_campaign(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.30,))
    campaign_path = stage / "campaign-manifest.json"
    campaign = json.loads(campaign_path.read_text())
    campaign["runs"] = campaign["runs"][:-1]
    campaign["campaign_identity_sha256"] = canonical_sha256({
        key: value for key, value in campaign.items()
        if key != "campaign_identity_sha256"
    })
    campaign_path.write_text(json.dumps(campaign))

    with pytest.raises(ValueError, match="exact Stage-D run matrix"):
        apply_capacity_decision(root, stage, config, validate_only=True)


def test_validation_rejects_release_eligible_provenance(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.30,))
    campaign_path = stage / "campaign-manifest.json"
    campaign = json.loads(campaign_path.read_text())
    campaign["eligible_for_release"] = True
    campaign["campaign_identity_sha256"] = canonical_sha256({
        key: value for key, value in campaign.items()
        if key != "campaign_identity_sha256"
    })
    campaign_path.write_text(json.dumps(campaign))

    with pytest.raises(ValueError, match="diagnostic-only"):
        apply_capacity_decision(root, stage, config, validate_only=True)


def test_reference_interval_records_repeating_decimal_with_exact_fraction(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.35,))

    decision = apply_capacity_decision(root, stage, config, validate_only=True)

    assert decision["reference_interval"]["exact_fraction"] == "1440/7"
    assert decision["reference_interval"]["yaml_decimal"] == \
        "205.714285714285714285714285714"


def test_apply_requires_explicit_new_version_and_a_clean_checkout(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.30,))

    with pytest.raises(ValueError, match="--new-version"):
        apply_capacity_decision(root, stage, config)

    (root / "untracked.txt").write_text("dirty\n")
    with pytest.raises(ValueError, match="clean git checkout"):
        apply_capacity_decision(root, stage, config, new_version=True)


def test_apply_stages_generation_then_updates_config_outputs_and_hashed_decision(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.25, 0.30))
    calls = []

    def fake_prepare(config_path, root=None, new_version=False):
        root = Path(root)
        calls.append((root, new_version))
        payload = yaml.safe_load(Path(config_path).read_text())
        assert payload["reference_interval_seconds"] == 240
        output = root / "results/fixture"
        (output / "demands").mkdir(parents=True)
        (output / "demands/train.json").write_text("[]\n")
        (output / "route-families.json").write_text("[]\n")
        from traffic_rl.research.artifacts import sha256_file
        manifest = {
            "protocol_version": 2, "dataset_id": "fixture",
            "generator_config_sha256": sha256_file(config_path),
            "route_families": {
                "path": "results/fixture/route-families.json",
                "sha256": sha256_file(output / "route-families.json"),
            },
            "cases": [{
                "flow_path": "results/fixture/demands/train.json",
                "flow_sha256": sha256_file(output / "demands/train.json"),
            }],
        }
        (output / "experiment-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest

    decision_path = root / "diagnostics/capacity-decision.json"
    decision = apply_capacity_decision(
        root, stage, config, decision_path=decision_path,
        new_version=True, prepare_fn=fake_prepare)

    assert len(calls) == 1
    assert calls[0][0] != root
    assert calls[0][1] is True
    assert yaml.safe_load(config.read_text())["reference_interval_seconds"] == 240
    assert (root / "results/fixture/demands/train.json").read_text() == "[]\n"
    assert json.loads(decision_path.read_text()) == decision
    assert decision["application"]["generator_config_sha256"] == \
        __import__("traffic_rl.research.artifacts", fromlist=["sha256_file"]).sha256_file(config)
    assert decision["application"]["generated_manifest_sha256"] == \
        __import__("traffic_rl.research.artifacts", fromlist=["sha256_file"]).sha256_file(
            root / "results/fixture/experiment-manifest.json")
    unsigned = dict(decision)
    unsigned.pop("decision_identity_sha256")
    assert decision["decision_identity_sha256"] == canonical_sha256(unsigned)


def test_apply_refuses_to_overwrite_an_existing_decision(tmp_path):
    root, stage, config = _stage_d_project(tmp_path, scales=(0.30,))
    decision = root / "diagnostics/capacity-decision.json"
    decision.parent.mkdir(exist_ok=True)
    decision.write_text("{}\n")
    _commit(root, "occupy decision path")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        apply_capacity_decision(
            root, stage, config, decision_path=decision, new_version=True,
            prepare_fn=lambda *args, **kwargs: {})
