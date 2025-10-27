#!/usr/bin/env python3
"""
Mock SUMO Experiments for Traffic Light Control.

This script runs RL experiments using mock SUMO environments for both
single and multi-intersection scenarios, allowing comparison of agent
performance without requiring actual SUMO installation.
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any
import argparse


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import agents
from agents.dqn_agent import DQNAgent, create_dqn_agent

# Import mock environments
from environment.mock_traffic_env import (
    SingleIntersectionMockEnv,
    MultiIntersectionMockEnv,
    create_single_intersection_env,
    create_multi_intersection_env
)


class MockExperimentRunner:
    """
    Experiment runner for mock SUMO traffic environments.

    This class manages training and evaluation of RL agents on mock
    traffic environments for both single and multi-intersection scenarios.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration
        """
        self.config = config
        self.results_dir = config.get('results_dir', './results/mock_experiments/')
        self.experiment_name = config.get('experiment_name', 'mock_traffic_control')

        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(os.path.join(self.results_dir, 'figures'), exist_ok=True)

        print(f"🚀 Starting mock experiments: {self.experiment_name}")
        print(f"📁 Results will be saved to: {self.results_dir}")

    def run_single_intersection_experiment(self) -> Dict[str, Any]:
        """Run experiment for single intersection."""
        print("\n" + "="*50)
        print("🟢 SINGLE INTERSECTION EXPERIMENT")
        print("="*50)

        # Create environment
        env = create_single_intersection_env(
            max_steps=self.config.get('max_steps', 3600),
            step_length=self.config.get('step_length', 1.0),
            traffic_demand=self.config.get('traffic_demand', 0.15)
        )

        # Create agent
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n

        agent = create_dqn_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            config=self.config.get('dqn_config', {})
        )

        # Training
        results = self._train_agent(env, agent, "single_intersection")

        # Evaluation
        eval_results = self._evaluate_agent(env, agent, "single_intersection")

        results.update(eval_results)
        env.close()

        return results

    def run_multi_intersection_experiment(self) -> Dict[str, Any]:
        """Run experiment for multi-intersection."""
        print("\n" + "="*50)
        print("🔴 MULTI-INTERSECTION EXPERIMENT")
        print("="*50)

        # Create environment
        env = create_multi_intersection_env(
            max_steps=self.config.get('max_steps', 3600),
            step_length=self.config.get('step_length', 1.0),
            traffic_demand=self.config.get('traffic_demand', 0.15),
            coordination=self.config.get('coordination', True)
        )

        # Create agent
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n if hasattr(env.action_space, 'n') else env.action_space.nvec[0]

        agent = create_dqn_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            config=self.config.get('dqn_config', {})
        )

        # Training
        results = self._train_agent(env, agent, "multi_intersection")

        # Evaluation
        eval_results = self._evaluate_agent(env, agent, "multi_intersection")

        results.update(eval_results)
        env.close()

        return results

    def _train_agent(self, env, agent: DQNAgent, scenario: str) -> Dict[str, Any]:
        """Train agent on environment."""
        print(f"\n🏋️  Training {scenario}...")

        num_episodes = self.config.get('num_episodes', 50)
        eval_freq = self.config.get('eval_frequency', 10)

        training_rewards = []
        training_waiting_times = []
        training_throughput = []

        for episode in range(num_episodes):
            obs, _ = env.reset()
            episode_reward = 0
            episode_waiting_time = 0
            episode_throughput = 0

            done = False
            while not done:
                # Select action
                action = agent.select_action(obs)

                # Execute action
                next_obs, reward, done, _, info = env.step(action)

                # Store experience
                agent.store_experience(obs, action, reward, next_obs, done)

                # Update agent
                agent.update_model()

                # Accumulate metrics
                episode_reward += reward
                episode_waiting_time += info.get('total_waiting_time', 0)
                episode_throughput += info.get('throughput', 0)

                obs = next_obs

            # Store episode metrics
            training_rewards.append(episode_reward)
            training_waiting_times.append(episode_waiting_time)
            training_throughput.append(episode_throughput)

            # Periodic evaluation
            if (episode + 1) % eval_freq == 0:
                print(f"  Episode {episode + 1:2d}: Reward={episode_reward:7.2f}, "
                      f"Waiting={episode_waiting_time:6.1f}, Throughput={episode_throughput:3d}")

        # Save training results
        training_results = {
            'scenario': scenario,
            'training_rewards': training_rewards,
            'training_waiting_times': training_waiting_times,
            'training_throughput': training_throughput,
            'final_reward': np.mean(training_rewards[-10:]),
            'final_waiting_time': np.mean(training_waiting_times[-10:]),
            'final_throughput': np.mean(training_throughput[-10:])
        }

        print(f"✅ Training completed for {scenario}")
        print(f"   Final avg reward: {training_results['final_reward']:.2f}")
        print(f"   Final avg waiting time: {training_results['final_waiting_time']:.1f}")
        print(f"   Final avg throughput: {training_results['final_throughput']:.1f}")

        return training_results

    def _evaluate_agent(self, env, agent: DQNAgent, scenario: str) -> Dict[str, Any]:
        """Evaluate trained agent."""
        print(f"\n🧪 Evaluating {scenario}...")

        num_eval_episodes = self.config.get('num_eval_episodes', 10)
        eval_rewards = []
        eval_waiting_times = []
        eval_throughput = []

        for episode in range(num_eval_episodes):
            obs, _ = env.reset()
            episode_reward = 0
            episode_waiting_time = 0
            episode_throughput = 0

            done = False
            while not done:
                # Select action (greedy for evaluation)
                # Temporarily disable training mode for greedy selection
                original_training_mode = agent.training_mode
                agent.training_mode = False
                action = agent.select_action(obs)
                agent.training_mode = original_training_mode
                next_obs, reward, done, _, info = env.step(action)

                episode_reward += reward
                episode_waiting_time += info.get('total_waiting_time', 0)
                episode_throughput += info.get('throughput', 0)

                obs = next_obs

            eval_rewards.append(episode_reward)
            eval_waiting_times.append(episode_waiting_time)
            eval_throughput.append(episode_throughput)

        eval_results = {
            'eval_rewards': eval_rewards,
            'eval_waiting_times': eval_waiting_times,
            'eval_throughput': eval_throughput,
            'eval_avg_reward': np.mean(eval_rewards),
            'eval_avg_waiting_time': np.mean(eval_waiting_times),
            'eval_avg_throughput': np.mean(eval_throughput),
            'eval_std_reward': np.std(eval_rewards),
            'eval_std_waiting_time': np.std(eval_waiting_times)
        }

        print(f"✅ Evaluation completed for {scenario}")
        print(f"   Avg reward: {eval_results['eval_avg_reward']:.2f} ± {eval_results['eval_std_reward']:.2f}")
        print(f"   Avg waiting time: {eval_results['eval_avg_waiting_time']:.1f} ± {eval_results['eval_std_waiting_time']:.1f}")
        print(f"   Avg throughput: {eval_results['eval_avg_throughput']:.1f}")

        return eval_results

    def run_comparison_experiment(self) -> Dict[str, Any]:
        """Run both single and multi-intersection experiments for comparison."""
        print("\n" + "="*60)
        print("🚦 MOCK SUMO TRAFFIC CONTROL COMPARISON STUDY")
        print("="*60)

        # Run single intersection experiment
        single_results = self.run_single_intersection_experiment()

        # Run multi-intersection experiment
        multi_results = self.run_multi_intersection_experiment()

        # Compile comparison results
        comparison_results = {
            'experiment_name': self.experiment_name,
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'single_intersection': single_results,
            'multi_intersection': multi_results,
            'comparison': self._generate_comparison(single_results, multi_results)
        }

        # Save results
        self._save_results(comparison_results)

        # Generate comparison plots
        self._generate_comparison_plots(comparison_results)

        return comparison_results

    def _generate_comparison(self, single: Dict, multi: Dict) -> Dict[str, Any]:
        """Generate comparison metrics."""
        comparison = {
            'reward_improvement': {
                'single_to_multi': multi['eval_avg_reward'] - single['eval_avg_reward'],
                'relative_percent': ((multi['eval_avg_reward'] - single['eval_avg_reward']) / abs(single['eval_avg_reward'])) * 100 if single['eval_avg_reward'] != 0 else 0
            },
            'waiting_time_comparison': {
                'single': single['eval_avg_waiting_time'],
                'multi': multi['eval_avg_waiting_time'],
                'multi_is_worse': multi['eval_avg_waiting_time'] > single['eval_avg_waiting_time']
            },
            'throughput_comparison': {
                'single': single['eval_avg_throughput'],
                'multi': multi['eval_avg_throughput'],
                'multi_is_better': multi['eval_avg_throughput'] > single['eval_avg_throughput']
            },
            'complexity_ratio': {
                'state_space': multi_intersection_obs_dim / single_intersection_obs_dim if 'single_intersection_obs_dim' in locals() else 3.0,
                'action_space': 2.0 if self.config.get('coordination', True) else 8.0
            }
        }

        return comparison

    def _save_results(self, results: Dict[str, Any]) -> None:
        """Save experiment results to files."""
        # Save JSON results
        json_path = os.path.join(self.results_dir, f'{self.experiment_name}_results.json')
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, cls=NumpyEncoder)
        print(f"\n💾 Results saved to: {json_path}")

        # Save summary CSV
        csv_path = os.path.join(self.results_dir, f'{self.experiment_name}_summary.csv')
        self._save_summary_csv(results, csv_path)
        print(f"📊 Summary saved to: {csv_path}")

    def _save_summary_csv(self, results: Dict[str, Any], csv_path: str) -> None:
        """Save summary results to CSV."""
        import csv

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Scenario', 'Eval_Avg_Reward', 'Eval_Std_Reward',
                           'Eval_Avg_Waiting_Time', 'Eval_Std_Waiting_Time',
                           'Eval_Avg_Throughput', 'Training_Time_Est'])

            # Single intersection results
            single = results['single_intersection']
            writer.writerow([
                'Single Intersection',
                single['eval_avg_reward'],
                single.get('eval_std_reward', 0),
                single['eval_avg_waiting_time'],
                single.get('eval_std_waiting_time', 0),
                single['eval_avg_throughput'],
                'N/A (Mock)'
            ])

            # Multi intersection results
            multi = results['multi_intersection']
            writer.writerow([
                'Multi Intersection',
                multi['eval_avg_reward'],
                multi.get('eval_std_reward', 0),
                multi['eval_avg_waiting_time'],
                multi.get('eval_std_waiting_time', 0),
                multi['eval_avg_throughput'],
                'N/A (Mock)'
            ])

            # Comparison
            comp = results['comparison']
            writer.writerow([
                'Improvement (Multi vs Single)',
                comp['reward_improvement']['single_to_multi'],
                '',
                comp['waiting_time_comparison']['multi'] - comp['waiting_time_comparison']['single'],
                '',
                comp['throughput_comparison']['multi'] - comp['throughput_comparison']['single'],
                ''
            ])

    def _generate_comparison_plots(self, results: Dict[str, Any]) -> None:
        """Generate comparison plots."""
        figures_dir = os.path.join(self.results_dir, 'figures')

        # Plot 1: Reward comparison
        plt.figure(figsize=(12, 8))

        scenarios = ['Single Intersection', 'Multi Intersection']
        rewards = [
            results['single_intersection']['eval_avg_reward'],
            results['multi_intersection']['eval_avg_reward']
        ]

        plt.subplot(2, 2, 1)
        bars = plt.bar(scenarios, rewards, color=['blue', 'red'])
        plt.title('Average Reward Comparison')
        plt.ylabel('Reward')
        for bar, reward in zip(bars, rewards):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{reward:.2f}', ha='center', va='bottom')

        # Plot 2: Waiting time comparison
        plt.subplot(2, 2, 2)
        waiting_times = [
            results['single_intersection']['eval_avg_waiting_time'],
            results['multi_intersection']['eval_avg_waiting_time']
        ]
        bars = plt.bar(scenarios, waiting_times, color=['lightblue', 'pink'])
        plt.title('Average Waiting Time Comparison')
        plt.ylabel('Waiting Time (s)')
        for bar, waiting in zip(bars, waiting_times):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{waiting:.1f}', ha='center', va='bottom')

        # Plot 3: Throughput comparison
        plt.subplot(2, 2, 3)
        throughput = [
            results['single_intersection']['eval_avg_throughput'],
            results['multi_intersection']['eval_avg_throughput']
        ]
        bars = plt.bar(scenarios, throughput, color=['green', 'orange'])
        plt.title('Average Throughput Comparison')
        plt.ylabel('Vehicles')
        for bar, tp in zip(bars, throughput):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{tp:.1f}', ha='center', va='bottom')

        # Plot 4: Training progress
        plt.subplot(2, 2, 4)
        single_rewards = results['single_intersection']['training_rewards']
        multi_rewards = results['multi_intersection']['training_rewards']

        plt.plot(single_rewards, label='Single Intersection', alpha=0.7)
        plt.plot(multi_rewards, label='Multi Intersection', alpha=0.7)
        plt.title('Training Progress')
        plt.xlabel('Episode')
        plt.ylabel('Reward')
        plt.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, f'{self.experiment_name}_comparison.png'),
                   dpi=300, bbox_inches='tight')
        plt.close()

        print(f"📊 Comparison plots saved to: {figures_dir}")

    def run_quick_test(self) -> Dict[str, Any]:
        """Run a quick test with fewer episodes for testing."""
        print("\n⚡ Running quick test mode...")

        # Use smaller configuration for quick testing
        quick_config = self.config.copy()
        quick_config.update({
            'num_episodes': 5,
            'num_eval_episodes': 3,
            'max_steps': 100,
            'dqn_config': {
                'learning_rate': 1e-3,
                'gamma': 0.99,
                'epsilon_start': 1.0,
                'epsilon_end': 0.1,
                'batch_size': 32,
                'buffer_capacity': 1000
            }
        })

        self.config = quick_config
        return self.run_comparison_experiment()


def main():
    """Main function to run mock experiments."""
    parser = argparse.ArgumentParser(description='Run mock SUMO traffic control experiments')
    parser.add_argument('--experiment-name', default='mock_traffic_study',
                       help='Name of the experiment')
    parser.add_argument('--num-episodes', type=int, default=50,
                       help='Number of training episodes')
    parser.add_argument('--num-eval-episodes', type=int, default=10,
                       help='Number of evaluation episodes')
    parser.add_argument('--max-steps', type=int, default=3600,
                       help='Maximum steps per episode')
    parser.add_argument('--quick-test', action='store_true',
                       help='Run quick test with minimal episodes')
    parser.add_argument('--no-coordination', action='store_true',
                       help='Disable intersection coordination for multi-intersection scenario')

    args = parser.parse_args()

    # Configuration
    config = {
        'experiment_name': args.experiment_name,
        'num_episodes': args.num_episodes,
        'num_eval_episodes': args.num_eval_episodes,
        'max_steps': args.max_steps,
        'coordination': not args.no_coordination,
        'traffic_demand': 0.15,
        'step_length': 1.0,
        'results_dir': './results/mock_experiments/',
        'dqn_config': {
            'learning_rate': 5e-4,
            'gamma': 0.99,
            'epsilon_start': 1.0,
            'epsilon_end': 0.01,
            'epsilon_decay': 0.995,
            'batch_size': 64,
            'buffer_capacity': 10000,
            'target_update_freq': 100
        }
    }

    # Create and run experiment
    runner = MockExperimentRunner(config)

    if args.quick_test:
        results = runner.run_quick_test()
    else:
        results = runner.run_comparison_experiment()

    # Print final summary
    print("\n" + "="*60)
    print("🎉 MOCK EXPERIMENT COMPLETED!")
    print("="*60)

    comparison = results['comparison']
    print("📊 COMPARISON RESULTS:")
    print(f"  Reward improvement: {comparison['reward_improvement']['single_to_multi']:.2f} "
          f"({comparison['reward_improvement']['relative_percent']:.1f}%)")
    print(f"  Single waiting time: {comparison['waiting_time_comparison']['single']:.1f}s")
    print(f"  Multi waiting time:  {comparison['waiting_time_comparison']['multi']:.1f}s")
    print(f"  Single throughput:   {comparison['throughput_comparison']['single']:.1f} vehicles")
    print(f"  Multi throughput:    {comparison['throughput_comparison']['multi']:.1f} vehicles")

    print("\n📁 Results saved to: ./results/mock_experiments/")
    print(f"📊 Plots: {args.experiment_name}_comparison.png")


if __name__ == '__main__':
    main()
