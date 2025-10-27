#!/usr/bin/env python3
"""
Results Display and Analysis Tool.

This script provides beautiful visualization and analysis of traffic control
experiment results, supporting both mock and real SUMO experiments.
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import Dict, List, Any
import argparse


def load_results(results_file: str) -> Dict[str, Any]:
    """Load experiment results from JSON file."""
    with open(results_file, 'r') as f:
        return json.load(f)


def display_experiment_summary(results: Dict[str, Any]) -> None:
    """Display comprehensive experiment summary."""
    print("\n" + "="*80)
    print("🚦 TRAFFIC LIGHT CONTROL EXPERIMENT RESULTS")
    print("="*80)

    print(f"\n📋 Experiment: {results['experiment_name']}")
    print(f"🕒 Timestamp: {results['timestamp']}")
    print(f"🔧 Configuration: {len(results['config'])} parameters")

    print("\n📊 SCENARIO RESULTS:")
    print("-" * 50)

    for scenario_name, scenario_data in results.get('scenarios', results).items():
        if scenario_name == 'comparison':
            continue

        print(f"\n🔹 {scenario_name.upper()}")
        reward = scenario_data['eval_avg_reward']
        reward_std = scenario_data.get('eval_std_reward', 0)
        waiting = scenario_data['eval_avg_waiting_time']
        waiting_std = scenario_data.get('eval_std_waiting_time', 0)
        throughput = scenario_data['eval_avg_throughput']
        throughput_std = scenario_data.get('eval_std_throughput', 0)

        print(f"   Reward:        {reward:,.0f".0f" {reward_std:,.0f".0f")
        print(f"   Waiting Time:  {waiting:,.0f".0f" {waiting_std:,.0f".0f")
        print(f"   Throughput:    {throughput:.1f".1f"icles {throughput_std:.1".1f")

    if 'comparison' in results:
        comp = results['comparison']
        print("
🎯 COMPARISON ANALYSIS:"        print("-" * 50)
        print(f"   Best Reward:       {comp['best_reward_scenario']}")
        print(f"   Best Throughput:   {comp['best_throughput_scenario']}")
        print(f"   Worst Waiting:     {comp['worst_waiting_scenario']}")
        print(f"   Reward Range:      {comp['reward_range']['min']".0f"} to {comp['reward_range']['max']".0f"}")
        print(f"   Throughput Range:  {comp['throughput_range']['min']".1f"} to {comp['throughput_range']['max']".1f"}")


def plot_training_curves(results: Dict[str, Any], save_path: str = None) -> None:
    """Plot training curves for all scenarios."""
    plt.figure(figsize=(15, 10))

    scenarios = [name for name in results.get('scenarios', {}).keys() if name != 'comparison']

    # Plot 1: Training Rewards
    plt.subplot(2, 3, 1)
    for scenario in scenarios:
        rewards = results['scenarios'][scenario]['training_rewards']
        plt.plot(rewards, label=scenario.replace('_', ' ').title(), alpha=0.8)
    plt.title('Training Rewards')
    plt.xlabel('Episode')
    plt.ylabel('Reward')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 2: Training Waiting Times
    plt.subplot(2, 3, 2)
    for scenario in scenarios:
        waiting_times = results['scenarios'][scenario]['training_waiting_times']
        plt.plot(waiting_times, label=scenario.replace('_', ' ').title(), alpha=0.8)
    plt.title('Training Waiting Times')
    plt.xlabel('Episode')
    plt.ylabel('Waiting Time (s)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 3: Training Throughput
    plt.subplot(2, 3, 3)
    for scenario in scenarios:
        throughput = results['scenarios'][scenario]['training_throughput']
        plt.plot(throughput, label=scenario.replace('_', ' ').title(), alpha=0.8)
    plt.title('Training Throughput')
    plt.xlabel('Episode')
    plt.ylabel('Vehicles')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 4: Final Performance Comparison
    plt.subplot(2, 3, 4)
    scenario_names = [s.replace('_', ' ').title() for s in scenarios]
    rewards = [results['scenarios'][s]['eval_avg_reward'] for s in scenarios]
    errors = [results['scenarios'][s].get('eval_std_reward', 0) for s in scenarios]

    bars = plt.bar(scenario_names, rewards, yerr=errors, capsize=5,
                   color=['skyblue', 'lightcoral'])
    plt.title('Average Reward by Scenario')
    plt.ylabel('Reward')
    plt.xticks(rotation=45)

    for bar, reward in zip(bars, rewards):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{reward",.0f"}', ha='center', va='bottom')

    # Plot 5: Waiting Time Comparison
    plt.subplot(2, 3, 5)
    waiting_times = [results['scenarios'][s]['eval_avg_waiting_time'] for s in scenarios]
    errors = [results['scenarios'][s].get('eval_std_waiting_time', 0) for s in scenarios]

    bars = plt.bar(scenario_names, waiting_times, yerr=errors, capsize=5,
                   color=['lightgreen', 'gold'])
    plt.title('Average Waiting Time by Scenario')
    plt.ylabel('Waiting Time (s)')
    plt.xticks(rotation=45)

    for bar, waiting in zip(bars, waiting_times):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{waiting",.0f"}', ha='center', va='bottom')

    # Plot 6: Throughput Comparison
    plt.subplot(2, 3, 6)
    throughput = [results['scenarios'][s]['eval_avg_throughput'] for s in scenarios]
    errors = [results['scenarios'][s].get('eval_std_throughput', 0) for s in scenarios]

    bars = plt.bar(scenario_names, throughput, yerr=errors, capsize=5,
                   color=['orange', 'purple'])
    plt.title('Average Throughput by Scenario')
    plt.ylabel('Vehicles')
    plt.xticks(rotation=45)

    for bar, tp in zip(bars, throughput):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{tp".1f"}', ha='center', va='bottom')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"📊 Plots saved to: {save_path}")
    else:
        plt.show()

    plt.close()


def generate_performance_report(results: Dict[str, Any], output_file: str = None) -> str:
    """Generate comprehensive performance report."""
    report = []
    report.append("# 🚦 Traffic Light Control Performance Report")
    report.append(f"**Generated:** {results['timestamp']}")
    report.append(f"**Experiment:** {results['experiment_name']}")
    report.append("")

    # Configuration summary
    report.append("## ⚙️ Configuration")
    config = results['config']
    report.append(f"- **Training Episodes:** {config.get('num_episodes', 'N/A')}")
    report.append(f"- **Evaluation Episodes:** {config.get('num_eval_episodes', 'N/A')}")
    report.append(f"- **Max Steps:** {config.get('max_steps', 'N/A')}")
    report.append(f"- **Traffic Demand:** {config.get('traffic_demand', 'N/A')}")
    report.append("")

    # Results table
    report.append("## 📊 Performance Results")
    report.append("| Scenario | Reward | Waiting Time | Throughput |")
    report.append("|----------|--------|--------------|------------|")

    for scenario_name, scenario_data in results.get('scenarios', results).items():
        if scenario_name == 'comparison':
            continue

        reward = scenario_data['eval_avg_reward']
        waiting = scenario_data['eval_avg_waiting_time']
        throughput = scenario_data['eval_avg_throughput']

        report.append(f"| {scenario_name} | {reward",.0f"} | {waiting",.0f"}s | {throughput".1f"} |")

    report.append("")

    # Comparison analysis
    if 'comparison' in results:
        comp = results['comparison']
        report.append("## 🎯 Comparison Analysis")
        report.append(f"- **Best Reward:** {comp['best_reward_scenario']}")
        report.append(f"- **Best Throughput:** {comp['best_throughput_scenario']}")
        report.append(f"- **Worst Waiting Time:** {comp['worst_waiting_scenario']}")
        report.append("")

    # Insights
    report.append("## 💡 Key Insights")
    scenarios = list(results.get('scenarios', results).keys())

    if len(scenarios) > 1:
        rewards = [results['scenarios'][s]['eval_avg_reward'] for s in scenarios if s != 'comparison']
        throughputs = [results['scenarios'][s]['eval_avg_throughput'] for s in scenarios if s != 'comparison']
        waiting_times = [results['scenarios'][s]['eval_avg_waiting_time'] for s in scenarios if s != 'comparison']

        if len(rewards) > 1:
            reward_range = max(rewards) - min(rewards)
            report.append(f"- **Reward Variability:** {reward_range:,.0f} across scenarios")

        if len(throughputs) > 1:
            throughput_range = max(throughputs) - min(throughputs)
            report.append(f"- **Throughput Range:** {throughput_range:.1f} vehicles difference")

        if len(waiting_times) > 1:
            waiting_range = max(waiting_times) - min(waiting_times)
            report.append(f"- **Waiting Time Range:** {waiting_range:,.0f}s difference")

    report.append("")

    # Recommendations
    report.append("## 🎯 Recommendations")
    if 'comparison' in results:
        comp = results['comparison']

        if comp['best_reward_scenario'] == comp['best_throughput_scenario']:
            report.append(f"- **{comp['best_reward_scenario']}** shows best overall performance")
        else:
            report.append(f"- **{comp['best_reward_scenario']}** for minimal waiting times")
            report.append(f"- **{comp['best_throughput_scenario']}** for maximum traffic flow")

        if comp['worst_waiting_scenario'] != comp['best_reward_scenario']:
            report.append(f"- **{comp['worst_waiting_scenario']}** needs optimization for waiting times")

    full_report = "\n".join(report)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(full_report)
        print(f"📄 Report saved to: {output_file}")

    return full_report


def analyze_results(results_file: str, generate_plots: bool = True, output_dir: str = None) -> None:
    """Complete analysis of experiment results."""
    print(f"🔍 Analyzing results from: {results_file}")

    # Load results
    results = load_results(results_file)

    # Display summary
    display_experiment_summary(results)

    # Generate plots
    if generate_plots:
        figures_dir = output_dir or './results/figures'
        os.makedirs(figures_dir, exist_ok=True)

        plot_file = os.path.join(figures_dir, f"{results['experiment_name']}_analysis.png")
        plot_training_curves(results, plot_file)

    # Generate report
    if output_dir:
        report_file = os.path.join(output_dir, f"{results['experiment_name']}_report.md")
        generate_performance_report(results, report_file)

    print("
✅ Analysis completed!"    print(f"📊 Plots: {figures_dir}")
    print(f"📄 Report: {output_dir}")


def compare_experiments(results_files: List[str], output_file: str = None) -> None:
    """Compare multiple experiments."""
    print("🔄 Comparing multiple experiments...")

    all_results = []
    for file in results_files:
        results = load_results(file)
        all_results.append({
            'experiment': results['experiment_name'],
            'timestamp': results['timestamp'],
            'single_reward': results['single_intersection']['eval_avg_reward'],
            'multi_reward': results['multi_intersection']['eval_avg_reward'],
            'single_throughput': results['single_intersection']['eval_avg_throughput'],
            'multi_throughput': results['multi_intersection']['eval_avg_throughput'],
            'single_waiting': results['single_intersection']['eval_avg_waiting_time'],
            'multi_waiting': results['multi_intersection']['eval_avg_waiting_time']
        })

    # Create comparison plot
    plt.figure(figsize=(12, 8))

    experiments = [r['experiment'] for r in all_results]
    single_rewards = [r['single_reward'] for r in all_results]
    multi_rewards = [r['multi_reward'] for r in all_results]

    x = np.arange(len(experiments))
    width = 0.35

    plt.bar(x - width/2, single_rewards, width, label='Single Intersection', alpha=0.8)
    plt.bar(x + width/2, multi_rewards, width, label='Multi Intersection', alpha=0.8)

    plt.xlabel('Experiment')
    plt.ylabel('Average Reward')
    plt.title('Reward Comparison Across Experiments')
    plt.xticks(x, experiments, rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Add value labels
    for i, (single, multi) in enumerate(zip(single_rewards, multi_rewards)):
        plt.text(i - width/2, single, f'{single",.0f"}', ha='center', va='bottom')
        plt.text(i + width/2, multi, f'{multi",.0f"}', ha='center', va='bottom')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Comparison plot saved to: {output_file}")

    plt.show()
    plt.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Display and analyze traffic control experiment results')
    parser.add_argument('--results', required=True,
                       help='Path to results JSON file')
    parser.add_argument('--output-dir', default='./results/analysis',
                       help='Output directory for plots and reports')
    parser.add_argument('--no-plots', action='store_true',
                       help='Skip plot generation')
    parser.add_argument('--compare', nargs='+',
                       help='Compare multiple result files')

    args = parser.parse_args()

    if args.compare:
        # Compare multiple experiments
        compare_experiments(args.compare, os.path.join(args.output_dir, 'comparison.png'))
    else:
        # Analyze single experiment
        analyze_results(args.results, not args.no_plots, args.output_dir)


if __name__ == '__main__':
    main()
