import hashlib
import json

import pytest

import traffic_rl.eval.robustness_appendix as robustness_appendix
from traffic_rl.eval.robustness_appendix import (
    CONDITIONS,
    LEARNING_SEEDS,
    expand_robustness_runs,
    freeze_robustness_protocol,
    write_campaign_manifest,
    write_robustness_summary,
    summarize_robustness,
    validate_robustness_directory,
)


@pytest.fixture(autouse=True)
def _stub_completed_primary_release(monkeypatch):
    """The appendix tests isolate appendix behavior from the primary verifier."""
    def validate(root, path, primary=None):
        campaign = path.parent / "campaign-manifest.json"
        summary = path.parent / "summary.json"
        return {
            "campaign_manifest_path": campaign.resolve(),
            "campaign_manifest_sha256": _sha(campaign),
            "summary_path": summary.resolve(),
            "summary_sha256": _sha(summary),
        }
    monkeypatch.setattr(
        robustness_appendix, "validate_primary_v3_reference",
        validate)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return _sha(path)


def _fixture(tmp_path):
    root = tmp_path
    roadnet = {"intersections": [], "roads": [
        {"id": "r0", "startIntersection": "V0", "endIntersection": "N00",
         "lanes": [{"maxSpeed": 11.0}, {"maxSpeed": 11.0}]},
        {"id": "r1", "startIntersection": "N00", "endIntersection": "V1",
         "lanes": [{"maxSpeed": 11.0}]},
    ]}
    roadnet["intersections"] = [
        {"id": "V0", "virtual": True, "roads": ["r0"]},
        {"id": "V1", "virtual": True, "roads": ["r1"]},
    ] + [
        {"id": "N%02d" % i, "virtual": False, "roads": [], "roadLinks": [],
         "trafficLight": {"roadLinkIndices": [], "lightphases": [
             {"time": 3, "availableRoadLinks": []},
             {"time": 25, "availableRoadLinks": []}]}}
        for i in range(53)
    ]
    roadnet_path = root / "network/roadnet.json"
    roadnet_sha = _write_json(roadnet_path, roadnet)
    phase_path = root / "network/phase.json"
    phase_sha = _write_json(phase_path, {
        "roadnet_sha256": roadnet_sha,
        "controlled_signal_ids": ["N%02d" % i for i in range(53)],
    })
    cases = []
    for i in range(15):
        flow_path = root / ("flows/test-%02d.json" % i)
        flow = [{
            "vehicle": {"length": 5.0, "width": 2.0, "maxPosAcc": 2.0,
                        "maxNegAcc": 4.5, "usualPosAcc": 2.0,
                        "usualNegAcc": 4.5, "minGap": 2.5,
                        "maxSpeed": 11.0, "headwayTime": 1.5},
            "route": ["r0", "r1"], "interval": 6.0,
            "startTime": 0, "endTime": 3599,
        }]
        flow_sha = _write_json(flow_path, flow)
        cases.append({
            "case_id": "test_%02d" % i,
            "split": "test",
            "regime": ("normal", "am_peak", "pm_peak")[i // 5],
            "demand_seed": 100 + i,
            "simulator_seed": 200 + i,
            "scheduled_vehicles": 600,
            "horizon_steps": 3600,
            "demand_path": str(flow_path.relative_to(root)),
            "demand_sha256": flow_sha,
        })
    case_manifest = root / "final/case-manifest.json"
    case_sha = _write_json(case_manifest, {
        "protocol_version": 3,
        "default_horizon_steps": 3600,
        "cases": cases,
    })
    checkpoints = []
    for seed in LEARNING_SEEDS:
        weights = root / ("training/seed-%d/checkpoint/weights.npz" % seed)
        weights.parent.mkdir(parents=True, exist_ok=True)
        weights.write_bytes(("checkpoint-%d" % seed).encode())
        checkpoints.append({
            "controller_id": "neighbor_phase_ddqn",
            "learning_seed": seed,
            "path": str(weights.relative_to(root)),
            "sha256": _sha(weights),
            "validation_eligible": True,
            "checkpoint_contract": {"controller_family": "neighbor_phase_ddqn",
                                    "training_step": 12},
        })
    protocol = {
        "protocol_version": 3,
        "code_commit": "1" * 40,
        "network_sha256": roadnet_sha,
        "viewer_network_sha256": "2" * 64,
        "phase_contract_sha256": phase_sha,
        "runtime_digest": "sha256:" + "3" * 64,
        "runtime_image": "example/cityflow@sha256:" + "3" * 64,
        "runtime_image_id": "sha256:" + "4" * 64,
        "runtime_dockerfile_path": "docker/haichau-evaluation.Dockerfile",
        "runtime_dockerfile_sha256": "5" * 64,
        "network_path": str(roadnet_path.relative_to(root)),
        "phase_contract_path": str(phase_path.relative_to(root)),
        "case_manifest_path": str(case_manifest.relative_to(root)),
        "case_manifest_sha256": case_sha,
        "agent_ids": ["N%02d" % i for i in range(53)],
        "controlled_signals": 53,
        "primary_learned_controller": "neighbor_phase_ddqn",
        "confirmatory_learning_seeds": list(LEARNING_SEEDS),
        "acceptance_rules": {"required_learning_seeds": list(LEARNING_SEEDS)},
        "resolved_config": {
            "network_path": str(roadnet_path.relative_to(root)),
            "phase_contract_path": str(phase_path.relative_to(root)),
            "phase_contract_sha256": phase_sha,
            "step_seconds": 1.0,
            "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
            "simulation": {"action_interval": 10, "yellow_time": 3,
                           "min_green": 20, "maximum_red": 180},
            "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.1,
                       "switch_penalty": 0.05},
        },
        "normalization": {"count_norm": 20.0, "capacity_norm": 40.0},
        "controller_configs": {
            "tuned_fixed": {"green_duration": 25},
            "max_pressure": {"controller_version": 2},
            "neighbor_phase_ddqn": {"controller_version": 3},
        },
        "checkpoints": checkpoints,
    }
    protocol_path = root / "final/frozen-protocol.json"
    _write_json(protocol_path, protocol)
    _write_json(root / "final/campaign-manifest.json", {
        "campaign_version": 2, "runs": []})
    _write_json(root / "final/summary.json", {
        "study_scope": {"evidence_namespace": "haichau_network_v2"}})
    config = {
        "schema_version": 1,
        "study_role": "exploratory_appendix",
        "conditions": {
            "demand_plus20": {"kind": "demand_scale", "multiplier": 1.20},
            "sensor_gaussian": {"kind": "sensor_gaussian", "sigma": 0.15},
            "sensor_dropout": {"kind": "sensor_dropout", "probability": 0.10},
            "incident_lane_reduction50": {
                "kind": "lane_restriction_incident",
                "restricted_lane_fraction": 0.50,
                "start_step": 1200, "end_step": 2400,
                "target_rule": "topology_max_incoming_lanes_then_ids",
            },
        },
        "controllers": ["tuned_fixed", "max_pressure", "neighbor_phase_ddqn"],
        "bootstrap": {"samples": 10000, "seed": 20260908},
    }
    config_path = root / "configs/robustness.yaml"
    _write_json(config_path, config)
    return root, protocol_path, config_path


