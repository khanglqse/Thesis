"""
Run experiments for three intersections using mock environment.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from experiment import ExperimentRunner


def print_results_summary(runner):
    """Print formatted results summary."""
    print("\n" + "="*70)
    print("EXPERIMENT RESULTS SUMMARY")
    print("="*70)
    print(f"\n{'Method':<15} {'Avg Wait (s)':<15} {'Avg Queue':<15} {'Reward':<15}")
    print("-" * 70)
    
    # Sort by waiting time (best first)
    sorted_results = sorted(runner.results.items(), key=lambda x: x[1]['avg_waiting_time'])
    
    for method, data in sorted_results:
        print(f"{method:<15} {data['avg_waiting_time']:>12.2f}  {data['avg_halting']:>12.2f}  {data['cumulative_reward']:>12.2f}")
    
    print("\n" + "="*70)
    print("Legend:")
    print("  - Avg Wait: Average waiting time per vehicle (lower is better)")
    print("  - Avg Queue: Average vehicles in queue (lower is better)")
    print("  - Reward: Cumulative reward during evaluation (higher is better)")
    print(f"\nResults saved in: results/")
    print("="*70)


if __name__ == "__main__":
    print("="*70)
    print("Traffic Control Experiment: Three Intersections (Mock)")
    print("="*70)
    print("\nControllers:")
    print("  1. Fixed-Time controller")
    print("  2. Actuated controller")
    print("  3. Adaptive controller")
    print("  4. Random controller")
    print("  5. DQN agent (Reinforcement Learning)")
    print("\nEnvironment: Mock (no SUMO required)")
    print("="*70)
    
    # Create experiment runner
    runner = ExperimentRunner(use_sumo=False, config_type="three_intersections")
    
    # Run experiments
    runner.run_all_experiments(train_dqn=True)
    
    # Save results
    results_file = runner.save_results()
    
    # Generate plots
    print("\n" + "="*70)
    print("Generating visualizations...")
    print("="*70)
    runner.plot_comparison()
    runner.plot_detailed_metrics()
    
    # Print summary
    print_results_summary(runner)
