#!/usr/bin/env python3
"""Fail-closed verification and CityFlow smoke for the Hai Chau v2 foundation."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

import yaml

from traffic_rl.network.haichau_dataset import audit_network
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.research.artifacts import validate_disjoint_splits, verify_artifact


EXPECTED_CONTROLLED_SIGNALS = 53
EXPECTED_CASES = 30
EXPECTED_SCENARIOS = {"normal", "am_peak", "pm_peak"}
EXPECTED_IMAGE_DIGEST = "sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32"
EXPECTED_PLATFORM = "linux/amd64"


def _load_verified_config(root, manifest):
    config_path = verify_artifact(
        root,
        {
            "path": manifest["generator_config_path"],
            "sha256": manifest["generator_config_sha256"],
        },
    )
    config = yaml.safe_load(config_path.read_text())
    if config.get("schema_version") != 2:
        raise ValueError("generator config schema_version must be 2")
    if config.get("dataset_id") != manifest.get("dataset_id"):
        raise ValueError("generator config dataset_id mismatch")
    return config


def _verify_network(root, manifest, config):
    network = manifest.get("network", {})
    if network.get("controlled_signals") != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("controlled signal count must be exactly 53")
    network_path = verify_artifact(root, network)
    if network.get("path") != config.get("roadnet"):
        raise ValueError("network path differs from generator config")

    provenance_record = network.get("provenance")
    if not provenance_record:
        raise ValueError("network provenance record is required")
    provenance_path = verify_artifact(root, provenance_record)
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("roadnet_expected_sha256") != network.get("sha256"):
        raise ValueError("provenance roadnet hash mismatch")
    if provenance.get("expected_controlled_signals") != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("provenance controlled signal count mismatch")

    actual = audit_network(network_path)
    if actual["controlled_signals"] != EXPECTED_CONTROLLED_SIGNALS:
        raise ValueError("controlled signal count audit mismatch")
    for field in (
        "roads",
        "intersections",
        "controlled_signals",
        "agent_ids",
        "directed_signal_edges",
        "weak_components",
        "phase_errors",
    ):
        if network.get(field) != actual[field]:
            raise ValueError("network audit field mismatch: %s" % field)
    if actual["phase_errors"]:
        raise ValueError("network phase audit failed")
    return network_path, actual


def _verify_cases(root, manifest, config):
    cases = manifest.get("cases", [])
    if len(cases) != EXPECTED_CASES:
        raise ValueError("expected exactly 30 primary cases")
    validate_disjoint_splits(cases)

    expected_min_signals = int(config["min_controlled_signals_per_route"])
    expected_route_count = int(config["route_count"])
    expected_label = config["demand_label"]
    families = defaultdict(set)
    sim_seed_splits = defaultdict(set)
    for case in cases:
        verify_artifact(
            root, {"path": case["flow_path"], "sha256": case["flow_sha256"]}
        )
        if case.get("data_source_label") != expected_label:
            raise ValueError("case data source label mismatch")
        histogram = case.get("route_signal_histogram", {})
        try:
            histogram_counts = {int(key): int(value) for key, value in histogram.items()}
        except (TypeError, ValueError):
            raise ValueError("invalid route-signal histogram")
        if (
            not histogram_counts
            or min(histogram_counts) < expected_min_signals
            or sum(histogram_counts.values()) != expected_route_count
        ):
            raise ValueError("route-signal histogram minimum or count mismatch")
        family = (case.get("split"), case.get("demand_seed"))
        families[family].add(case.get("scenario"))
        sim_seed_splits[case.get("sim_seed")].add(case.get("split"))

    if any(scenarios != EXPECTED_SCENARIOS for scenarios in families.values()):
        raise ValueError("scenario coverage must be normal, am_peak and pm_peak per seed")
    if any(len(splits) > 1 for splits in sim_seed_splits.values()):
        raise ValueError("simulation seed appears in multiple splits")

    split_counts = validate_disjoint_splits(cases)
    if split_counts != {"test": 15, "train": 9, "validation": 6}:
        raise ValueError("split case counts mismatch")
    return split_counts


def verify_foundation(root, manifest):
    """Verify the complete host-side foundation and return one summary record."""
    root = Path(root).resolve()
    if manifest.get("protocol_version") != 2:
        raise ValueError("protocol_version must be 2")
    runtime = manifest.get("runtime", {})
    if runtime.get("image_digest") != EXPECTED_IMAGE_DIGEST:
        raise ValueError("runtime digest mismatch")
    if runtime.get("platform") != EXPECTED_PLATFORM:
        raise ValueError("runtime platform mismatch")

    config = _load_verified_config(root, manifest)
    _, network_audit = _verify_network(root, manifest, config)
    split_counts = _verify_cases(root, manifest, config)
    return {
        "status": "verified",
        "protocol_version": 2,
        "controlled_signals": network_audit["controlled_signals"],
        "cases": len(manifest["cases"]),
        "split_counts": split_counts,
        "network_sha256": manifest["network"]["sha256"],
        "generator_config_sha256": manifest["generator_config_sha256"],
        "runtime_digest": runtime["image_digest"],
    }


def run_engine_smoke(root, manifest, max_steps=60):
    """Run a real 60-second Fixed-Time episode in the pinned CityFlow image."""
    from traffic_rl.agents.fixed_time import FixedTimeController
    from traffic_rl.sim.engine import CityFlowEngine
    from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv

    verify_foundation(root, manifest)
    root = Path(root).resolve()
    case = next(
        case
        for case in manifest["cases"]
        if case["split"] == "train" and case["scenario"] == "normal"
    )
    runtime_config = {
        "interval": 1.0,
        "seed": int(case["sim_seed"]),
        "dir": str(root) + "/",
        "roadnetFile": manifest["network"]["path"],
        "flowFile": case["flow_path"],
        "rlTrafficLight": True,
        "laneChange": False,
        "saveReplay": False,
    }
    config_handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="haichau-smoke-", delete=False
    )
    try:
        json.dump(runtime_config, config_handle, sort_keys=True)
        config_handle.close()
        roadnet = RoadNet.load(str(root / manifest["network"]["path"]))
        simulation = manifest["simulation"]
        env = MultiAgentTrafficEnv(
            roadnet,
            CityFlowEngine(config_handle.name),
            action_interval=int(simulation["action_interval"]),
            max_steps=int(max_steps),
            yellow_time=int(simulation["yellow_time"]),
            min_green=int(simulation["min_green"]),
            count_norm=float(manifest["preprocessing"]["count_norm"]),
        )
        controller = FixedTimeController(
            num_actions=env.num_actions,
            green_duration=30,
            action_interval=int(simulation["action_interval"]),
        )
        observations = env.reset()
        controller.reset()
        done = False
        info = {}
        while not done:
            actions = controller.act(
                {
                    "observations": observations,
                    "waiting_counts": env.current_waiting_counts(),
                    "action_masks": env.action_masks(),
                }
            )
            observations, _, done, info = env.step(actions)
        return {
            "status": "engine-smoke-passed",
            "controller": "FixedTime",
            "case_id": case["case_id"],
            "controlled_signals": len(env.agent_ids),
            "steps": info["step"],
            "vehicle_count": info["vehicle_count"],
            "average_travel_time": info["average_travel_time"],
            "queue_integral_vehicle_seconds": info[
                "queue_integral_vehicle_seconds"
            ],
        }
    finally:
        path = Path(config_handle.name)
        if path.exists():
            path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="results/haichau_network_v2/experiment-manifest.json",
    )
    parser.add_argument("--engine-smoke", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / args.manifest).read_text())
    report = (
        run_engine_smoke(root, manifest)
        if args.engine_smoke
        else verify_foundation(root, manifest)
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
