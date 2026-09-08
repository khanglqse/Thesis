import json

import numpy as np
import traffic_rl.train.network_trainer as network_trainer

from traffic_rl.agents.dqn import SharedDQN
from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.train.network_trainer import (
    _default_foundation_verifier, canonical_json_sha256,
    precompute_baseline_tuning, resolve_training_config, train_network)


class FakeNetworkEnv(object):
    def __init__(self, case, horizon_seconds):
        self.case = case
        self.horizon_seconds = horizon_seconds
        self.agent_ids = ["A", "B"]
        self.num_actions = {"A": 2, "B": 2}
        self._step = 0
        self._switched = False

    def _observations(self):
        value = float(self._step) / 10.0
        features = np.full((2, 12), value, np.float32)
        features[:, 6] = [1.0, 0.0]
        return {agent: features.copy() for agent in self.agent_ids}

    def reset(self):
        self._step = 0
        self._switched = False
        return self._observations()

    def action_masks(self):
        return {agent: np.array([True, True]) for agent in self.agent_ids}

    def step(self, actions):
        assert set(actions) == set(self.agent_ids)
        self._switched = self._switched or any(value == 1 for value in actions.values())
        self._step += 1
        done = self._step >= 2
        info = {
            "step": self._step * 10,
            "total_queue": 10.0,
            "queue_integral_vehicle_seconds": 80.0 if self._switched else 100.0,
            "completion_rate": 1.0,
            "insertion_rate": 1.0,
            "phase_switches": 0,
            "total_queue": 10.0,
            "arrived": 4,
            "active_vehicles": 2,
            "max_red_seconds": 10.0,
            "intergreen_vehicle_seconds": 2.0,
        }
        rewards = {agent: -1.0 for agent in self.agent_ids}
        return self._observations(), rewards, done, info


class FakeVectorNetworkEnv(FakeNetworkEnv):
    class Encoder(object):
        feature_order = ["incoming_0", "outgoing_0", "green_0", "green_1"]

    encoder = Encoder()

    def _observations(self):
        value = float(self._step) / 10.0
        return {agent: np.full(4, value, np.float32)
                for agent in self.agent_ids}


def _manifest():
    cases = []
    for split, seed in (("train", 11), ("validation", 31)):
        for scenario in ("normal", "am_peak", "pm_peak"):
            cases.append({
                "case_id": "%s-%s" % (split, scenario), "split": split,
                "scenario": scenario, "demand_seed": seed, "sim_seed": seed + 100,
                "flow_sha256": scenario * 8,
            })
    return {
        "protocol_version": 2,
        "network": {"sha256": "network-hash", "controlled_signals": 2},
        "phase_contract": {"path": "phase-contract.json",
                           "sha256": "phase-contract-hash"},
        "generator_config_sha256": "generator-hash",
        "runtime": {"base_image": "cityflow:tag",
                    "base_image_digest": "sha256:runtime",
                    "platform": "linux/amd64",
                    "dockerfile": {"sha256": "dockerfile-hash"}},
        "preprocessing": {"count_norm": 20.0, "capacity_norm": 40.0},
        "simulation": {"action_interval": 10, "yellow_time": 3,
                       "min_green": 20, "maximum_red": 180},
        "cases": cases,
    }


def _config():
    return {
        "schema_version": 2,
        "mode": "final",
        "learning_seed": 11,
        "model": {"feature_dim": 12, "hidden": 8, "lr": 0.01,
                  "gamma": 0.99, "n_step": 1},
        "optimizer": {"batch_size": 2, "buffer_capacity": 100,
                      "train_start": 1, "target_sync": 2,
                      "grad_clip": 10.0, "huber_delta": 1.0},
        "exploration": {"epsilon_start": 0.2, "epsilon_end": 0.0,
                        "epsilon_decay_decisions": 10},
        "reward": {"queue_weight": 1.0, "downstream_block_weight": 0.2,
                   "switch_penalty": 0.05},
        "baseline": {"controller": "validation_tuned_fixed",
                     "search_green_durations": [10, 20]},
        "run": {"episodes": 3, "horizon_seconds": 20, "eval_every": 3},
    }


