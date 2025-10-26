#!/usr/bin/env python3
"""
Script to run RL traffic control experiments.
This script runs experiments with reinforcement learning agents
and compares them with baseline methods.
"""

import os
import sys
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.run_experiment import ExperimentRunner

def main():
    """Run RL experiments."""
    print("="*60)
    print("TRAFFIC CONTROL RL EXPERIMENTS")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load configuration
    config_file = os.path.join(os.path.dirname(__file__), 'rl_config.json')
    
    if not os.path.exists(config_file):
        print(f"Error: Configuration file not found: {config_file}")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    print(f"Experiment: {config['experiment_name']}")
    print(f"Training episodes: {config['num_episodes']}")
    print(f"Evaluation episodes: {config['eval_episodes']}")
    print(f"Max steps per episode: {config['max_steps_per_episode']}")
    print(f"DQN training: {config['train_dqn']}")
    print(f"PPO training: {config['train_ppo']}")
    print()
    
    # Create experiment runner
    runner = ExperimentRunner(config)
    
    try:
        # Run experiment
        print("Starting RL experiments...")
        start_time = time.time()
        
        results = runner.run_experiment()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print("RL EXPERIMENTS COMPLETED")
        print("="*60)
        print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"Results saved to: {config['results_dir']}")
        
        # Print summary
        print("\nPERFORMANCE SUMMARY:")
        print("-" * 50)
        for agent_name, metrics in results.items():
            if 'evaluation' in agent_name and isinstance(metrics, dict):
                agent = agent_name.replace('_evaluation', '')
                print(f"{agent:15s}: "
                      f"Reward={metrics.get('avg_reward', 0):8.2f}, "
                      f"Waiting={metrics.get('avg_waiting_time', 0):8.2f}, "
                      f"Throughput={metrics.get('avg_throughput', 0):8.2f}")
        
        # Print training progress for RL agents
        print("\nTRAINING PROGRESS:")
        print("-" * 50)
        for agent_name, metrics in results.items():
            if 'training' in agent_name and isinstance(metrics, dict):
                agent = agent_name.replace('_training', '')
                if 'rewards' in metrics and len(metrics['rewards']) > 0:
                    initial_reward = metrics['rewards'][0]
                    final_reward = metrics['rewards'][-1]
                    improvement = final_reward - initial_reward
                    print(f"{agent:15s}: "
                          f"Initial={initial_reward:8.2f}, "
                          f"Final={final_reward:8.2f}, "
                          f"Improvement={improvement:8.2f}")
        
    except Exception as e:
        print(f"Error during experiment: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
