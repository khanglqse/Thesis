"""
Script for evaluating baseline traffic controllers against RL agents.
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Any
import argparse

from environment.traffic_env import create_env
from agents.baseline_controllers import (
    create_fixed_time_controller,
    create_actuated_controller,
    create_adaptive_controller,
    create_random_controller
)
from agents.dqn_agent import create_dqn_agent
from agents.ppo_agent import create_ppo_agent

# Set style for plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class BaselineEvaluator:
    """
    Evaluator for comparing baseline controllers with RL agents.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize baseline evaluator.

        Args:
            config: Evaluation configuration
        """
        self.config = config or {}

        # Evaluation settings
        self.num_episodes = self.config.get('num_episodes', 10)
        self.max_steps_per_episode = self.config.get('max_steps_per_episode', 3600)
        self.use_gui = self.config.get('use_gui', False)

        # Environment settings
        self.env_config = self.config.get('env_config', {})

        # Agent configurations
        self.dqn_config = self.config.get('dqn_config', {})
        self.ppo_config = self.config.get('ppo_config', {})

        # Baseline configurations
        self.baseline_configs = self.config.get('baseline_configs', {
            'fixed_time': {'phase_duration': 30},
            'actuated': {'threshold': 10.0},
            'adaptive': {'base_green_time': 20},
            'random': {}
        })

        # Results directory
        self.results_dir = self.config.get('results_dir', './results/')
        os.makedirs(self.results_dir, exist_ok=True)

    def create_environment(self):
        """Create evaluation environment."""
        return create_env(use_gui=self.use_gui, **self.env_config)

    def load_agents(self, env):
        """Load trained RL agents if available."""
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n

        agents = {}

        # Try to load trained models
        for agent_name in ['dqn', 'ppo']:
            model_path = os.path.join(self.results_dir, f'{agent_name}_model.zip')
            if os.path.exists(model_path):
                if agent_name == 'dqn':
                    agent = create_dqn_agent(state_dim, action_dim, **self.dqn_config)
                    agent.load_model(model_path)
                    agent.set_training_mode(False)  # Evaluation mode
                else:  # ppo
                    agent = create_ppo_agent(env, **self.ppo_config)
                    agent.load_model(model_path)
                    agent.set_training_mode(False)  # Evaluation mode

                agents[agent_name] = agent
                print(f"Loaded trained {agent_name} model")
            else:
                print(f"Trained {agent_name} model not found at {model_path}")

        return agents

    def create_baseline_agents(self):
        """Create baseline controller agents."""
        agents = {}

        for baseline_name, baseline_config in self.baseline_configs.items():
            if baseline_name == 'fixed_time':
                agents[baseline_name] = create_fixed_time_controller(**baseline_config)
            elif baseline_name == 'actuated':
                agents[baseline_name] = create_actuated_controller(**baseline_config)
            elif baseline_name == 'adaptive':
                agents[baseline_name] = create_adaptive_controller(**baseline_config)
            elif baseline_name == 'random':
                agents[baseline_name] = create_random_controller(**baseline_config)

        return agents

    def evaluate_agent(self, agent, env, agent_name: str) -> Dict[str, float]:
        """
        Evaluate a single agent.

        Args:
            agent: Agent to evaluate
            env: Evaluation environment
            agent_name: Name of the agent

        Returns:
            Evaluation metrics
        """
        print(f"Evaluating {agent_name}...")

        episode_rewards = []
        episode_waiting_times = []
        episode_queue_lengths = []
        episode_throughputs = []

        for episode in range(self.num_episodes):
            state, _ = env.reset()

            if hasattr(agent, 'reset'):
                agent.reset()

            episode_reward = 0
            episode_waiting_time = 0
            episode_queue_length = 0
            episode_throughput = 0
            done = False
            truncated = False

            while not (done or truncated):
                # Select action
                action = agent.select_action(state)

                # Execute action
                next_state, reward, done, truncated, info = env.step(action)

                # Accumulate metrics
                episode_reward += reward

                # Extract metrics from info or calculate them
                if 'total_waiting_time' in info:
                    episode_waiting_time += info['total_waiting_time']
                else:
                    # Estimate from state (this is a simplified calculation)
                    waiting_time = np.sum(state[8:16])  # Assuming waiting times are in indices 8-15
                    episode_waiting_time += waiting_time

                if 'total_queue_length' in info:
                    episode_queue_length += info['total_queue_length']
                else:
                    # Estimate from state (this is a simplified calculation)
                    queue_length = np.sum(state[0:8])  # Assuming queue lengths are in indices 0-7
                    episode_queue_length += queue_length

                if 'throughput' in info:
                    episode_throughput += info['throughput']

                state = next_state

            # Store episode statistics
            episode_rewards.append(episode_reward)
            episode_waiting_times.append(episode_waiting_time)
            episode_queue_lengths.append(episode_queue_length)
            episode_throughputs.append(episode_throughput)

        # Calculate average metrics
        return {
            'agent': agent_name,
            'avg_reward': np.mean(episode_rewards),
            'std_reward': np.std(episode_rewards),
            'avg_waiting_time': np.mean(episode_waiting_times),
            'std_waiting_time': np.std(episode_waiting_times),
            'avg_queue_length': np.mean(episode_queue_lengths),
            'std_queue_length': np.std(episode_queue_lengths),
            'avg_throughput': np.mean(episode_throughputs),
            'std_throughput': np.std(episode_throughputs),
            'rewards': episode_rewards,
            'waiting_times': episode_waiting_times,
            'queue_lengths': episode_queue_lengths,
            'throughputs': episode_throughputs
        }

    def run_evaluation(self) -> Dict[str, Any]:
        """
        Run complete baseline evaluation.

        Returns:
            Evaluation results
        """
        print("Starting baseline evaluation...")

        # Create environment
        env = self.create_environment()

        # Load RL agents if available
        rl_agents = self.load_agents(env)

        # Create baseline agents
        baseline_agents = self.create_baseline_agents()

        # Combine all agents
        all_agents = {**rl_agents, **baseline_agents}

        # Evaluate all agents
        results = {}
        for agent_name, agent in all_agents.items():
            agent_results = self.evaluate_agent(agent, env, agent_name)
            results[agent_name] = agent_results

            print(f"{agent_name:15} | Reward: {agent_results['avg_reward']:8.2f} ± {agent_results['std_reward']:.2f} | "
                  f"Waiting: {agent_results['avg_waiting_time']:8.2f} ± {agent_results['std_waiting_time']:.2f}")

        # Save results
        self.save_results(results)

        # Create comparison plots
        self.create_comparison_plots(results)

        # Close environment
        env.close()

        print(f"\nEvaluation completed! Results saved to {self.results_dir}")
        return results

    def save_results(self, results: Dict[str, Any]):
        """Save evaluation results to files."""
        # Save detailed results as JSON
        results_file = os.path.join(self.results_dir, 'baseline_evaluation_results.json')
        with open(results_file, 'w') as f:
            # Convert numpy arrays to lists for JSON serialization
            serializable_results = {}
            for agent_name, agent_results in results.items():
                serializable_results[agent_name] = {
                    k: (v.tolist() if hasattr(v, 'tolist') else v)
                    for k, v in agent_results.items()
                }
            json.dump(serializable_results, f, indent=2)

        # Save summary as CSV
        summary_data = []
        for agent_name, agent_results in results.items():
            summary_data.append({
                'agent': agent_name,
                'avg_reward': agent_results['avg_reward'],
                'std_reward': agent_results['std_reward'],
                'avg_waiting_time': agent_results['avg_waiting_time'],
                'std_waiting_time': agent_results['std_waiting_time'],
                'avg_queue_length': agent_results['avg_queue_length'],
                'std_queue_length': agent_results['std_queue_length'],
                'avg_throughput': agent_results['avg_throughput'],
                'std_throughput': agent_results['std_throughput']
            })

        df = pd.DataFrame(summary_data)
        csv_file = os.path.join(self.results_dir, 'baseline_evaluation_summary.csv')
        df.to_csv(csv_file, index=False)

    def create_comparison_plots(self, results: Dict[str, Any]):
        """Create comparison plots for all metrics."""
        # Set up the plotting style
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Traffic Light Controller Performance Comparison', fontsize=16)

        # Colors for different agent types
        agent_types = {
            'dqn': 'RL Agents',
            'ppo': 'RL Agents',
            'fixed_time': 'Traditional Controllers',
            'actuated': 'Traditional Controllers',
            'adaptive': 'Traditional Controllers',
            'random': 'Traditional Controllers'
        }

        colors = {
            'RL Agents': '#2E86AB',
            'Traditional Controllers': '#A23B72'
        }

        # 1. Average Reward Comparison
        ax1 = axes[0, 0]
        agent_names = list(results.keys())
        avg_rewards = [results[name]['avg_reward'] for name in agent_names]

        bars = ax1.bar(range(len(agent_names)), avg_rewards,
                      color=[colors[agent_types.get(name, 'Traditional Controllers')] for name in agent_names])
        ax1.set_xlabel('Controllers')
        ax1.set_ylabel('Average Reward')
        ax1.set_title('Average Reward Comparison')
        ax1.set_xticks(range(len(agent_names)))
        ax1.set_xticklabels(agent_names, rotation=45, ha='right')

        # Add value labels on bars
        for bar, reward in zip(bars, avg_rewards):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{reward:.2f}', ha='center', va='bottom')

        # 2. Average Waiting Time Comparison
        ax2 = axes[0, 1]
        avg_waiting = [results[name]['avg_waiting_time'] for name in agent_names]

        bars = ax2.bar(range(len(agent_names)), avg_waiting,
                      color=[colors[agent_types.get(name, 'Traditional Controllers')] for name in agent_names])
        ax2.set_xlabel('Controllers')
        ax2.set_ylabel('Average Waiting Time')
        ax2.set_title('Average Waiting Time Comparison')
        ax2.set_xticks(range(len(agent_names)))
        ax2.set_xticklabels(agent_names, rotation=45, ha='right')

        for bar, waiting in zip(bars, avg_waiting):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{waiting:.2f}', ha='center', va='bottom')

        # 3. Average Queue Length Comparison
        ax3 = axes[1, 0]
        avg_queues = [results[name]['avg_queue_length'] for name in agent_names]

        bars = ax3.bar(range(len(agent_names)), avg_queues,
                      color=[colors[agent_types.get(name, 'Traditional Controllers')] for name in agent_names])
        ax3.set_xlabel('Controllers')
        ax3.set_ylabel('Average Queue Length')
        ax3.set_title('Average Queue Length Comparison')
        ax3.set_xticks(range(len(agent_names)))
        ax3.set_xticklabels(agent_names, rotation=45, ha='right')

        for bar, queue in zip(bars, avg_queues):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{queue:.2f}', ha='center', va='bottom')

        # 4. Average Throughput Comparison
        ax4 = axes[1, 1]
        avg_throughputs = [results[name]['avg_throughput'] for name in agent_names]

        bars = ax4.bar(range(len(agent_names)), avg_throughputs,
                      color=[colors[agent_types.get(name, 'Traditional Controllers')] for name in agent_names])
        ax4.set_xlabel('Controllers')
        ax4.set_ylabel('Average Throughput')
        ax4.set_title('Average Throughput Comparison')
        ax4.set_xticks(range(len(agent_names)))
        ax4.set_xticklabels(agent_names, rotation=45, ha='right')

        for bar, throughput in zip(bars, avg_throughputs):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{throughput:.2f}', ha='center', va='bottom')

        plt.tight_layout()

        # Save plot
        plot_file = os.path.join(self.results_dir, 'baseline_comparison.png')
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        print(f"Comparison plot saved to {plot_file}")

        # Also save as PDF for LaTeX
        pdf_file = os.path.join(self.results_dir, 'baseline_comparison.pdf')
        plt.savefig(pdf_file, dpi=300, bbox_inches='tight')


def run_evaluation(config_file: str = None, **kwargs):
    """
    Run baseline evaluation with given configuration.

    Args:
        config_file: Path to configuration file
        **kwargs: Override configuration parameters
    """
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    # Update config with kwargs
    config.update(kwargs)

    # Create and run evaluation
    evaluator = BaselineEvaluator(config)
    results = evaluator.run_evaluation()

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Baseline Controller Evaluation')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--num_episodes', type=int, default=10, help='Number of evaluation episodes')
    parser.add_argument('--max_steps', type=int, default=3600, help='Maximum steps per episode')
    parser.add_argument('--use_gui', action='store_true', help='Use SUMO GUI')
    parser.add_argument('--results_dir', type=str, default='./results/', help='Results directory')

    args = parser.parse_args()

    # Create configuration
    config = {
        'num_episodes': args.num_episodes,
        'max_steps_per_episode': args.max_steps,
        'use_gui': args.use_gui,
        'results_dir': args.results_dir
    }

    # Run evaluation
    results = run_evaluation(args.config, **config)
    print("\nBaseline evaluation completed successfully!")