def _bc_config():
    config = _config()
    config["behavior_prior"] = {
        "type": "fixed_time_behavior_cloning",
        "bc_epochs": 1,
        "reference_probability_start": 0.75,
        "reference_probability_end": 0.10,
        "random_probability_start": 0.10,
        "random_probability_end": 0.02,
        "minimum_validation_reference_disagreement_rate": 0.01,
    }
    return config


def test_behavior_prior_uses_only_train_cases_and_audits_raw_validation(tmp_path):
    created = []

    def factory(case, horizon_seconds):
        created.append(case["case_id"])
        return FakeNetworkEnv(case, horizon_seconds)

    output = tmp_path / "run"
    manifest = _manifest()
    config = _bc_config()
    tuning = _precomputed_tuning(manifest, config)
    tuning_path = tmp_path / "baseline.json"
    tuning_path.write_text(json.dumps(tuning))

    summary = train_network(
        factory, manifest, config, str(output), foundation_root=str(tmp_path),
        foundation_verifier=_verified,
        baseline_tuning_artifact=str(tuning_path))

    prior = json.loads((output / "behavior-prior.json").read_text())
    assert prior["teacher"] == "validation_tuned_fixed"
    assert prior["fixed_green_duration"] == 10
    assert prior["updates"] > 0
    assert {row["case_id"] for row in prior["train_cases"]} == {
        "train-normal", "train-am_peak", "train-pm_peak"}
    assert all(not case_id.startswith("validation-")
               for case_id in prior["source_case_ids"])
    assert summary["training_policy_audit"]["eligible_decisions"] > 0
    validation = json.loads((output / "validation.json").read_text())
    rows = validation["step-3"]["rows"]
    assert all(row["policy_audit"]["evaluation_policy"] == "raw_ddqn_greedy"
               for row in rows)
    assert all(row["policy_audit"]["eligible_decisions"] > 0 for row in rows)
    contract = json.loads((output / "checkpoint/contract.json").read_text())
    assert contract["behavior_prior"]["type"] == "fixed_time_behavior_cloning"
    status = json.loads((output / "status.json").read_text())
    assert "behavior-prior.json" in status["artifact_sha256"]


def _verified(root, manifest):
    return {
        "status": "verified",
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime_digest": manifest["runtime"]["base_image_digest"],
    }


def _precomputed_tuning(manifest, config):
    validation_cases = [case for case in manifest["cases"]
                        if case["split"] == "validation"]
    binding = {
        "manifest_sha256": canonical_json_sha256(manifest),
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime": manifest["runtime"],
        "validation_case_hashes": {
            case["case_id"]: case["flow_sha256"] for case in validation_cases},
        "horizon_seconds": config["run"]["horizon_seconds"],
        "action_interval": config.get("simulation", {}).get("action_interval", 10),
        "queue_objective": {
            "schema_version": 2,
            "network_queue": "per_step_waiting",
            "entry_pending": "due_not_inserted",
            "future_departures": "unreleased_excluded",
        },
    }
    return network_trainer._tune_fixed_time(
        lambda case, horizon: FakeNetworkEnv(case, horizon), validation_cases,
        config["run"]["horizon_seconds"], config, binding)


def test_default_foundation_verifier_loads_from_requested_root(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "verify_haichau_foundation.py").write_text(
        "def verify_foundation(root, manifest):\n"
        "    return {'status': 'verified', 'root': str(root), "
        "'marker': manifest['marker']}\n")

    evidence = _default_foundation_verifier(
        str(tmp_path), {"marker": "root-bound"})

    assert evidence == {
        "status": "verified", "root": str(tmp_path), "marker": "root-bound"}