def test_freeze_binds_primary_artifacts_and_writes_only_robustness_namespace(tmp_path):
    root, primary, config = _fixture(tmp_path)
    output = root / "results/haichau_network_v2/robustness"

    frozen = freeze_robustness_protocol(
        root, primary, config, output, robustness_code_commit="6" * 40)

    assert frozen["study_role"] == "exploratory_appendix"
    assert frozen["primary_protocol_sha256"] == _sha(primary)
    assert frozen["primary_results_reference"]["usage"] == "reference_only"
    assert frozen["primary_results_reference"]["campaign_manifest_sha256"] == _sha(
        root / "final/campaign-manifest.json")
    assert frozen["case_manifest_sha256"] == _sha(root / "final/case-manifest.json")
    assert frozen["network_sha256"] == _sha(root / "network/roadnet.json")
    assert frozen["phase_contract_sha256"] == _sha(root / "network/phase.json")
    assert len(frozen["checkpoint_bindings"]) == 5
    assert (output / "frozen-robustness-protocol.json").is_file()
    assert not (root / "results/haichau_network_v2/final/robustness").exists()

    with pytest.raises(ValueError, match="already exists"):
        freeze_robustness_protocol(
            root, primary, config, output, robustness_code_commit="6" * 40)


def test_freeze_validates_primary_before_reading_or_materializing_test_flows(
        tmp_path, monkeypatch):
    root, primary, config = _fixture(tmp_path)
    flow = root / "flows/test-00.json"
    flow.unlink()
    monkeypatch.setattr(
        robustness_appendix, "validate_primary_v3_reference",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("primary checkpoint eligible:false")))
    monkeypatch.setattr(
        robustness_appendix, "_case_bindings",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("test flow was opened before primary validation")))

    with pytest.raises(ValueError, match="eligible:false"):
        freeze_robustness_protocol(
            root, primary, config,
            root / "results/haichau_network_v2/robustness",
            robustness_code_commit="6" * 40)

    assert not (root / "results/haichau_network_v2/robustness").exists()


