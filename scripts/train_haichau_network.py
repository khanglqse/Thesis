#!/usr/bin/env python3
"""Train the phase-scoring DDQN on the versioned Hai Chau case manifest."""
import argparse
import json
import os
from pathlib import Path
import resource
import time

import yaml

from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.sim.encoder import ObservationEncoder
from traffic_rl.sim.phase_encoder import PhaseFeatureEncoder
from traffic_rl.train.network_trainer import resolve_training_config, train_network


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
            switch_penalty=float(reward["switch_penalty"]))

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
    args = parser.parse_args(argv)

    os.chdir(str(ROOT))
    manifest = json.loads((ROOT / args.manifest).read_text())
    training_config = yaml.safe_load((ROOT / args.config).read_text())
    resolved = resolve_training_config(
        training_config, args.mode, args.learning_seed)
    resolved["simulation"] = manifest["simulation"]
    output_dir = (Path(args.output) if args.output else
                  ROOT / "results" / "haichau_network_v2" / "training" /
                  (("%s-seed%d" if args.controller_family == "neighbor_phase_ddqn"
                    else "legacy-%s-seed%d") % (args.mode, args.learning_seed)))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    env_factory = _make_env_factory(
        manifest, resolved, output_dir, args.controller_family)
    summary = train_network(
        env_factory, manifest, resolved, str(output_dir), foundation_root=str(ROOT),
        run_started_at=command_start, controller_family=args.controller_family)

    if args.mode == "pilot":
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        profile = _pilot_profile(
            summary, args.learning_seed, peak_rss,
            str(output_dir / "summary.json"))
        _write_json(ROOT / "results" / "haichau_network_v2" / "profiling" /
                    (("pilot-seed%d.json" if args.controller_family
                      == "neighbor_phase_ddqn" else "legacy-pilot-seed%d.json")
                     % args.learning_seed), profile)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
