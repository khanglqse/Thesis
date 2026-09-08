import copy
import hashlib
import json

import pytest

from traffic_rl.eval.pressure_validation import evaluate_pressure_validation
from traffic_rl.train.network_trainer import canonical_json_sha256, _tuning_binding
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from tests.conftest import FakeEngine
from tests.sim.test_multi_agent_env import _net


def _inputs(tmp_path):
    roadnet = _net(tmp_path)
    artifact = tmp_path / "input.json"
    artifact.write_text("{}")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    flow = tmp_path / "validation-flow.json"
    flow.write_text("[]")
    flow_digest = hashlib.sha256(flow.read_bytes()).hexdigest()
    cases = [{"case_id": "%s-%s" % (scenario, seed), "scenario": scenario,
              "split": "validation", "demand_seed": seed, "sim_seed": seed + 100,
              "flow_path": "validation-flow.json", "flow_sha256": flow_digest,
              "scheduled_vehicles": 2}
             for scenario in ("normal", "am_peak", "pm_peak") for seed in (31, 32)]
    manifest = {
        "protocol_version": 2, "network": {"path": "input.json", "sha256": digest,
                                             "controlled_signals": 1},
        "phase_contract": {"path": "input.json", "sha256": digest},
        "generator_config_path": "input.json", "generator_config_sha256": digest,
        "runtime": {"base_image_digest": "sha256:runtime"},
        "simulation": {"action_interval": 10, "min_green": 20, "maximum_red": 180},
        "preprocessing": {"capacity_norm": 40},
        "cases": cases + [{"case_id": "never-open-test", "split": "test",
                           "flow_path": "missing-secret-test.json"}],
    }
    config = {"simulation": manifest["simulation"],
              "run": {"horizon_seconds": 3600},
              "baseline": {"controller": "validation_tuned_fixed",
                           "search_green_durations": [30]}}
    rows = [{"case_id": c["case_id"], "scenario": c["scenario"],
             "queue_integral_vehicle_seconds": 10000., "completion_rate": 0.5,
             "insertion_rate": 1.0}
            for c in cases]
    tuning = {"schema_version": 1, "method": "validation_grid_search",
              "binding": _tuning_binding(manifest, cases, 3600, config),
              "search_space": {"fixed_green_duration": [30]},
              "selected": {"fixed_green_duration": 30},
              "candidates": [{"fixed_green_duration": 30, "rows": rows,
                              "mean_queue_integral_vehicle_seconds": 10000.}]}
    tuning["tuning_sha256"] = canonical_json_sha256(tuning)
    opened = []

    class Engine(FakeEngine):
        def vehicle_ids(self):
            return ["first"] if 1 <= self._t < 10 else []

        def due_vehicle_ids(self):
            return ["first", "pending"] if self._t >= 1 else []

    def factory(case, horizon):
        opened.append((case["case_id"], horizon))
        return MultiAgentTrafficEnv(
            roadnet, Engine(waiting_counts={"rin_0": 2, "rin_1": 1}),
            action_interval=10, min_green=20, maximum_red=180,
            max_steps=horizon, scheduled_vehicles=case["scheduled_vehicles"])

    return manifest, config, tuning, factory, opened


def test_diagnostic_runs_only_six_validation_cases_and_binds_accounting(tmp_path):
    manifest, config, tuning, factory, opened = _inputs(tmp_path)
    output = tmp_path / "diagnostic"
    result = evaluate_pressure_validation(factory, manifest, config, tuning,
                                          output, tmp_path)

    assert len(opened) == 12
    assert set(case for case, _ in opened) == set(tuning["binding"]["validation_case_hashes"])
    assert {horizon for _, horizon in opened} == {3600}
    assert result["status"] == "diagnostic_complete"
    assert result["eligible_for_release"] is False
    assert result["eligible_for_test_evaluation"] is False
    assert result["binding"] == tuning["binding"]
    assert result["baseline_tuning_sha256"] == tuning["tuning_sha256"]
    assert {row["controller_id"] for row in result["rows"]} == {
        "raw_max_pressure", "hysteretic_max_pressure"}
    for row in result["rows"]:
        metrics = row["metrics"]
        assert metrics["observed_steps"] == 3600
        assert metrics["network_queue_integral_vehicle_seconds"] == 10800
        assert metrics["pending_integral_vehicle_seconds"] == 3600
        assert metrics["queue_integral_vehicle_seconds"] == 14400
        assert metrics["completion_rate"] == 0.5
        assert metrics["scheduled"] == metrics["due"] == 2
        assert metrics["unreleased"] == metrics["running"] == metrics["removed"] == 0
        assert metrics["inserted"] == metrics["arrived"] == metrics["pending"] == 1
        assert metrics["max_red_seconds"] <= 180
        assert row["queue_regret"] == pytest.approx(0.44)
    stored = json.loads((output / "diagnostic.json").read_text())
    assert stored == result


@pytest.mark.parametrize("mutation", ["missing_case", "duplicate_case", "short_horizon",
                                       "stale_flow", "stale_baseline", "output_exists"])
def test_diagnostic_rejects_invalid_inputs_before_rollout(tmp_path, mutation):
    manifest, config, tuning, factory, opened = _inputs(tmp_path)
    output = tmp_path / "diagnostic"
    if mutation == "missing_case":
        manifest["cases"].pop(0)
    elif mutation == "duplicate_case":
        manifest["cases"][1] = copy.deepcopy(manifest["cases"][0])
    elif mutation == "short_horizon":
        config["run"]["horizon_seconds"] = 120
    elif mutation == "stale_flow":
        (tmp_path / "validation-flow.json").write_text("changed")
    elif mutation == "stale_baseline":
        tuning["selected"]["fixed_green_duration"] = 40
    else:
        output.mkdir()
    with pytest.raises(ValueError):
        evaluate_pressure_validation(factory, manifest, config, tuning,
                                     output, tmp_path)
    assert opened == []


def test_incomplete_rollout_keeps_diagnostic_partial(tmp_path):
    manifest, config, tuning, factory, opened = _inputs(tmp_path)
    output = tmp_path / "diagnostic"

    def short_factory(case, horizon):
        env = factory(case, horizon)
        env.max_steps = 20
        return env

    with pytest.raises(ValueError, match="complete 3600"):
        evaluate_pressure_validation(short_factory, manifest, config, tuning,
                                     output, tmp_path)
    stored = json.loads((output / "diagnostic.json").read_text())
    assert len(opened) == 1
    assert stored["status"] == "diagnostic_partial"
    assert stored["eligible_for_release"] is False
    assert stored["rows"] == []
