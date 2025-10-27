#!/usr/bin/env python3
"""
Configurable Traffic Light Control Experiments.

This script runs experiments using configuration files, supporting both
mock and real SUMO environments with easy switching.
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment.env_factory import create_traffic_environment, get_available_scenarios
from agents.dqn_agent import DQNAgent, create_dqn_agent
from experiments.run_mock_experiments import MockExperimentRunner


def run_scenario_experiment(scenario_config: Dict[str, Any], agent_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run experiment for a single scenario.

    Args:
        scenario_config: Configuration for the scenario
        agent_config: Configuration for the agent

    Returns:
        Experiment results
    """
    print(f"\n{'='*50}")
    print(f"🚦 Running {scenario_config['name']} scenario")
    print(f"{'='*50}")

    # Create environment
    env = create_traffic_environment(scenario_config)

    # Create agent
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n if hasattr(env.action_space, 'n') else env.action_space.nvec[0]

    agent = create_dqn_agent(
        state_dim=state_dim,
        action_dim=action_dim,
        config=agent_config
    )

    # Create experiment runner
    runner_config = {
        'experiment_name': scenario_config['name'],
        'results_dir': './results/configured_experiments/',
        'num_episodes': scenario_config.get('num_episodes', 50),
        'num_eval_episodes': scenario_config.get('num_eval_episodes', 10),
        'max_steps': scenario_config.get('max_steps', 3600),
        'dqn_config': agent_config
    }

    runner = MockExperimentRunner(runner_config)

    # Train agent
    training_results = runner._train_agent(env, agent, scenario_config['name'])

    # Evaluate agent
    eval_results = runner._evaluate_agent(env, agent, scenario_config['name'])

    # Combine results
    results = {**training_results, **eval_results}
    results['scenario_config'] = scenario_config

    env.close()

    return results


def run_comparison_study(config_file: str) -> Dict[str, Any]:
    """
    Run comparison study between multiple scenarios.

    Args:
        config_file: Path to configuration file

    Returns:
        Complete study results
    """
    # Load configuration
    with open(config_file, 'r') as f:
        config = json.load(f)

    print(f"🚀 Starting configured experiment: {config['experiment_name']}")

    all_results = {
        'experiment_name': config['experiment_name'],
        'timestamp': config.get('timestamp', 'N/A'),
        'config': config,
        'scenarios': {}
    }

    # Run each scenario
    for scenario_config in config['scenarios']:
        scenario_results = run_scenario_experiment(scenario_config, config['agent_config'])
        all_results['scenarios'][scenario_config['name']] = scenario_results

    # Generate comparison
    if len(all_results['scenarios']) > 1:
        all_results['comparison'] = generate_comparison(all_results['scenarios'])

    # Save results
    save_configured_results(all_results, config)

    return all_results


def generate_comparison(scenario_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comparison between scenarios."""
    scenarios = list(scenario_results.keys())

    if len(scenarios) < 2:
        return {}

    # Get metrics for comparison
    rewards = [scenario_results[s]['eval_avg_reward'] for s in scenarios]
    waiting_times = [scenario_results[s]['eval_avg_waiting_time'] for s in scenarios]
    throughput = [scenario_results[s]['eval_avg_throughput'] for s in scenarios]

    return {
        'scenarios_compared': scenarios,
        'reward_range': {'min': min(rewards), 'max': max(rewards)},
        'waiting_time_range': {'min': min(waiting_times), 'max': max(waiting_times)},
        'throughput_range': {'min': min(throughput), 'max': max(throughput)},
        'best_reward_scenario': scenarios[rewards.index(max(rewards))],
        'best_throughput_scenario': scenarios[throughput.index(max(throughput))],
        'worst_waiting_scenario': scenarios[waiting_times.index(max(waiting_times))]
    }


def save_configured_results(results: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Save results to files."""
    results_dir = config['output_config']['results_dir']
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(os.path.join(results_dir, 'figures'), exist_ok=True)

    # Save JSON results
    json_path = os.path.join(results_dir, f"{config['experiment_name']}_results.json")
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {json_path}")

    # Save summary CSV
    csv_path = os.path.join(results_dir, f"{config['experiment_name']}_summary.csv")
    save_summary_csv(results, csv_path)
    print(f"📊 Summary saved to: {csv_path}")


def save_summary_csv(results: Dict[str, Any], csv_path: str) -> None:
    """Save summary to CSV."""
    import csv

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['Scenario', 'Eval_Avg_Reward', 'Eval_Avg_Waiting_Time',
                        'Eval_Avg_Throughput', 'Best_Metric'])

        # Scenario results
        for scenario_name, scenario_data in results['scenarios'].items():
            best_metric = 'reward'  # Default
            if scenario_name == results['comparison'].get('best_throughput_scenario'):
                best_metric = 'throughput'
            elif scenario_name == results['comparison'].get('worst_waiting_scenario'):
                best_metric = 'waiting_time'

            writer.writerow([
                scenario_name,
                scenario_data['eval_avg_reward'],
                scenario_data['eval_avg_waiting_time'],
                scenario_data['eval_avg_throughput'],
                best_metric
            ])


def list_available_scenarios():
    """List all available scenarios."""
    scenarios = get_available_scenarios()

    print("\n📋 Available Scenarios:")
    print("-" * 50)
    for name, info in scenarios.items():
        print(f"🔹 {name}")
        print(f"   Description: {info['description']}")
        print(f"   State Dim: {info['state_dim']}")
        print(f"   Action Dim: {info['action_dim']}")
        print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run configured traffic control experiments')
    parser.add_argument('--config', default='experiments/configs/mock_study_config.json',
                       help='Path to configuration file')
    parser.add_argument('--list-scenarios', action='store_true',
                       help='List available scenarios')
    parser.add_argument('--quick-test', action='store_true',
                       help='Run quick test with minimal episodes')
    parser.add_argument('--scenario', help='Run specific scenario only')

    args = parser.parse_args()

    if args.list_scenarios:
        list_available_scenarios()
        return

    # Load and modify config for quick test
    with open(args.config, 'r') as f:
        config = json.load(f)

    if args.quick_test:
        config['training_config']['num_episodes'] = 5
        config['training_config']['num_eval_episodes'] = 3
        config['training_config']['max_steps_per_episode'] = 100
        config['experiment_name'] = config['experiment_name'] + '_quick_test'
        print("⚡ Quick test mode enabled")

    # Run specific scenario or all scenarios
    if args.scenario:
        # Run single scenario
        scenario_config = next(s for s in config['scenarios'] if s['name'] == args.scenario)
        results = run_scenario_experiment(scenario_config, config['agent_config'])
        print(f"\n✅ {args.scenario} experiment completed!")
    else:
        # Run comparison study
        results = run_comparison_study(args.config)

        # Print final summary
        print(f"\n{'='*60}")
        print("🎉 CONFIGURED EXPERIMENT COMPLETED!")
        print(f"{'='*60}")

        if 'comparison' in results:
            comp = results['comparison']
            print("📊 COMPARISON SUMMARY:")
            print(f"  Best Reward: {comp['best_reward_scenario']}")
            print(f"  Best Throughput: {comp['best_throughput_scenario']}")
            print(f"  Worst Waiting Time: {comp['worst_waiting_scenario']}")
            print(f"  Reward Range: {comp['reward_range']['min']:.0f} to {comp['reward_range']['max']:.0f}")
            print(f"  Throughput Range: {comp['throughput_range']['min']:.0f} to {comp['throughput_range']['max']:.0f}")


if __name__ == '__main__':
    main()