@pytest.mark.parametrize("mutation,error", [
    (("confirmatory_learning_seeds", [11, 12, 13, 14, 15]), "12--16"),
    (("acceptance_rules", {"required_learning_seeds": [12]}), "12--16"),
])
def test_freeze_rejects_seed11_override_or_primary_seed_mismatch(
        tmp_path, mutation, error):
    root, primary, config = _fixture(tmp_path)
    document = json.loads(primary.read_text())
    document[mutation[0]] = mutation[1]
    primary.write_text(json.dumps(document))

    with pytest.raises(ValueError, match=error):
        freeze_robustness_protocol(
            root, primary, config,
            root / "results/haichau_network_v2/robustness",
            robustness_code_commit="6" * 40)


def test_freeze_rejects_final_namespace_and_does_not_mutate_primary(tmp_path):
    root, primary, config = _fixture(tmp_path)
    before = {path: path.read_bytes() for path in (root / "final").rglob("*")
              if path.is_file()}

    with pytest.raises(ValueError, match="separate robustness namespace"):
        freeze_robustness_protocol(
            root, primary, config,
            root / "results/haichau_network_v2/final/robustness",
            robustness_code_commit="6" * 40)

    after = {path: path.read_bytes() for path in (root / "final").rglob("*")
             if path.is_file()}
    assert after == before


def test_runtime_directory_must_be_the_exact_project_robustness_namespace(tmp_path):
    expected = tmp_path / "results/haichau_network_v2/robustness"
    assert validate_robustness_directory(tmp_path, expected) == expected.resolve()
    with pytest.raises(ValueError, match="separate robustness namespace"):
        validate_robustness_directory(
            tmp_path, tmp_path / "results/haichau_network_v2/final")


def test_expansion_is_exactly_420_fresh_episodes_and_never_reuses_primary_runs(tmp_path):
    root, primary, config = _fixture(tmp_path)
    output = root / "results/haichau_network_v2/robustness"
    frozen = freeze_robustness_protocol(
        root, primary, config, output, robustness_code_commit="6" * 40)

    runs = expand_robustness_runs(root, frozen)

    assert len(runs) == 420
    assert len({run["run_id"] for run in runs}) == 420
    assert set(run["condition_id"] for run in runs) == set(CONDITIONS)
    assert set(run["case_id"] for run in runs) == {
        "test_%02d" % i for i in range(15)}
    assert all(run["fresh_evaluation"] is True for run in runs)
    assert all(run["study_role"] == "exploratory_appendix" for run in runs)
    learned = [r for r in runs if r["controller_id"] == "neighbor_phase_ddqn"]
    assert set(r["learning_seed"] for r in learned) == set(LEARNING_SEEDS)
    assert all(r["learning_seed"] is None for r in runs if r not in learned)
    assert not any("primary/final/runs" in r["run_id"] for r in runs)
    for condition in ("sensor_gaussian", "sensor_dropout"):
        by_case = {}
        for run in runs:
            if run["condition_id"] == condition:
                by_case.setdefault(run["case_id"], set()).add(
                    run["perturbation_seed"])
        assert all(len(seeds) == 1 for seeds in by_case.values())


