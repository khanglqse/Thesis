"""
Main experiment runner for training and evaluating traffic light control agents.
"""

import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional, Any
from tqdm import tqdm
import argparse

from environment.traffic_env import create_env
from agents.dqn_agent import create_dqn_agent
from agents.ppo_agent import create_ppo_agent
from agents.baseline_controllers import (
    create_fixed_time_controller,
    create_actuated_controller,
    create_adaptive_controller,
    create_random_controller
)


class ExperimentRunner:
    """
    Main class for running traffic light control experiments.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration
        """
        self.config = config or {}

        # Experiment settings
        self.experiment_name = self.config.get('experiment_name', 'traffic_control_experiment')
        self.num_episodes = self.config.get('num_episodes', 10)
        self.max_steps_per_episode = self.config.get('max_steps_per_episode', 3600)
        self.eval_episodes = self.config.get('eval_episodes', 5)
        self.save_models = self.config.get('save_models', True)
        self.save_results = self.config.get('save_results', True)
        self.results_dir = self.config.get('results_dir', './results/')

        # Environment settings
        self.env_config = self.config.get('env_config', {})
        self.use_gui = self.config.get('use_gui', False)

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

        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)

        # Results storage
        self.results = {}

    def create_environment(self):
        """Create traffic environment."""
        return create_env(use_gui=self.use_gui, **self.env_config)

    def create_agents(self, env):
        """Create all agents for comparison."""
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n

        agents = {}

        # RL Agents
        if self.config.get('train_dqn', True):
            agents['dqn'] = create_dqn_agent(state_dim, action_dim, **self.dqn_config)

        if self.config.get('train_ppo', False):
            agents['ppo'] = create_ppo_agent(env, config=self.ppo_config)

        # Baselines
        for baseline_name in self.baseline_configs.keys():
            if self.config.get(f'use_{baseline_name}', True):
                if baseline_name == 'fixed_time':
                    agents[baseline_name] = create_fixed_time_controller(**self.baseline_configs[baseline_name])
                elif baseline_name == 'actuated':
                    agents[baseline_name] = create_actuated_controller(**self.baseline_configs[baseline_name])
                elif baseline_name == 'adaptive':
                    agents[baseline_name] = create_adaptive_controller(**self.baseline_configs[baseline_name])
                elif baseline_name == 'random':
                    agents[baseline_name] = create_random_controller(**self.baseline_configs[baseline_name])

        return agents

    def train_agent(self, agent, env, agent_name: str) -> Dict[str, List[float]]:
        """
        Train a single agent.

        Args:
            agent: Agent to train
            env: Training environment
            agent_name: Name of the agent

        Returns:
            Training statistics
        """
        print(f"\nTraining {agent_name}...")

        episode_rewards = []
        episode_lengths = []
        episode_waiting_times = []
        episode_throughputs = []

        for episode in tqdm(range(self.num_episodes), desc=f"Training {agent_name}"):
            state, _ = env.reset()
            episode_reward = 0
            episode_waiting_time = 0
            episode_throughput = 0
            done = False
            truncated = False

            while not (done or truncated):
                # Select action
                action = agent.select_action(state)

                # Execute action
                next_state, reward, done, truncated, info = env.step(action)

                # Store experience (for RL agents)
                if hasattr(agent, 'store_experience'):
                    agent.store_experience(state, action, reward, next_state, done)

                # Update model (for RL agents)
                if hasattr(agent, 'update_model'):
                    agent.update_model()

                # Update epsilon (for DQN)
                if hasattr(agent, 'update_epsilon'):
                    agent.update_epsilon()

                # Accumulate metrics
                episode_reward += reward

                # Get waiting time from info if available
                if 'total_waiting_time' in info:
                    episode_waiting_time += info['total_waiting_time']

                if 'throughput' in info:
                    episode_throughput += info['throughput']

                state = next_state

            # Store episode statistics
            episode_rewards.append(episode_reward)
            episode_lengths.append(env.current_step)
            episode_waiting_times.append(episode_waiting_time)
            episode_throughputs.append(episode_throughput)

        # Save model if requested
        if self.save_models and hasattr(agent, 'save_model'):
            model_path = os.path.join(self.results_dir, f'{agent_name}_model.zip')
            agent.save_model(model_path)

        return {
            'rewards': episode_rewards,
            'lengths': episode_lengths,
            'waiting_times': episode_waiting_times,
            'throughputs': episode_throughputs
        }

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
        episode_lengths = []
        episode_waiting_times = []
        episode_throughputs = []

        for episode in tqdm(range(self.eval_episodes), desc=f"Evaluating {agent_name}"):
            state, _ = env.reset()
            episode_reward = 0
            episode_waiting_time = 0
            episode_throughput = 0
            done = False
            truncated = False

            while not (done or truncated):
                # Select action (no exploration for evaluation)
                if hasattr(agent, 'set_training_mode'):
                    agent.set_training_mode(False)

                action = agent.select_action(state)

                # Execute action
                next_state, reward, done, truncated, info = env.step(action)

                # Accumulate metrics
                episode_reward += reward

                # Get metrics from info if available
                if 'total_waiting_time' in info:
                    episode_waiting_time += info['total_waiting_time']

                if 'throughput' in info:
                    episode_throughput += info['throughput']

                state = next_state

            # Store episode statistics
            episode_rewards.append(episode_reward)
            episode_lengths.append(env.current_step)
            episode_waiting_times.append(episode_waiting_time)
            episode_throughputs.append(episode_throughput)

        # Calculate average metrics
        avg_reward = np.mean(episode_rewards)
        avg_waiting_time = np.mean(episode_waiting_times)
        avg_throughput = np.mean(episode_throughputs)
        avg_length = np.mean(episode_lengths)

        return {
            'avg_reward': avg_reward,
            'avg_waiting_time': avg_waiting_time,
            'avg_throughput': avg_throughput,
            'avg_episode_length': avg_length,
            'std_reward': np.std(episode_rewards),
            'std_waiting_time': np.std(episode_waiting_times)
        }

    def run_experiment(self):
        """Run the complete experiment."""
        print(f"Starting experiment: {self.experiment_name}")

        # Create environment
        env = self.create_environment()

        # Create agents
        agents = self.create_agents(env)

        # Train and evaluate agents
        self.results = {}

        for agent_name, agent in agents.items():
            # Reset agent for training
            if hasattr(agent, 'reset'):
                agent.reset()

            # Train agent (if it's an RL agent)
            if agent_name in ['dqn', 'ppo']:
                training_stats = self.train_agent(agent, env, agent_name)
                self.results[f'{agent_name}_training'] = training_stats

            # Evaluate agent
            eval_metrics = self.evaluate_agent(agent, env, agent_name)
            self.results[f'{agent_name}_evaluation'] = eval_metrics

            print(f"{agent_name} - Avg Reward: {eval_metrics['avg_reward']:.2f}, "
                  f"Avg Waiting Time: {eval_metrics['avg_waiting_time']:.2f}, "
                  f"Avg Throughput: {eval_metrics['avg_throughput']:.2f}")

        # Save results
        if self.save_results:
            self.save_results_to_file()

        # Close environment
        env.close()

        print(f"\nExperiment {self.experiment_name} completed!")
        return self.results

    def save_results_to_file(self):
        """Save experiment results to files."""
        # Save results as JSON
        results_file = os.path.join(self.results_dir, f'{self.experiment_name}_results.json')
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        # Save results as CSV for easy analysis
        summary_data = []
        for key, value in self.results.items():
            if isinstance(value, dict) and 'avg_reward' in value:
                summary_data.append({
                    'agent': key.replace('_evaluation', ''),
                    'avg_reward': value['avg_reward'],
                    'avg_waiting_time': value['avg_waiting_time'],
                    'avg_throughput': value['avg_throughput'],
                    'avg_episode_length': value['avg_episode_length']
                })

        if summary_data:
            df = pd.DataFrame(summary_data)
            csv_file = os.path.join(self.results_dir, f'{self.experiment_name}_summary.csv')
            df.to_csv(csv_file, index=False)

        print(f"Results saved to {self.results_dir}")


