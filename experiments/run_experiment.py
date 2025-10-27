"""
Simple script to run traffic control experiments.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from experiment import ExperimentRunner

if __name__ == "__main__":
    print("Starting Traffic Control Experiment")
    print("="*60)
    print("\nThis experiment will compare:")
    print("  1. Fixed-Time controller (baseline)")
    print("  2. Actuated controller")
    print("  3. Adaptive controller")
    print("  4. Random controller")
    print("  5. DQN agent (Reinforcement Learning)")
    print("\nUsing mock environment (no SUMO installation required)")
    print("="*60)
    
    # Create experiment runner
    runner = ExperimentRunner(use_sumo=False, config_type="one_intersection")
    
    # Run experiments
    runner.run_all_experiments(train_dqn=True)
    
    # Save results
    results_file = runner.save_results()
    
    # Generate plots
    print("\n" + "="*60)
    print("Generating visualizations...")
    print("="*60)
    runner.plot_comparison()
    runner.plot_detailed_metrics()
    
    # Print summary table
    print("\n" + "="*60)
    print("EXPERIMENT RESULTS SUMMARY")
    print("="*60)
    print(f"\n{'Method':<15} {'Avg Wait (s)':<15} {'Avg Queue':<15} {'Reward':<15}")
    print("-" * 60)
    
    # Sort by waiting time (best first)
    sorted_results = sorted(runner.results.items(), key=lambda x: x[1]['avg_waiting_time'])
    
    for method, data in sorted_results:
        print(f"{method:<15} {data['avg_waiting_time']:>12.2f}  {data['avg_halting']:>12.2f}  {data['cumulative_reward']:>12.2f}")
    
    print("\n" + "="*60)
    print("Legend:")
    print("  - Avg Wait: Average waiting time per vehicle (lower is better)")
    print("  - Avg Queue: Average vehicles in queue (lower is better)")
    print("  - Reward: Cumulative reward during evaluation (higher is better)")
    print("\nResults and plots saved in 'results/' directory")
    print("="*60)