def test_expansion_revalidates_completed_primary_release(tmp_path, monkeypatch):
    root, primary, config = _fixture(tmp_path)
    output = root / "results/haichau_network_v2/robustness"
    frozen = freeze_robustness_protocol(
        root, primary, config, output, robustness_code_commit="6" * 40)
    monkeypatch.setattr(
        robustness_appendix, "validate_primary_v3_reference",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("primary campaign is incomplete")))

    with pytest.raises(ValueError, match="incomplete"):
        expand_robustness_runs(root, frozen)


@pytest.mark.parametrize("mutation,error", [
    ("condition", "condition"),
    ("case", "cases"),
    ("demand", "demand_plus20"),
    ("acceptance", "training/selection/acceptance"),
])
def test_expansion_rejects_mutated_protocol_even_when_artifact_hashes_still_exist(
        tmp_path, mutation, error):
    root, primary, config = _fixture(tmp_path)
    output = root / "results/haichau_network_v2/robustness"
    frozen = freeze_robustness_protocol(
        root, primary, config, output, robustness_code_commit="6" * 40)
    if mutation == "condition":
        frozen["conditions"]["sensor_gaussian"]["sigma"] = 0.9
    elif mutation == "case":
        frozen["cases"][0]["simulator_seed"] = 999
    elif mutation == "demand":
        first = sorted(frozen["demand_plus20_bindings"])[0]
        frozen["demand_plus20_bindings"][first]["scheduled_vehicles"] += 1
    else:
        frozen["acceptance_rules"] = {"accepted": True}

    with pytest.raises(ValueError, match=error):
        expand_robustness_runs(root, frozen)


def test_freeze_rejects_case_checkpoint_and_config_hash_drift(tmp_path):
    for target, expected in (
            ("case", "case manifest"), ("checkpoint", "checkpoint"),
            ("config", "config")):
        root, primary, config = _fixture(tmp_path / target)
        protocol = json.loads(primary.read_text())
        if target == "case":
            (root / protocol["case_manifest_path"]).write_text("{}")
        elif target == "checkpoint":
            (root / protocol["checkpoints"][0]["path"]).write_bytes(b"drift")
        else:
            document = json.loads(config.read_text())
            document["training"] = {"episodes": 1}
            config.write_text(json.dumps(document))
        with pytest.raises(ValueError, match=expected):
            freeze_robustness_protocol(
                root, primary, config,
                root / "results/haichau_network_v2/robustness",
                robustness_code_commit="6" * 40)


@pytest.mark.parametrize("mutation,error", [
    ("signals", "53 unique"),
    ("route", "topologically continuous"),
    ("phase", "invalid road link"),
])
def test_freeze_fails_closed_on_signal_route_and_phase_invalidity(
        tmp_path, mutation, error):
    root, primary, config = _fixture(tmp_path)
    protocol = json.loads(primary.read_text())
    if mutation == "signals":
        protocol["agent_ids"] = protocol["agent_ids"][:-1]
        primary.write_text(json.dumps(protocol))
    elif mutation == "route":
        roadnet = json.loads((root / protocol["network_path"]).read_text())
        roadnet["roads"][1]["startIntersection"] = "elsewhere"
        (root / protocol["network_path"]).write_text(json.dumps(roadnet))
        protocol["network_sha256"] = _sha(root / protocol["network_path"])
        primary.write_text(json.dumps(protocol))
    else:
        roadnet = json.loads((root / protocol["network_path"]).read_text())
        roadnet["intersections"][2]["trafficLight"]["lightphases"][1][
            "availableRoadLinks"] = [0]
        (root / protocol["network_path"]).write_text(json.dumps(roadnet))
        protocol["network_sha256"] = _sha(root / protocol["network_path"])
        primary.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match=error):
        freeze_robustness_protocol(
            root, primary, config,
            root / "results/haichau_network_v2/robustness",
            robustness_code_commit="6" * 40)


