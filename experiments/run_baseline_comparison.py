#!/usr/bin/env python3
"""
Baseline Comparison Experiments for Traffic Light Control.

This script runs comprehensive experiments comparing RL agents (DQN) against
traditional baseline controllers (fixed-time, actuated, adaptive, random)
for both single and multi-intersection scenarios.
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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import agents and environments
from agents.dqn_agent import DQNAgent, create_dqn_agent
from agents.baseline_controllers import (
    FixedTimeController,
    ActuatedController,
    AdaptiveController,
    RandomController
)

from environment.baseline_env import (
    create_baseline_single_env,
    create_baseline_multi_env
)
from environment.mock_traffic_env import (
    create_single_intersection_env,
    create_multi_intersection_env
)


class BaselineComparisonRunner:
    """
    Experiment runner for comparing RL agents against baseline controllers.

    This class manages comprehensive evaluation of different traffic light
    control methods across single and multi-intersection scenarios.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize comparison experiment runner.

        Args:
            config: Experiment configuration
        """
        self.config = config
        self.results_dir = config.get('results_dir', './results/baseline_comparison/')
        self.experiment_name = config.get('experiment_name', 'baseline_comparison_study')

        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(os.path.join(self.results_dir, 'figures'), exist_ok=True)

        print(f"🚀 Starting baseline comparison: {self.experiment_name}")
        print(f"📁 Results will be saved to: {self.results_dir}")

    def run_single_intersection_comparison(self) -> Dict[str, Any]:
        """Run comparison for single intersection."""
        print("\n" + "="*60)
        print("🟢 SINGLE INTERSECTION BASELINE COMPARISON")
        print("="*60)

        results = {
            'scenario': 'single_intersection',
            'controllers': {}
        }

        # Define controllers to test
        controllers = {
            'DQN': self._create_dqn_agent(),
            'FixedTime': FixedTimeController(phase_duration=30),
            'Actuated': ActuatedController(threshold=10.0, min_green_time=15, max_green_time=60),
            'Adaptive': AdaptiveController(base_green_time=20, max_green_time=60),
            'Random': RandomController(num_phases=2)
        }

        # Test each controller
        for controller_name, controller in controllers.items():
            print(f"\n🧪 Testing {controller_name}...")

            if controller_name == 'DQN':
                # Use RL environment for DQN
                env = create_single_intersection_env(
                    max_steps=self.config.get('max_steps', 3600),
                    step_length=self.config.get('step_length', 1.0),
                    traffic_demand=self.config.get('traffic_demand', 0.15)
                )
                controller_results = self._train_and_evaluate_rl(env, controller, controller_name)
            else:
                # Use baseline environment for traditional controllers
                env = create_baseline_single_env(
                    controller=controller,
                    max_steps=self.config.get('max_steps', 3600),
                    step_length=self.config.get('step_length', 1.0),
                    traffic_demand=self.config.get('traffic_demand', 0.15)
                )
                controller_results = self._evaluate_baseline(env, controller, controller_name)

            results['controllers'][controller_name] = controller_results
            env.close()

        return results

    def run_multi_intersection_comparison(self) -> Dict[str, Any]:
        """Run comparison for multi-intersection."""
        print("\n" + "="*60)
        print("🔴 MULTI-INTERSECTION BASELINE COMPARISON")
        print("="*60)

        results = {
            'scenario': 'multi_intersection',
            'controllers': {}
        }

        # Define controllers to test
        controllers = {
            'DQN': self._create_dqn_agent(),
            'FixedTime': FixedTimeController(phase_duration=30),
            'Actuated': ActuatedController(threshold=10.0, min_green_time=15, max_green_time=60),
            'Adaptive': AdaptiveController(base_green_time=20, max_green_time=60),
            'Random': RandomController(num_phases=2)
        }

        # Test each controller
        for controller_name, controller in controllers.items():
            print(f"\n🧪 Testing {controller_name}...")

            if controller_name == 'DQN':
                # Use RL environment for DQN
                env = create_multi_intersection_env(
                    max_steps=self.config.get('max_steps', 3600),
                    step_length=self.config.get('step_length', 1.0),
                    traffic_demand=self.config.get('traffic_demand', 0.15),
                    coordination=self.config.get('coordination', True)
                )
                controller_results = self._train_and_evaluate_rl(env, controller, controller_name)
            else:
                # Use baseline environment for traditional controllers
                env = create_baseline_multi_env(
                    controller=controller,
                    max_steps=self.config.get('max_steps', 3600),
                    step_length=self.config.get('step_length', 1.0),
                    traffic_demand=self.config.get('traffic_demand', 0.15),
                    coordination=self.config.get('coordination', True)
                )
                controller_results = self._evaluate_baseline(env, controller, controller_name)

            results['controllers'][controller_name] = controller_results
            env.close()

        return results

    def _create_dqn_agent(self) -> DQNAgent:
        """Create DQN agent with configuration."""
        # This will be created in the specific environment context
        # Return a placeholder - actual agent will be created in training method
        return None

    def _train_and_evaluate_rl(self, env, agent: DQNAgent, controller_name: str) -> Dict[str, Any]:
        """Train and evaluate RL agent."""
        print(f"🏋️  Training {controller_name}...")

        # Create agent with proper dimensions
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n if hasattr(env.action_space, 'n') else env.action_space.nvec[0]

        agent = create_dqn_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            config=self.config.get('dqn_config', {})
        )

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

            # Periodic progress report
            if (episode + 1) % eval_freq == 0:
                print(f"  Episode {episode + 1:2d}: Reward={episode_reward:7.2f}, "
                      f"Waiting={episode_waiting_time:6.1f}, Throughput={episode_throughput:3d}")

        # Evaluation
        print(f"🧪 Evaluating {controller_name}...")
        eval_results = self._evaluate_rl_agent(env, agent, controller_name)

        return {
            'type': 'RL',
            'training_rewards': training_rewards,
            'training_waiting_times': training_waiting_times,
            'training_throughput': training_throughput,
            'final_reward': np.mean(training_rewards[-10:]),
            'final_waiting_time': np.mean(training_waiting_times[-10:]),
            'final_throughput': np.mean(training_throughput[-10:]),
            **eval_results
        }

    def _evaluate_rl_agent(self, env, agent: DQNAgent, controller_name: str) -> Dict[str, Any]:
        """Evaluate trained RL agent."""
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

        return {
            'eval_rewards': eval_rewards,
            'eval_waiting_times': eval_waiting_times,
            'eval_throughput': eval_throughput,
            'eval_avg_reward': np.mean(eval_rewards),
            'eval_avg_waiting_time': np.mean(eval_waiting_times),
            'eval_avg_throughput': np.mean(eval_throughput),
            'eval_std_reward': np.std(eval_rewards),
            'eval_std_waiting_time': np.std(eval_waiting_times)
        }

    def _evaluate_baseline(self, env, controller, controller_name: str) -> Dict[str, Any]:
        """Evaluate baseline controller."""
        print(f"🧪 Evaluating {controller_name}...")

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
                # Let controller make decision
                action = controller.select_action(obs)
                next_obs, reward, done, _, info = env.step(action)

                episode_reward += reward
                episode_waiting_time += info.get('total_waiting_time', 0)
                episode_throughput += info.get('throughput', 0)

                obs = next_obs

            eval_rewards.append(episode_reward)
            eval_waiting_times.append(episode_waiting_time)
            eval_throughput.append(episode_throughput)

        return {
            'type': 'Baseline',
            'eval_rewards': eval_rewards,
            'eval_waiting_times': eval_waiting_times,
            'eval_throughput': eval_throughput,
            'eval_avg_reward': np.mean(eval_rewards),
            'eval_avg_waiting_time': np.mean(eval_waiting_times),
            'eval_avg_throughput': np.mean(eval_throughput),
            'eval_std_reward': np.std(eval_rewards),
            'eval_std_waiting_time': np.std(eval_waiting_times)
        }

    def run_complete_comparison(self) -> Dict[str, Any]:
        """Run complete comparison study."""
        print("\n" + "="*70)
        print("🚦 COMPLETE BASELINE COMPARISON STUDY")
        print("="*70)

        # Run single intersection comparison
        single_results = self.run_single_intersection_comparison()

        # Run multi-intersection comparison
        multi_results = self.run_multi_intersection_comparison()

        # Compile complete results
        complete_results = {
            'experiment_name': self.experiment_name,
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'single_intersection': single_results,
            'multi_intersection': multi_results,
            'comparison': self._generate_comparison_analysis(single_results, multi_results)
        }

        # Save results
        self._save_comparison_results(complete_results)

        # Generate comparison plots
        self._generate_comparison_plots(complete_results)

        return complete_results

    def _generate_comparison_analysis(self, single_results: Dict, multi_results: Dict) -> Dict[str, Any]:
        """Generate comprehensive comparison analysis."""
        analysis = {
            'single_intersection_rankings': {},
            'multi_intersection_rankings': {},
            'improvements': {}
        }

        # Single intersection rankings
        single_controllers = single_results['controllers']
        single_rewards = [(name, data['eval_avg_reward']) for name, data in single_controllers.items()]
        single_rewards.sort(key=lambda x: x[1], reverse=True)  # Sort by reward (higher is better)

        analysis['single_intersection_rankings'] = {
            'best_reward': single_rewards[0][0],
            'worst_reward': single_rewards[-1][0],
            'reward_order': [name for name, _ in single_rewards]
        }

        # Multi-intersection rankings
        multi_controllers = multi_results['controllers']
        multi_rewards = [(name, data['eval_avg_reward']) for name, data in multi_controllers.items()]
        multi_rewards.sort(key=lambda x: x[1], reverse=True)

        analysis['multi_intersection_rankings'] = {
            'best_reward': multi_rewards[0][0],
            'worst_reward': multi_rewards[-1][0],
            'reward_order': [name for name, _ in multi_rewards]
        }

        # Calculate improvements
        if 'DQN' in single_controllers and 'DQN' in multi_controllers:
            dqn_single = single_controllers['DQN']['eval_avg_reward']
            dqn_multi = multi_controllers['DQN']['eval_avg_reward']

            analysis['improvements']['rl_scalability'] = {
                'single_to_multi_change': dqn_multi - dqn_single,
                'relative_change_percent': ((dqn_multi - dqn_single) / abs(dqn_single)) * 100 if dqn_single != 0 else 0
            }

        return analysis

    def _save_comparison_results(self, results: Dict[str, Any]) -> None:
        """Save comparison results to files."""
        # Save JSON results
        json_path = os.path.join(self.results_dir, f'{self.experiment_name}_results.json')
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {json_path}")

        # Save summary CSV
        csv_path = os.path.join(self.results_dir, f'{self.experiment_name}_summary.csv')
        self._save_comparison_csv(results, csv_path)
        print(f"📊 Summary saved to: {csv_path}")

    def _save_comparison_csv(self, results: Dict[str, Any], csv_path: str) -> None:
        """Save comparison results to CSV."""
        import csv

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Scenario', 'Controller', 'Type', 'Avg_Reward', 'Std_Reward',
                           'Avg_Waiting_Time', 'Std_Waiting_Time', 'Avg_Throughput'])

            # Single intersection results
            for controller_name, data in results['single_intersection']['controllers'].items():
                writer.writerow([
                    'Single Intersection',
                    controller_name,
                    data['type'],
                    data['eval_avg_reward'],
                    data.get('eval_std_reward', 0),
                    data['eval_avg_waiting_time'],
                    data.get('eval_std_waiting_time', 0),
                    data['eval_avg_throughput']
                ])

            # Multi-intersection results
            for controller_name, data in results['multi_intersection']['controllers'].items():
                writer.writerow([
                    'Multi Intersection',
                    controller_name,
                    data['type'],
                    data['eval_avg_reward'],
                    data.get('eval_std_reward', 0),
                    data['eval_avg_waiting_time'],
                    data.get('eval_std_waiting_time', 0),
                    data['eval_avg_throughput']
                ])

    def _generate_comparison_plots(self, results: Dict[str, Any]) -> None:
        """Generate comprehensive comparison plots."""
        figures_dir = os.path.join(self.results_dir, 'figures')

        # Plot 1: Reward comparison by scenario
        plt.figure(figsize=(15, 10))

        # Single intersection rewards
        single_controllers = results['single_intersection']['controllers']
        multi_controllers = results['multi_intersection']['controllers']

        controller_names = list(single_controllers.keys())
        single_rewards = [single_controllers[name]['eval_avg_reward'] for name in controller_names]
        multi_rewards = [multi_controllers[name]['eval_avg_reward'] for name in controller_names]

        x = np.arange(len(controller_names))
        width = 0.35

        plt.subplot(2, 3, 1)
        bars1 = plt.bar(x - width/2, single_rewards, width, label='Single Intersection', alpha=0.8)
        bars2 = plt.bar(x + width/2, multi_rewards, width, label='Multi Intersection', alpha=0.8)

        plt.xlabel('Controller')
        plt.ylabel('Average Reward')
        plt.title('Reward Comparison by Controller and Scenario')
        plt.xticks(x, controller_names, rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Add value labels
        for bar, reward in zip(bars1, single_rewards):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{reward:,.0f}', ha='center', va='bottom')
        for bar, reward in zip(bars2, multi_rewards):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{reward:,.0f}', ha='center', va='bottom')

        # Plot 2: Waiting time comparison
        plt.subplot(2, 3, 2)
        single_waiting = [single_controllers[name]['eval_avg_waiting_time'] for name in controller_names]
        multi_waiting = [multi_controllers[name]['eval_avg_waiting_time'] for name in controller_names]

        bars1 = plt.bar(x - width/2, single_waiting, width, label='Single Intersection', alpha=0.8)
        bars2 = plt.bar(x + width/2, multi_waiting, width, label='Multi Intersection', alpha=0.8)

        plt.xlabel('Controller')
        plt.ylabel('Average Waiting Time (s)')
        plt.title('Waiting Time Comparison by Controller and Scenario')
        plt.xticks(x, controller_names, rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)

        for bar, waiting in zip(bars1, single_waiting):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{waiting:,.0f}', ha='center', va='bottom')
        for bar, waiting in zip(bars2, multi_waiting):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{waiting:,.0f}', ha='center', va='bottom')

        # Plot 3: Throughput comparison
        plt.subplot(2, 3, 3)
        single_throughput = [single_controllers[name]['eval_avg_throughput'] for name in controller_names]
        multi_throughput = [multi_controllers[name]['eval_avg_throughput'] for name in controller_names]

        bars1 = plt.bar(x - width/2, single_throughput, width, label='Single Intersection', alpha=0.8)
        bars2 = plt.bar(x + width/2, multi_throughput, width, label='Multi Intersection', alpha=0.8)

        plt.xlabel('Controller')
        plt.ylabel('Average Throughput')
        plt.title('Throughput Comparison by Controller and Scenario')
        plt.xticks(x, controller_names, rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)

        for bar, tp in zip(bars1, single_throughput):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{tp:.1f}', ha='center', va='bottom')
        for bar, tp in zip(bars2, multi_throughput):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{tp:.1f}', ha='center', va='bottom')

        # Plot 4: RL vs Best Baseline
        plt.subplot(2, 3, 4)
        rl_controllers = ['DQN']
        baseline_controllers = ['FixedTime', 'Actuated', 'Adaptive', 'Random']

        # Single intersection
        rl_single = single_controllers['DQN']['eval_avg_reward']
        baseline_single = [single_controllers[name]['eval_avg_reward'] for name in baseline_controllers]
        best_baseline_single = max(baseline_single)

        # Multi intersection
        rl_multi = multi_controllers['DQN']['eval_avg_reward']
        baseline_multi = [multi_controllers[name]['eval_avg_reward'] for name in baseline_controllers]
        best_baseline_multi = max(baseline_multi)

        scenarios = ['Single', 'Multi']
        rl_rewards = [rl_single, rl_multi]
        best_baseline_rewards = [best_baseline_single, best_baseline_multi]

        x = np.arange(len(scenarios))
        width = 0.35

        bars1 = plt.bar(x - width/2, rl_rewards, width, label='DQN (RL)', color='blue', alpha=0.8)
        bars2 = plt.bar(x + width/2, best_baseline_rewards, width, label='Best Baseline', color='orange', alpha=0.8)

        plt.xlabel('Scenario')
        plt.ylabel('Average Reward')
        plt.title('RL vs Best Baseline Performance')
        plt.xticks(x, scenarios)
        plt.legend()
        plt.grid(True, alpha=0.3)

        for bar, reward in zip(bars1, rl_rewards):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{reward:,.0f}', ha='center', va='bottom')
        for bar, reward in zip(bars2, best_baseline_rewards):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{reward:,.0f}', ha='center', va='bottom')

        # Plot 5: Improvement analysis
        plt.subplot(2, 3, 5)
        improvement_single = rl_single - best_baseline_single
        improvement_multi = rl_multi - best_baseline_multi

        improvements = [improvement_single, improvement_multi]
        colors = ['green' if imp > 0 else 'red' for imp in improvements]

        bars = plt.bar(scenarios, improvements, color=colors, alpha=0.8)
        plt.xlabel('Scenario')
        plt.ylabel('Reward Improvement')
        plt.title('RL Improvement over Best Baseline')
        plt.grid(True, alpha=0.3)

        for bar, improvement in zip(bars, improvements):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{improvement:+.0f}', ha='center', va='bottom' if improvement >= 0 else 'top')

        # Plot 6: Controller type comparison
        plt.subplot(2, 3, 6)
        controller_types = ['RL', 'Adaptive', 'Actuated', 'Fixed-Time', 'Random']

        # Average performance across scenarios
        type_performance = {}
        for controller_type in controller_types:
            if controller_type == 'RL':
                avg_reward = (single_controllers['DQN']['eval_avg_reward'] +
                            multi_controllers['DQN']['eval_avg_reward']) / 2
            elif controller_type == 'Adaptive':
                avg_reward = (single_controllers['Adaptive']['eval_avg_reward'] +
                            multi_controllers['Adaptive']['eval_avg_reward']) / 2
            elif controller_type == 'Actuated':
                avg_reward = (single_controllers['Actuated']['eval_avg_reward'] +
                            multi_controllers['Actuated']['eval_avg_reward']) / 2
            elif controller_type == 'Fixed-Time':
                avg_reward = (single_controllers['FixedTime']['eval_avg_reward'] +
                            multi_controllers['FixedTime']['eval_avg_reward']) / 2
            else:  # Random
                avg_reward = (single_controllers['Random']['eval_avg_reward'] +
                            multi_controllers['Random']['eval_avg_reward']) / 2

            type_performance[controller_type] = avg_reward

        plt.bar(controller_types, [type_performance[t] for t in controller_types],
               color=['blue', 'green', 'orange', 'red', 'gray'], alpha=0.8)
        plt.xlabel('Controller Type')
        plt.ylabel('Average Reward')
        plt.title('Average Performance by Controller Type')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)

        # Add value labels
        for i, controller_type in enumerate(controller_types):
            reward = type_performance[controller_type]
            plt.text(i, reward, f'{reward:,.0f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, f'{self.experiment_name}_comparison.png'),
                   dpi=300, bbox_inches='tight')
        plt.close()

        print(f"📊 Comparison plots saved to: {figures_dir}")

    def run_quick_comparison(self) -> Dict[str, Any]:
        """Run a quick comparison with fewer episodes for testing."""
        print("\n⚡ Running quick comparison mode...")

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
        return self.run_complete_comparison()


def main():
    """Main function to run baseline comparison experiments."""
    parser = argparse.ArgumentParser(description='Run baseline comparison experiments')
    parser.add_argument('--experiment-name', default='baseline_comparison',
                       help='Name of the experiment')
    parser.add_argument('--num-episodes', type=int, default=50,
                       help='Number of training episodes for RL')
    parser.add_argument('--num-eval-episodes', type=int, default=10,
                       help='Number of evaluation episodes')
    parser.add_argument('--max-steps', type=int, default=3600,
                       help='Maximum steps per episode')
    parser.add_argument('--quick-test', action='store_true',
                       help='Run quick test with minimal episodes')
    parser.add_argument('--coordination', action='store_true', default=True,
                       help='Enable coordination for multi-intersection scenario')

    args = parser.parse_args()

    # Configuration
    config = {
        'experiment_name': args.experiment_name,
        'num_episodes': args.num_episodes,
        'num_eval_episodes': args.num_eval_episodes,
        'max_steps': args.max_steps,
        'coordination': args.coordination,
        'traffic_demand': 0.15,
        'step_length': 1.0,
        'results_dir': './results/baseline_comparison/',
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
    runner = BaselineComparisonRunner(config)

    if args.quick_test:
        results = runner.run_quick_comparison()
    else:
        results = runner.run_complete_comparison()

    # Print final summary
    print("\n" + "="*70)
    print("🎉 BASELINE COMPARISON COMPLETED!")
    print("="*70)

    # Single intersection rankings
    single_controllers = results['single_intersection']['controllers']
    single_rankings = results['comparison']['single_intersection_rankings']
    print("\n📊 SINGLE INTERSECTION RANKINGS:")
    print(f"  🥇 Best Reward: {single_rankings['best_reward']}")
    print(f"  🥉 Worst Reward: {single_rankings['worst_reward']}")
    print(f"  📋 Order: {', '.join(single_rankings['reward_order'])}")

    # Multi-intersection rankings
    multi_controllers = results['multi_intersection']['controllers']
    multi_rankings = results['comparison']['multi_intersection_rankings']
    print("\n📊 MULTI-INTERSECTION RANKINGS:")
    print(f"  🥇 Best Reward: {multi_rankings['best_reward']}")
    print(f"  🥉 Worst Reward: {multi_rankings['worst_reward']}")
    print(f"  📋 Order: {', '.join(multi_rankings['reward_order'])}")

    # Performance comparison
    if 'DQN' in single_controllers and 'DQN' in multi_controllers:
        dqn_single = single_controllers['DQN']['eval_avg_reward']
        dqn_multi = multi_controllers['DQN']['eval_avg_reward']
        rl_improvement = results['comparison']['improvements']['rl_scalability']

        print(f"\n🚀 RL SCALABILITY ANALYSIS:")
        print(f"  Single Intersection: {dqn_single:,.0f} reward")
        print(f"  Multi Intersection:  {dqn_multi:,.0f} reward")
        print(f"  Change: {rl_improvement['single_to_multi_change']:+.0f} "
              f"({rl_improvement['relative_change_percent']:+.1f}%)")

    print("\n📁 Results saved to: ./results/baseline_comparison/")
    print(f"📊 Plots: {args.experiment_name}_comparison.png")


if __name__ == '__main__':
    main()