def test_training_visits_all_regimes_and_saves_resolved_contract(tmp_path):
    created = []

    def factory(case, horizon_seconds):
        env = FakeNetworkEnv(case, horizon_seconds)
        created.append(env)
        return env

    output = tmp_path / "run"
    manifest = _manifest()
    summary = train_network(factory, manifest, _config(), str(output),
                            foundation_root=str(tmp_path),
                            foundation_verifier=_verified)

    assert set(summary["episode_regimes"]) == {"normal", "am_peak", "pm_peak"}
    assert summary["episode_agent_counts"] == [2, 2, 2]
    contract = json.loads((output / "checkpoint" / "contract.json").read_text())
    assert contract["controller_family"] == "neighbor_phase_ddqn"
    assert contract["hidden_size"] == 8
    assert contract["normalization"] == {
        "capacity_norm": 40.0,
        "count_norm": 20.0,
    }
    assert contract["action_contract"] == {
        "mask_type": "boolean_selectable_green_rows",
        "padding_actions_selectable": False,
        "type": "phase_rows",
        "version": 1,
    }
    assert contract["network_compatibility"] == {
        "generator_config_sha256": "generator-hash",
        "manifest_sha256": canonical_json_sha256(manifest),
        "network_sha256": manifest["network"]["sha256"],
        "phase_contract_sha256": "phase-contract-hash",
    }
    assert contract["manifest_sha256"] == canonical_json_sha256(manifest)
    assert contract["generator_config_sha256"] == "generator-hash"
    assert contract["baseline_tuning_sha256"]
    assert contract["checkpoint_eligibility_policy"] == {
        "comparison_unit": "matched_validation_case",
        "maximum_completion_loss": 0.02,
        "maximum_insertion_loss": 0.02,
        "queue_regret_limit_per_regime": 0.0,
        "required_regimes": ["normal", "am_peak", "pm_peak"],
        "schema_version": 2,
    }
    run_manifest = json.loads((output / "run-manifest.json").read_text())
    assert run_manifest["controller_id"] == "neighbor_phase_ddqn"
    assert run_manifest["mode"] == "final"
    assert run_manifest["learning_seed"] == 11
    assert json.loads((output / "replay-coverage.json").read_text()) == {
        "am_peak": 4, "normal": 4, "pm_peak": 4}
    loaded = PhaseScoringDDQN.load_bundle(str(output / "checkpoint"), contract)
    assert loaded.feature_dim == 12

    validation_ids = {case["case_id"] for case in manifest["cases"]
                      if case["split"] == "validation"}
    for case_id in validation_ids:
        assert sum(env.case["case_id"] == case_id for env in created) >= 2

    tuning = json.loads((output / "baseline-tuning.json").read_text())
    tuning_hash = tuning.pop("tuning_sha256")
    assert tuning_hash == canonical_json_sha256(tuning)
    assert tuning["selected"]["fixed_green_duration"] == 10
    assert tuning["binding"]["validation_case_hashes"]
    default_rows = json.loads((output / "validation.json").read_text())["step-3"]["rows"]
    assert all(row["fresh_baseline"] is True for row in default_rows)
    assert all("baseline_source" not in row for row in default_rows)
    assert all(row["candidate_insertion"] == 1.0 for row in default_rows)
    assert all(row["baseline_insertion"] == 1.0 for row in default_rows)
    selection = json.loads((output / "selection.json").read_text())
    assert selection["score"]["insertion_evidence_complete"] is True
    assert selection["eligibility_policy"] == contract[
        "checkpoint_eligibility_policy"]
    assert summary["selected_validation_score"] == selection["score"]
    assert summary["checkpoint_eligibility_policy"] == selection[
        "eligibility_policy"]
    episode = json.loads((output / "train-log.json").read_text())[0]
    for field in ("demand_seed", "sim_seed", "flow_sha256",
                  "queue_integral_vehicle_seconds", "total_queue", "arrived",
                  "active_vehicles", "completion_rate", "max_red_seconds",
                  "intergreen_vehicle_seconds", "wall_time_seconds"):
        assert field in episode
    status = json.loads((output / "status.json").read_text())
    assert status["status"] in ("complete", "ineligible")
    assert status["artifact_sha256"]
    assert summary["updates"] > 0


