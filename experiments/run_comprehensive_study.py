#!/usr/bin/env python3
"""
Comprehensive Study Script for Master's Thesis
===============================================
This script runs complete experiments to demonstrate results before and after 
using Reinforcement Learning for traffic light control optimization.

Experiments:
1. Baseline Controllers (Fixed-Time, Actuated, Adaptive, Random)
2. DQN Agent (Deep Q-Network)
3. PPO Agent (Proximal Policy Optimization)

Results are saved for thesis presentation and analysis.
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.run_experiment import ExperimentRunner


def print_header(title: str):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_section(title: str):
    """Print formatted subsection header."""
    print("\n" + "-"*60)
    print(f"  {title}")
    print("-"*60)


class ComprehensiveStudy:
    """Main class for running comprehensive thesis experiments."""
    
    def __init__(self, results_dir: str = "./results/"):
        """
        Initialize comprehensive study.
        
        Args:
            results_dir: Directory to save results
        """
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.study_results = {
            'metadata': {
                'start_time': datetime.now().isoformat(),
                'python_version': sys.version,
                'study_type': 'comprehensive_traffic_control'
            },
            'baselines': {},
            'rl_agents': {},
            'comparison': {}
        }
    
    def run_baseline_study(self, num_episodes: int = 20, eval_episodes: int = 10):
        """
        Run baseline controller experiments (traditional methods).
        
        Args:
            num_episodes: Number of episodes (not used for baselines, but for consistency)
            eval_episodes: Number of evaluation episodes
        """
        print_header("PHASE 1: BASELINE CONTROLLERS (BEFORE RL)")
        print("Testing traditional traffic control methods:")
        print("  • Fixed-Time Controller")
        print("  • Actuated Controller")
        print("  • Adaptive Controller")
        print("  • Random Controller (worst case)")
        print()
        
        baseline_config = {
            'experiment_name': 'baseline_study',
            'num_episodes': 1,  # Baselines don't train
            'eval_episodes': eval_episodes,
            'max_steps_per_episode': 3600,
            'use_gui': False,
            'train_dqn': False,
            'train_ppo': False,
            'use_fixed_time': True,
            'use_actuated': True,
            'use_adaptive': True,
            'use_random': True,
            'results_dir': self.results_dir,
            'env_config': {
                'reward_function': 'combined',
                'max_steps': 3600,
                'step_length': 1.0
            },
            'baseline_configs': {
                'fixed_time': {'phase_duration': 30},
                'actuated': {
                    'threshold': 10.0,
                    'min_green_time': 15,
                    'max_green_time': 60,
                    'yellow_time': 3
                },
                'adaptive': {
                    'base_green_time': 20,
                    'max_green_time': 60,
                    'vehicle_threshold': 5.0,
                    'congestion_threshold': 15.0
                },
                'random': {}
            }
        }
        
        try:
            start_time = time.time()
            runner = ExperimentRunner(baseline_config)
            results = runner.run_experiment()
            duration = time.time() - start_time
            
            # Extract baseline results
            for key, value in results.items():
                if 'evaluation' in key and isinstance(value, dict):
                    agent_name = key.replace('_evaluation', '')
                    self.study_results['baselines'][agent_name] = value
                    self.study_results['baselines'][agent_name]['training_time'] = 0  # No training
            
            print(f"\n✓ Baseline study completed in {duration:.2f} seconds")
            print_section("Baseline Results Summary")
            self._print_results_table(self.study_results['baselines'])
            
            return results
            
        except Exception as e:
            print(f"✗ Error in baseline study: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_dqn_study(self, num_episodes: int = 50, eval_episodes: int = 10):
        """
        Run DQN agent experiments (Deep Q-Network).
        
        Args:
            num_episodes: Number of training episodes
            eval_episodes: Number of evaluation episodes
        """
        print_header("PHASE 2: DQN AGENT (DEEP REINFORCEMENT LEARNING)")
        print("Training Deep Q-Network for traffic control optimization")
        print(f"  • Training Episodes: {num_episodes}")
        print(f"  • Evaluation Episodes: {eval_episodes}")
        print(f"  • Network Architecture: [256, 128, 64] hidden layers")
        print(f"  • Learning Rate: 5e-4")
        print(f"  • Epsilon-Greedy Exploration: 1.0 → 0.01")
        print()
        
        dqn_config = {
            'experiment_name': 'dqn_study',
            'num_episodes': num_episodes,
            'eval_episodes': eval_episodes,
            'max_steps_per_episode': 3600,
            'use_gui': False,
            'train_dqn': True,
            'train_ppo': False,
            'use_fixed_time': False,
            'use_actuated': False,
            'use_adaptive': False,
            'use_random': False,
            'save_models': True,
            'results_dir': self.results_dir,
            'env_config': {
                'reward_function': 'combined',
                'max_steps': 3600,
                'step_length': 1.0
            },
            'dqn_config': {
                'learning_rate': 5e-4,
                'gamma': 0.99,
                'epsilon_start': 1.0,
                'epsilon_end': 0.01,
                'epsilon_decay': 0.995,
                'target_update_freq': 1000,
                'batch_size': 128,
                'buffer_capacity': 20000,
                'device': 'cpu'
            }
        }
        
        try:
            start_time = time.time()
            runner = ExperimentRunner(dqn_config)
            results = runner.run_experiment()
            duration = time.time() - start_time
            
            # Extract DQN results
            if 'dqn_evaluation' in results:
                self.study_results['rl_agents']['dqn'] = results['dqn_evaluation']
                self.study_results['rl_agents']['dqn']['training_time'] = duration
                self.study_results['rl_agents']['dqn']['training_episodes'] = num_episodes
                
                # Also save training curve data
                if 'dqn_training' in results:
                    self.study_results['rl_agents']['dqn']['training_data'] = results['dqn_training']
            
            print(f"\n✓ DQN study completed in {duration:.2f} seconds ({duration/60:.2f} minutes)")
            print_section("DQN Results Summary")
            self._print_results_table({'dqn': self.study_results['rl_agents']['dqn']})
            
            return results
            
        except Exception as e:
            print(f"✗ Error in DQN study: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_ppo_study(self, num_episodes: int = 50, eval_episodes: int = 10):
        """
        Run PPO agent experiments (Proximal Policy Optimization).
        
        Args:
            num_episodes: Number of training episodes
            eval_episodes: Number of evaluation episodes
        """
        print_header("PHASE 3: PPO AGENT (POLICY GRADIENT RL)")
        print("Training Proximal Policy Optimization for traffic control")
        print(f"  • Training Episodes: {num_episodes}")
        print(f"  • Evaluation Episodes: {eval_episodes}")
        print(f"  • Learning Rate: 3e-4")
        print(f"  • GAE Lambda: 0.95")
        print(f"  • Clip Range: 0.2")
        print()
        
        ppo_config = {
            'experiment_name': 'ppo_study',
            'num_episodes': num_episodes,
            'eval_episodes': eval_episodes,
            'max_steps_per_episode': 3600,
            'use_gui': False,
            'train_dqn': False,
            'train_ppo': True,
            'use_fixed_time': False,
            'use_actuated': False,
            'use_adaptive': False,
            'use_random': False,
            'save_models': True,
            'results_dir': self.results_dir,
            'env_config': {
                'reward_function': 'combined',
                'max_steps': 3600,
                'step_length': 1.0
            },
            'ppo_config': {
                'learning_rate': 3e-4,
                'gamma': 0.99,
                'gae_lambda': 0.95,
                'clip_range': 0.2,
                'ent_coef': 0.01,
                'vf_coef': 0.5,
                'max_grad_norm': 0.5,
                'n_epochs': 10,
                'batch_size': 64,
                'device': 'cpu'
            }
        }
        
        try:
            start_time = time.time()
            runner = ExperimentRunner(ppo_config)
            results = runner.run_experiment()
            duration = time.time() - start_time
            
            # Extract PPO results
            if 'ppo_evaluation' in results:
                self.study_results['rl_agents']['ppo'] = results['ppo_evaluation']
                self.study_results['rl_agents']['ppo']['training_time'] = duration
                self.study_results['rl_agents']['ppo']['training_episodes'] = num_episodes
                
                # Also save training curve data
                if 'ppo_training' in results:
                    self.study_results['rl_agents']['ppo']['training_data'] = results['ppo_training']
            
            print(f"\n✓ PPO study completed in {duration:.2f} seconds ({duration/60:.2f} minutes)")
            print_section("PPO Results Summary")
            self._print_results_table({'ppo': self.study_results['rl_agents']['ppo']})
            
            return results
            
        except Exception as e:
            print(f"✗ Error in PPO study: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_improvements(self):
        """Calculate improvement metrics (RL vs Baselines)."""
        print_header("COMPARATIVE ANALYSIS: RL vs TRADITIONAL METHODS")
        
        if not self.study_results['baselines'] or not self.study_results['rl_agents']:
            print("✗ Cannot calculate improvements - missing baseline or RL data")
            return
        
        # Get baseline reference (Fixed-Time as standard baseline)
        baseline_ref = self.study_results['baselines'].get('fixed_time', None)
        if not baseline_ref:
            print("✗ Fixed-Time baseline not found")
            return
        
        comparison_results = {}
        
        # Compare each RL agent with baselines
        for rl_name, rl_metrics in self.study_results['rl_agents'].items():
            comparison_results[rl_name] = {}
            
            # Calculate improvements vs Fixed-Time
            for metric in ['avg_reward', 'avg_waiting_time', 'avg_throughput']:
                if metric in rl_metrics and metric in baseline_ref:
                    baseline_value = baseline_ref[metric]
                    rl_value = rl_metrics[metric]
                    
                    if baseline_value != 0:
                        if metric == 'avg_reward' or metric == 'avg_throughput':
                            # Higher is better
                            improvement = ((rl_value - baseline_value) / abs(baseline_value)) * 100
                        else:
                            # Lower is better (waiting time)
                            improvement = ((baseline_value - rl_value) / abs(baseline_value)) * 100
                        
                        comparison_results[rl_name][f'{metric}_improvement'] = improvement
                        comparison_results[rl_name][f'{metric}_baseline'] = baseline_value
                        comparison_results[rl_name][f'{metric}_rl'] = rl_value
        
        self.study_results['comparison'] = comparison_results
        
        # Print comparison table
        print_section("Performance Improvements vs Fixed-Time Baseline")
        print(f"\n{'Agent':<15} {'Metric':<25} {'Baseline':<15} {'RL':<15} {'Improvement':<15}")
        print("-" * 85)
        
        for agent_name, metrics in comparison_results.items():
            print(f"\n{agent_name.upper()}")
            
            for key, value in metrics.items():
                if '_improvement' in key:
                    metric_base = key.replace('_improvement', '')
                    baseline_val = metrics[f'{metric_base}_baseline']
                    rl_val = metrics[f'{metric_base}_rl']
                    improvement = value
                    
                    metric_display = metric_base.replace('avg_', '').replace('_', ' ').title()
                    print(f"  {'':<13} {metric_display:<25} {baseline_val:<15.2f} {rl_val:<15.2f} {improvement:>+13.2f}%")
    
    def _print_results_table(self, results: Dict[str, Dict]):
        """Print formatted results table."""
        if not results:
            print("No results to display")
            return
        
        print(f"\n{'Agent':<15} {'Avg Reward':<15} {'Waiting Time':<15} {'Throughput':<15} {'Std Reward':<15}")
        print("-" * 75)
        
        for agent_name, metrics in results.items():
            if isinstance(metrics, dict):
                reward = metrics.get('avg_reward', 0)
                waiting = metrics.get('avg_waiting_time', 0)
                throughput = metrics.get('avg_throughput', 0)
                std_reward = metrics.get('std_reward', 0)
                
                print(f"{agent_name:<15} {reward:<15.2f} {waiting:<15.2f} {throughput:<15.2f} {std_reward:<15.2f}")
    
    def save_results(self):
        """Save all results to files."""
        print_header("SAVING RESULTS")
        
        # Add completion metadata
        self.study_results['metadata']['end_time'] = datetime.now().isoformat()
        
        # Save full results as JSON
        json_path = os.path.join(self.results_dir, 'comprehensive_study_results.json')
        with open(json_path, 'w') as f:
            json.dump(self.study_results, f, indent=2)
        print(f"✓ Saved full results: {json_path}")
        
        # Create summary CSV
        summary_data = []
        
        # Add baseline results
        for agent_name, metrics in self.study_results['baselines'].items():
            if isinstance(metrics, dict):
                summary_data.append({
                    'Agent Type': 'Baseline',
                    'Agent Name': agent_name,
                    'Avg Reward': metrics.get('avg_reward', 0),
                    'Avg Waiting Time': metrics.get('avg_waiting_time', 0),
                    'Avg Throughput': metrics.get('avg_throughput', 0),
                    'Std Reward': metrics.get('std_reward', 0),
                    'Std Waiting Time': metrics.get('std_waiting_time', 0),
                    'Training Time (s)': 0
                })
        
        # Add RL results
        for agent_name, metrics in self.study_results['rl_agents'].items():
            if isinstance(metrics, dict):
                summary_data.append({
                    'Agent Type': 'RL',
                    'Agent Name': agent_name,
                    'Avg Reward': metrics.get('avg_reward', 0),
                    'Avg Waiting Time': metrics.get('avg_waiting_time', 0),
                    'Avg Throughput': metrics.get('avg_throughput', 0),
                    'Std Reward': metrics.get('std_reward', 0),
                    'Std Waiting Time': metrics.get('std_waiting_time', 0),
                    'Training Time (s)': metrics.get('training_time', 0)
                })
        
        if summary_data:
            df = pd.DataFrame(summary_data)
            csv_path = os.path.join(self.results_dir, 'comprehensive_study_summary.csv')
            df.to_csv(csv_path, index=False)
            print(f"✓ Saved summary CSV: {csv_path}")
        
        print(f"\nAll results saved to: {self.results_dir}")
    
    def run_full_study(self, 
                       baseline_eval_episodes: int = 20,
                       rl_training_episodes: int = 50,
                       rl_eval_episodes: int = 10):
        """
        Run complete comprehensive study for thesis.
        
        Args:
            baseline_eval_episodes: Number of evaluation episodes for baselines
            rl_training_episodes: Number of training episodes for RL agents
            rl_eval_episodes: Number of evaluation episodes for RL agents
        """
        print_header("COMPREHENSIVE TRAFFIC CONTROL STUDY FOR MASTER'S THESIS")
        print(f"Study Start Time: {self.study_results['metadata']['start_time']}")
        print(f"\nStudy Configuration:")
        print(f"  • Baseline Evaluation Episodes: {baseline_eval_episodes}")
        print(f"  • RL Training Episodes: {rl_training_episodes}")
        print(f"  • RL Evaluation Episodes: {rl_eval_episodes}")
        print(f"  • Results Directory: {self.results_dir}")
        
        overall_start = time.time()
        
        # Phase 1: Baseline Controllers
        self.run_baseline_study(
            num_episodes=1, 
            eval_episodes=baseline_eval_episodes
        )
        
        # Phase 2: DQN Agent
        self.run_dqn_study(
            num_episodes=rl_training_episodes,
            eval_episodes=rl_eval_episodes
        )
        
        # Phase 3: PPO Agent (optional, can comment out if takes too long)
        # self.run_ppo_study(
        #     num_episodes=rl_training_episodes,
        #     eval_episodes=rl_eval_episodes
        # )
        
        # Comparative Analysis
        self.calculate_improvements()
        
        # Save all results
        self.save_results()
        
        overall_duration = time.time() - overall_start
        
        print_header("STUDY COMPLETE")
        print(f"Total Duration: {overall_duration:.2f} seconds ({overall_duration/60:.2f} minutes)")
        print(f"\nResults have been saved and are ready for thesis presentation!")
        print(f"Check the '{self.results_dir}' directory for:")
        print(f"  • comprehensive_study_results.json (detailed data)")
        print(f"  • comprehensive_study_summary.csv (summary table)")
        print(f"  • Model files (*_model.zip) for RL agents")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run comprehensive traffic control study for thesis'
    )
    parser.add_argument('--baseline-episodes', type=int, default=20,
                       help='Number of evaluation episodes for baselines')
    parser.add_argument('--rl-train-episodes', type=int, default=50,
                       help='Number of training episodes for RL agents')
    parser.add_argument('--rl-eval-episodes', type=int, default=10,
                       help='Number of evaluation episodes for RL agents')
    parser.add_argument('--results-dir', type=str, default='./results/',
                       help='Directory to save results')
    parser.add_argument('--quick-test', action='store_true',
                       help='Run quick test with minimal episodes')
    
    args = parser.parse_args()
    
    # Quick test mode
    if args.quick_test:
        print("⚡ Quick Test Mode - Using minimal episodes")
        args.baseline_episodes = 3
        args.rl_train_episodes = 5
        args.rl_eval_episodes = 2
    
    # Create and run study
    study = ComprehensiveStudy(results_dir=args.results_dir)
    
    study.run_full_study(
        baseline_eval_episodes=args.baseline_episodes,
        rl_training_episodes=args.rl_train_episodes,
        rl_eval_episodes=args.rl_eval_episodes
    )


if __name__ == "__main__":
    main()

