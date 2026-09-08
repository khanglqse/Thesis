import json

import numpy as np

from traffic_rl.agents.phase_ddqn import PhaseScoringDDQN
from traffic_rl.train.network_trainer import (
    canonical_json_sha256, resolve_training_config, train_network)


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
            "phase_switches": 0,
            "total_queue": 10.0,
            "arrived": 4,
            "active_vehicles": 2,
            "max_red_seconds": 10.0,
            "intergreen_vehicle_seconds": 2.0,
        }
        rewards = {agent: -1.0 for agent in self.agent_ids}
        return self._observations(), rewards, done, info


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


def _verified(root, manifest):
    return {
        "status": "verified",
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime_digest": manifest["runtime"]["base_image_digest"],
    }


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
    assert contract["count_norm"] == 20.0
    assert contract["network_sha256"] == manifest["network"]["sha256"]
    assert contract["manifest_sha256"] == canonical_json_sha256(manifest)
    assert contract["generator_config_sha256"] == "generator-hash"
    assert contract["baseline_tuning_sha256"]
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