def test_freeze_rejects_case_id_that_could_escape_immutable_input_namespace(tmp_path):
    root, primary, config = _fixture(tmp_path)
    protocol = json.loads(primary.read_text())
    case_path = root / protocol["case_manifest_path"]
    cases = json.loads(case_path.read_text())
    cases["cases"][0]["case_id"] = "../../final"
    case_path.write_text(json.dumps(cases))
    protocol["case_manifest_sha256"] = _sha(case_path)
    primary.write_text(json.dumps(protocol))

    with pytest.raises(ValueError, match="case ID is unsafe"):
        freeze_robustness_protocol(
            root, primary, config,
            root / "results/haichau_network_v2/robustness",
            robustness_code_commit="6" * 40)


def test_summary_is_hierarchical_seed_paired_and_has_no_pass_fail_label():
    rows = []
    for condition in CONDITIONS:
        for case in range(15):
            base = 1000.0 + case
            for controller in ("tuned_fixed", "max_pressure"):
                rows.append({"condition_id": condition, "case_id": "c%d" % case,
                             "regime": ("normal", "am_peak", "pm_peak")[case // 5],
                             "controller_id": controller, "learning_seed": None,
                             "queue_integral_vehicle_seconds": base + (
                                 5 if controller == "max_pressure" else 0),
                             "completion_rate": 0.9})
            for seed in LEARNING_SEEDS:
                rows.append({"condition_id": condition, "case_id": "c%d" % case,
                             "regime": ("normal", "am_peak", "pm_peak")[case // 5],
                             "controller_id": "neighbor_phase_ddqn",
                             "learning_seed": seed,
                             "queue_integral_vehicle_seconds": base + seed - 14,
                             "completion_rate": 0.89})

    result = summarize_robustness(rows)

    assert result["study_role"] == "exploratory_appendix"
    assert result["inference"]["bootstrap_samples"] == 10000
    assert result["inference"]["bootstrap_seed"] == 20260908
    assert result["inference"]["learning_statistical_unit"] == (
        "learning_seed_after_matched_case_mean")
    assert "accepted" not in json.dumps(result).lower()
    assert "pass" not in json.dumps(result).lower()
    cell = result["conditions"]["sensor_gaussian"]["neighbor_phase_ddqn"]
    assert cell["queue"]["n_independent"] == 5
    assert cell["completion_rate"]["n_independent"] == 5
    assert cell["queue_difference_vs_tuned_fixed"]["n_independent"] == 5
    assert cell["queue_difference_vs_tuned_fixed"]["mean"] == pytest.approx(0.0)
    assert set(cell["by_regime"]) == {"normal", "am_peak", "pm_peak"}
    assert cell["by_regime"]["normal"][
        "queue_difference_vs_tuned_fixed"]["n_independent"] == 5


def test_campaign_and_summary_writes_are_immutable_and_never_enter_final(tmp_path):
    root, primary, config = _fixture(tmp_path)
    output = root / "results/haichau_network_v2/robustness"
    frozen = freeze_robustness_protocol(
        root, primary, config, output, robustness_code_commit="6" * 40)
    runs = expand_robustness_runs(root, frozen)

    campaign = write_campaign_manifest(output, runs)
    assert campaign["evidence_namespace"] == "haichau_network_v2"
    assert campaign["study_role"] == "exploratory_appendix"
    assert len(campaign["runs"]) == 420
    with pytest.raises(ValueError, match="refusing to replace"):
        write_campaign_manifest(output, runs)
    summary = {"study_role": "exploratory_appendix", "conditions": {}}
    write_robustness_summary(output, summary)
    with pytest.raises(ValueError, match="refusing to replace"):
        write_robustness_summary(output, summary)
    assert not (root / "results/haichau_network_v2/final/summary.json").exists()