def test_precomputed_baseline_reuses_tuning_rows_and_hash_binds_provenance(tmp_path):
    manifest = _manifest()
    config = _config()
    cache_path = tmp_path / "precomputed-baseline.json"
    cache_path.write_text(json.dumps(_precomputed_tuning(manifest, config)))
    created = []

    def factory(case, horizon_seconds):
        env = FakeNetworkEnv(case, horizon_seconds)
        created.append(env)
        return env

    output = tmp_path / "cached-run"
    summary = train_network(
        factory, manifest, config, str(output), foundation_root=str(tmp_path),
        foundation_verifier=_verified, baseline_tuning_artifact=str(cache_path))

    validation_cases = [case for case in manifest["cases"]
                        if case["split"] == "validation"]
    assert sum(env.case["split"] == "validation" for env in created) == \
        len(validation_cases) + 1
    rows = json.loads((output / "validation.json").read_text())["step-3"]["rows"]
    assert all(row["fresh_baseline"] is False for row in rows)
    assert all(row["baseline_source"] == "precomputed_tuning" for row in rows)
    assert summary["baseline_tuning_wall_time_seconds"] == 0.0

    provenance = json.loads(
        (output / "baseline-tuning-provenance.json").read_text())
    status = json.loads((output / "status.json").read_text())
    run_manifest = json.loads((output / "run-manifest.json").read_text())
    assert provenance["copied_artifact_sha256"] == \
        status["artifact_sha256"]["baseline-tuning.json"]
    assert run_manifest["baseline_tuning"]["provenance_sha256"] == \
        status["artifact_sha256"]["baseline-tuning-provenance.json"]


def test_precomputed_baseline_rejects_horizon_drift_before_writing_run(tmp_path):
    manifest = _manifest()
    config = _config()
    tuning = _precomputed_tuning(manifest, config)
    tuning["binding"]["horizon_seconds"] = 10
    tuning["tuning_sha256"] = canonical_json_sha256(
        dict((key, value) for key, value in tuning.items()
             if key != "tuning_sha256"))
    cache_path = tmp_path / "wrong-horizon.json"
    cache_path.write_text(json.dumps(tuning))
    output = tmp_path / "rejected-cache"

    with np.testing.assert_raises_regex(ValueError, "horizon"):
        train_network(
            lambda case, horizon: FakeNetworkEnv(case, horizon), manifest, config,
            str(output), foundation_root=str(tmp_path), foundation_verifier=_verified,
            baseline_tuning_artifact=str(cache_path))

    assert not output.exists()


def test_precomputed_baseline_without_insertion_rate_is_rejected(tmp_path):
    manifest = _manifest()
    config = _config()
    tuning = _precomputed_tuning(manifest, config)
    for candidate in tuning["candidates"]:
        for row in candidate["rows"]:
            row.pop("insertion_rate")
    tuning["tuning_sha256"] = canonical_json_sha256(
        dict((key, value) for key, value in tuning.items()
             if key != "tuning_sha256"))
    cache_path = tmp_path / "old-baseline.json"
    cache_path.write_text(json.dumps(tuning))
    output = tmp_path / "rejected-cache"

    with np.testing.assert_raises_regex(ValueError, "insertion"):
        train_network(
            lambda case, horizon: FakeNetworkEnv(case, horizon), manifest, config,
            str(output), foundation_root=str(tmp_path), foundation_verifier=_verified,
            baseline_tuning_artifact=str(cache_path))

    assert not output.exists()


def test_precompute_baseline_tuning_writes_reusable_artifact_without_training(tmp_path):
    manifest = _manifest()
    config = _config()
    artifact = tmp_path / "cache" / "baseline-tuning.json"

    tuning = precompute_baseline_tuning(
        lambda case, horizon: FakeNetworkEnv(case, horizon), manifest, config,
        str(artifact), foundation_root=str(tmp_path), foundation_verifier=_verified)

    assert artifact.is_file()
    assert json.loads(artifact.read_text()) == tuning
    assert tuning["binding"]["horizon_seconds"] == 20
    assert tuning["binding"]["validation_case_hashes"] == {
        "validation-normal": "normal" * 8,
        "validation-am_peak": "am_peak" * 8,
        "validation-pm_peak": "pm_peak" * 8,
    }


def test_legacy_vector_family_trains_and_saves_distinct_bundle(tmp_path):
    output = tmp_path / "legacy-run"
    config = _config()
    summary = train_network(
        lambda case, horizon: FakeVectorNetworkEnv(case, horizon),
        _manifest(), config, str(output), foundation_root=str(tmp_path),
        foundation_verifier=_verified,
        controller_family="shared_ddqn_legacy")

    contract = json.loads((output / "checkpoint/contract.json").read_text())
    assert contract["controller_family"] == "shared_ddqn_legacy"
    assert contract["feature_order"] == FakeVectorNetworkEnv.Encoder.feature_order
    assert contract["action_contract"] == {
        "type": "fixed_vector", "version": 1,
        "mask_type": "boolean_phase_index",
        "padding_actions_selectable": False,
        "n_actions": 2,
    }
    loaded = SharedDQN.load_bundle(str(output / "checkpoint"), contract)
    assert loaded.obs_dim == 4 and loaded.n_actions == 2
    run_manifest = json.loads((output / "run-manifest.json").read_text())
    assert run_manifest["controller_id"] == "shared_ddqn_legacy"
    assert set(summary["episode_regimes"]) == {"normal", "am_peak", "pm_peak"}