def run_single_experiment(config_file: str = None, **kwargs):
    """
    Run a single experiment with given configuration.

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

    # Create and run experiment
    runner = ExperimentRunner(config)
    results = runner.run_experiment()

    return results


def run_parameter_sweep(parameter_configs: List[Dict], base_config: Dict = None):
    """
    Run multiple experiments with different parameter configurations.

    Args:
        parameter_configs: List of parameter configurations to test
        base_config: Base configuration for all experiments
    """
    if base_config is None:
        base_config = {}

    all_results = {}

    for i, param_config in enumerate(parameter_configs):
        print(f"\n{'='*50}")
        print(f"Running experiment {i+1}/{len(parameter_configs)}")
        print(f"Parameters: {param_config}")
        print(f"{'='*50}")

        # Merge configurations
        config = base_config.copy()
        config.update(param_config)
        config['experiment_name'] = f"experiment_{i+1}"

        # Run experiment
        runner = ExperimentRunner(config)
        results = runner.run_experiment()
        all_results[f'experiment_{i+1}'] = results

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Traffic Light Control Experiment Runner')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--experiment_name', type=str, default='traffic_control_experiment',
                       help='Name of the experiment')
    parser.add_argument('--num_episodes', type=int, default=10, help='Number of training episodes')
    parser.add_argument('--eval_episodes', type=int, default=5, help='Number of evaluation episodes')
    parser.add_argument('--max_steps', type=int, default=3600, help='Maximum steps per episode')
    parser.add_argument('--use_gui', action='store_true', help='Use SUMO GUI')
    parser.add_argument('--train_dqn', action='store_true', default=True, help='Train DQN agent')
    parser.add_argument('--train_ppo', action='store_true', help='Train PPO agent')
    parser.add_argument('--no_baselines', action='store_true', help='Skip baseline controllers')

    args = parser.parse_args()

    # Create configuration
    config = {
        'experiment_name': args.experiment_name,
        'num_episodes': args.num_episodes,
        'eval_episodes': args.eval_episodes,
        'max_steps_per_episode': args.max_steps,
        'use_gui': args.use_gui,
        'train_dqn': args.train_dqn,
        'train_ppo': args.train_ppo,
        'use_fixed_time': not args.no_baselines,
        'use_actuated': not args.no_baselines,
        'use_adaptive': not args.no_baselines,
        'use_random': not args.no_baselines
    }

    # Run experiment
    results = run_single_experiment(args.config, **config)
    print("\nExperiment completed successfully!")
