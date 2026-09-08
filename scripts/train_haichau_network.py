#!/usr/bin/env python3
"""Train the phase-scoring DDQN on the versioned Hai Chau case manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import time

import yaml

from traffic_rl.eval.network_metrics import NetworkMetricsObserver
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder
from traffic_rl.train.network_trainer import (
    precompute_baseline_tuning, resolve_training_config, train_network)


ROOT = Path(__file__).resolve().parent.parent


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _make_env_factory(manifest, resolved, output_dir, controller_family):
    roadnet_path = ROOT / manifest["network"]["path"]
    phase_contract = manifest.get("phase_contract")
    if not isinstance(phase_contract, dict):
        raise ValueError("manifest phase_contract artifact is required")
    roadnet = RoadNet.load(
        str(roadnet_path), str(ROOT / phase_contract["path"]),
        require_phase_contract=True,
        expected_phase_contract_sha256=phase_contract["sha256"])
    preprocessing = manifest["preprocessing"]
    simulation = manifest["simulation"]
    if controller_family == "neighbor_phase_ddqn":
        encoder = PhaseFeatureEncoder(
            roadnet, preprocessing["count_norm"], preprocessing["capacity_norm"])
    else:
        encoder = ObservationEncoder(
            roadnet, count_norm=preprocessing["count_norm"], state_mode="basic")
    lane_to_node = {}
    for node_id in roadnet.signalized_ids():
        for lane_id in roadnet.incoming_lanes(node_id):
            lane_to_node[lane_id] = node_id
    runtime_dir = output_dir / "runtime-configs"

    def factory(case, horizon_seconds):
        run_config = {
            "interval": 1.0,
            "seed": int(case["sim_seed"]),
            "dir": str(ROOT) + "/",
            "roadnetFile": manifest["network"]["path"],
            "flowFile": case["flow_path"],
            "rlTrafficLight": True,
            "laneChange": False,
            "saveReplay": False,
        }
        config_path = runtime_dir / (case["case_id"] + ".json")
        _write_json(config_path, run_config)
        reward = resolved["reward"]
        observer = NetworkMetricsObserver(
            int(case["scheduled_vehicles"]), step_seconds=1.0,
            lane_to_node=lane_to_node,
            spillback_thresholds=dict(
                (lane_id, preprocessing["capacity_norm"])
                for lane_id in lane_to_node))
        return MultiAgentTrafficEnv(
            roadnet, CityFlowEngine(str(config_path)),
            action_interval=int(simulation["action_interval"]),
            max_steps=int(horizon_seconds),
            yellow_time=int(simulation["yellow_time"]),
            min_green=int(simulation["min_green"]),
            maximum_red=int(simulation["maximum_red"]),
            encoder=encoder, reward_type="queue_norm",
            state_mode="basic",
            queue_weight=float(reward["queue_weight"]),
            downstream_block_weight=float(reward["downstream_block_weight"]),
            switch_penalty=float(reward["switch_penalty"]),
            network_metric_observer=observer,
            scheduled_vehicles=int(case["scheduled_vehicles"]))

    return factory


def _pilot_profile(summary, learning_seed, peak_rss_kb, source_summary):
    return {
        "learning_seed": learning_seed,
        "simulated_seconds_per_second": summary["simulated_seconds_per_second"],
        "updates_per_second": summary["updates_per_second"],
        "peak_rss_kb": peak_rss_kb,
        "validation_wall_time_seconds": summary["validation_wall_time_seconds"],
        "baseline_tuning_wall_time_seconds": summary[
            "baseline_tuning_wall_time_seconds"],
        "measured_end_to_end_wall_time_seconds": summary["wall_time_seconds"],
        "projected_five_seed_campaign_seconds": (
            5.0 * summary["wall_time_seconds"]),
        "source_summary": source_summary,
    }


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pilot_profile_path(output_dir, controller_family, learning_seed):
    """Keep canonical names while separating explicitly named pilot runs."""
    output_dir = Path(output_dir).resolve()
    default_name = ("pilot-seed%d" if controller_family == "neighbor_phase_ddqn"
                    else "legacy-pilot-seed%d") % learning_seed
    name = default_name if output_dir.name == default_name else output_dir.name
    if name in ("", ".", ".."):
        raise ValueError("pilot output directory must have a usable name")
    return ROOT / "results" / "haichau_network_v2" / "profiling" / (name + ".json")


def _profile_source_artifacts(sources, root):
    root = Path(root).resolve()
    bound = {}
    for label in ("summary", "resolved_config", "run_manifest", "baseline_tuning"):
        path = Path(sources.get(label, ""))
        if not path.is_file():
            raise ValueError("pilot profile source artifact is missing: %s" % label)
        resolved = path.resolve()
        try:
            display_path = str(resolved.relative_to(root))
        except ValueError:
            display_path = str(resolved)
        bound[label] = {
            "path": display_path,
            "sha256": _sha256_file(resolved),
        }
    return bound


def _write_pilot_profile(path, profile, sources, root=ROOT):
    """Write a profile only when an existing artifact has the same sources."""
    source_artifacts = _profile_source_artifacts(sources, root)
    path = Path(path)
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise ValueError("cannot safely overwrite invalid pilot profile: %s" % exc)
        if existing.get("source_artifacts") != source_artifacts:
            raise ValueError(
                "refusing to overwrite pilot profile with different source artifact identity")
    value = dict(profile)
    value["schema_version"] = 2
    value["source_artifacts"] = source_artifacts
    _write_json(path, value)


def main(argv=None):
    command_start = time.time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True,
                        choices=("smoke", "pilot", "final"))
    parser.add_argument("--learning-seed", required=True, type=int)
    parser.add_argument("--controller-family", default="neighbor_phase_ddqn",
                        choices=("neighbor_phase_ddqn", "shared_ddqn_legacy"))
    parser.add_argument("--manifest",
                        default="results/haichau_network_v2/experiment-manifest.json")
    parser.add_argument("--config", default="configs/haichau_training_v2.yaml")
    parser.add_argument("--output")
    parser.add_argument(
        "--baseline-tuning-artifact",
        help=("precomputed validation-only fixed-time tuning JSON; it must "
              "match this manifest, validation cases, horizon, and search space"))
    parser.add_argument(
        "--precompute-baseline-tuning", metavar="PATH",
        help=("write one immutable validation-only fixed-time tuning JSON and "
              "exit before learning episodes"))
    args = parser.parse_args(argv)

    os.chdir(str(ROOT))
    manifest = json.loads((ROOT / args.manifest).read_text())
    training_config = yaml.safe_load((ROOT / args.config).read_text())
    resolved = resolve_training_config(
        training_config, args.mode, args.learning_seed)
    resolved["simulation"] = manifest["simulation"]
    if args.baseline_tuning_artifact and args.precompute_baseline_tuning:
        parser.error("cache input and --precompute-baseline-tuning cannot be combined")
    if args.precompute_baseline_tuning:
        artifact_path = Path(args.precompute_baseline_tuning)
        if not artifact_path.is_absolute():
            artifact_path = ROOT / artifact_path
        output_dir = artifact_path.parent / ".baseline-tuning-runtime"
    else:
        artifact_path = None
        output_dir = (Path(args.output) if args.output else
                      ROOT / "results" / "haichau_network_v2" / "training" /
                      (("%s-seed%d" if args.controller_family == "neighbor_phase_ddqn"
                        else "legacy-%s-seed%d") % (args.mode, args.learning_seed)))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    env_factory = _make_env_factory(
        manifest, resolved, output_dir, args.controller_family)
    if artifact_path is not None:
        tuning = precompute_baseline_tuning(
            env_factory, manifest, resolved, str(artifact_path),
            foundation_root=str(ROOT))
        print(json.dumps({
            "artifact_path": str(artifact_path),
            "tuning_sha256": tuning["tuning_sha256"],
        }, indent=2, sort_keys=True))
        return 0
    summary = train_network(
        env_factory, manifest, resolved, str(output_dir), foundation_root=str(ROOT),
        run_started_at=command_start, controller_family=args.controller_family,
        baseline_tuning_artifact=args.baseline_tuning_artifact)

    if args.mode == "pilot":
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        profile = _pilot_profile(
            summary, args.learning_seed, peak_rss,
            str(output_dir / "summary.json"))
        _write_pilot_profile(
            _pilot_profile_path(
                output_dir, args.controller_family, args.learning_seed),
            profile,
            sources={
                "summary": output_dir / "summary.json",
                "resolved_config": output_dir / "resolved-config.json",
                "run_manifest": output_dir / "run-manifest.json",
                "baseline_tuning": output_dir / "baseline-tuning.json",
            })
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