def test_trainer_never_opens_test_split(tmp_path):
    manifest = _manifest()
    manifest["cases"].append({"case_id": "locked-test", "split": "test",
                              "scenario": "normal"})
    opened = []

    def factory(case, horizon_seconds):
        opened.append(case["case_id"])
        return FakeNetworkEnv(case, horizon_seconds)

    train_network(factory, manifest, _config(), str(tmp_path / "run"),
                  foundation_root=str(tmp_path), foundation_verifier=_verified)

    assert "locked-test" not in opened


def test_tier_resolution_binds_mode_and_required_learning_seed():
    config = _config()
    config.pop("run")
    config.pop("learning_seed")
    config["tiers"] = {
        "smoke": {"episodes": 3, "horizon_seconds": 120, "eval_every": 3}}

    resolved = resolve_training_config(config, "smoke", learning_seed=17)

    assert resolved["mode"] == "smoke"
    assert resolved["learning_seed"] == 17
    assert resolved["run"] == config["tiers"]["smoke"]


def test_training_fails_closed_before_artifacts_when_foundation_rejects(tmp_path):
    output = tmp_path / "rejected"

    def reject(root, manifest):
        raise ValueError("route-family leakage")

    with np.testing.assert_raises_regex(ValueError, "route-family leakage"):
        train_network(lambda case, horizon: FakeNetworkEnv(case, horizon),
                      _manifest(), _config(), str(output),
                      foundation_root=str(tmp_path), foundation_verifier=reject)

    assert not output.exists()


def test_required_optimizer_update_failure_is_persisted(tmp_path):
    config = _config()
    config["run"]["train_start"] = 1000
    config["run"]["require_optimizer_updates"] = True
    output = tmp_path / "no-update"

    with np.testing.assert_raises_regex(ValueError, "optimizer update"):
        train_network(lambda case, horizon: FakeNetworkEnv(case, horizon),
                      _manifest(), config, str(output),
                      foundation_root=str(tmp_path),
                      foundation_verifier=_verified)

    status = json.loads((output / "status.json").read_text())
    assert status["status"] == "failed"


def test_incomplete_rollout_fails_run_status(tmp_path):
    class EarlyEnv(FakeNetworkEnv):
        def step(self, actions):
            observations, rewards, _, info = super(EarlyEnv, self).step(actions)
            return observations, rewards, True, info

    output = tmp_path / "partial-horizon"
    with np.testing.assert_raises_regex(ValueError, "horizon"):
        train_network(lambda case, horizon: EarlyEnv(case, horizon),
                      _manifest(), _config(), str(output),
                      foundation_root=str(tmp_path),
                      foundation_verifier=_verified)

    assert json.loads((output / "status.json").read_text())["status"] == "failed"


def test_total_wall_time_includes_baseline_tuning(monkeypatch, tmp_path):
    clock = [0.0]
    original_tune = network_trainer._tune_fixed_time

    def measured_tune(*args, **kwargs):
        result = original_tune(*args, **kwargs)
        clock[0] += 50.0
        return result

    def measured_verifier(root, manifest):
        clock[0] += 10.0
        return _verified(root, manifest)

    monkeypatch.setattr(network_trainer.time, "time", lambda: clock[0])
    monkeypatch.setattr(network_trainer, "_tune_fixed_time", measured_tune)

    summary = train_network(
        lambda case, horizon: FakeNetworkEnv(case, horizon),
        _manifest(), _config(), str(tmp_path / "timed"),
        foundation_root=str(tmp_path), foundation_verifier=measured_verifier)

    assert summary["foundation_verification_wall_time_seconds"] == 10.0
    assert summary["baseline_tuning_wall_time_seconds"] == 50.0
    assert summary["wall_time_seconds"] >= 60.0
    assert summary["measured_scope"] == (
        "foundation_verification_through_artifact_verification")
