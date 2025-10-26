"""
Visualization utilities for traffic light control experiment results.
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Any
import argparse
from pathlib import Path

# Set style for plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class ResultsVisualizer:
    """
    Visualizer for traffic light control experiment results.
    """

    def __init__(self, results_dir: str = './results/'):
        """
        Initialize results visualizer.

        Args:
            results_dir: Directory containing experiment results
        """
        self.results_dir = Path(results_dir)
        self.figures_dir = self.results_dir / 'figures'
        self.figures_dir.mkdir(exist_ok=True)

    def load_results(self, experiment_name: str) -> Dict[str, Any]:
        """
        Load experiment results.

        Args:
            experiment_name: Name of the experiment

        Returns:
            Loaded results dictionary
        """
        results_file = self.results_dir / f'{experiment_name}_results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Results file not found: {results_file}")

    def load_summary(self, experiment_name: str) -> pd.DataFrame:
        """
        Load experiment summary.

        Args:
            experiment_name: Name of the experiment

        Returns:
            Summary DataFrame
        """
        summary_file = self.results_dir / f'{experiment_name}_summary.csv'
        if summary_file.exists():
            return pd.read_csv(summary_file)
        else:
            raise FileNotFoundError(f"Summary file not found: {summary_file}")

    def plot_training_curves(self, results: Dict[str, Any], save: bool = True):
        """
        Plot training curves for RL agents.

        Args:
            results: Experiment results
            save: Whether to save the plot
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Training Progress', fontsize=16)

        # Training rewards
        ax1 = axes[0, 0]
        for agent_name in ['dqn', 'ppo']:
            if f'{agent_name}_training' in results:
                rewards = results[f'{agent_name}_training']['rewards']
                episodes = range(1, len(rewards) + 1)
                ax1.plot(episodes, rewards, label=agent_name.upper(), linewidth=2)

        ax1.set_xlabel('Episode')
        ax1.set_ylabel('Total Reward')
        ax1.set_title('Training Rewards')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Training episode lengths
        ax2 = axes[0, 1]
        for agent_name in ['dqn', 'ppo']:
            if f'{agent_name}_training' in results:
                lengths = results[f'{agent_name}_training']['lengths']
                episodes = range(1, len(lengths) + 1)
                ax2.plot(episodes, lengths, label=agent_name.upper(), linewidth=2)

        ax2.set_xlabel('Episode')
        ax2.set_ylabel('Episode Length')
        ax2.set_title('Episode Lengths')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Training waiting times
        ax3 = axes[1, 0]
        for agent_name in ['dqn', 'ppo']:
            if f'{agent_name}_training' in results:
                waiting_times = results[f'{agent_name}_training']['waiting_times']
                episodes = range(1, len(waiting_times) + 1)
                ax3.plot(episodes, waiting_times, label=agent_name.upper(), linewidth=2)

        ax3.set_xlabel('Episode')
        ax3.set_ylabel('Total Waiting Time')
        ax3.set_title('Training Waiting Times')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Training throughputs
        ax4 = axes[1, 1]
        for agent_name in ['dqn', 'ppo']:
            if f'{agent_name}_training' in results:
                throughputs = results[f'{agent_name}_training']['throughputs']
                episodes = range(1, len(throughputs) + 1)
                ax4.plot(episodes, throughputs, label=agent_name.upper(), linewidth=2)

        ax4.set_xlabel('Episode')
        ax4.set_ylabel('Total Throughput')
        ax4.set_title('Training Throughput')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        if save:
            plot_file = self.figures_dir / 'training_curves.png'
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            print(f"Training curves saved to {plot_file}")

        plt.show()

    def plot_evaluation_comparison(self, summary_df: pd.DataFrame, save: bool = True):
        """
        Plot evaluation comparison between all controllers.

        Args:
            summary_df: Summary DataFrame with evaluation results
            save: Whether to save the plot
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Controller Performance Comparison', fontsize=16)

        # Color scheme for different controller types
        colors = {
            'dqn': '#2E86AB',
            'ppo': '#A23B72',
            'fixed_time': '#F18F01',
            'actuated': '#C73E1D',
            'adaptive': '#8B5A2B',
            'random': '#666666'
        }

        # Average Reward Comparison
        ax1 = axes[0, 0]
        agents = summary_df['agent'].tolist()
        rewards = summary_df['avg_reward'].tolist()

        bars = ax1.bar(range(len(agents)), rewards,
                      color=[colors.get(agent, '#666666') for agent in agents])

        ax1.set_xlabel('Controllers')
        ax1.set_ylabel('Average Reward')
        ax1.set_title('Average Reward Comparison')
        ax1.set_xticks(range(len(agents)))
        ax1.set_xticklabels([agent.replace('_', ' ').title() for agent in agents],
                           rotation=45, ha='right')

        # Add value labels on bars
        for bar, reward in zip(bars, rewards):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{reward:.2f}', ha='center', va='bottom')

        # Average Waiting Time Comparison
        ax2 = axes[0, 1]
        waiting_times = summary_df['avg_waiting_time'].tolist()

        bars = ax2.bar(range(len(agents)), waiting_times,
                      color=[colors.get(agent, '#666666') for agent in agents])

        ax2.set_xlabel('Controllers')
        ax2.set_ylabel('Average Waiting Time')
        ax2.set_title('Average Waiting Time Comparison')
        ax2.set_xticks(range(len(agents)))
        ax2.set_xticklabels([agent.replace('_', ' ').title() for agent in agents],
                           rotation=45, ha='right')

        for bar, waiting in zip(bars, waiting_times):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{waiting:.2f}', ha='center', va='bottom')

        # Average Episode Length Comparison
        ax3 = axes[1, 0]
        episode_lengths = summary_df['avg_episode_length'].tolist()

        bars = ax3.bar(range(len(agents)), episode_lengths,
                      color=[colors.get(agent, '#666666') for agent in agents])

        ax3.set_xlabel('Controllers')
        ax3.set_ylabel('Average Episode Length')
        ax3.set_title('Average Episode Length Comparison')
        ax3.set_xticks(range(len(agents)))
        ax3.set_xticklabels([agent.replace('_', ' ').title() for agent in agents],
                           rotation=45, ha='right')

        for bar, length in zip(bars, episode_lengths):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{length:.0f}', ha='center', va='bottom')

        # Average Throughput Comparison
        ax4 = axes[1, 1]
        throughputs = summary_df['avg_throughput'].tolist()

        bars = ax4.bar(range(len(agents)), throughputs,
                      color=[colors.get(agent, '#666666') for agent in agents])

        ax4.set_xlabel('Controllers')
        ax4.set_ylabel('Average Throughput')
        ax4.set_title('Average Throughput Comparison')
        ax4.set_xticks(range(len(agents)))
        ax4.set_xticklabels([agent.replace('_', ' ').title() for agent in agents],
                           rotation=45, ha='right')

        for bar, throughput in zip(bars, throughputs):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{throughput:.2f}', ha='center', va='bottom')

        plt.tight_layout()

        if save:
            plot_file = self.figures_dir / 'evaluation_comparison.png'
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            pdf_file = self.figures_dir / 'evaluation_comparison.pdf'
            plt.savefig(pdf_file, dpi=300, bbox_inches='tight')
            print(f"Comparison plots saved to {self.figures_dir}")

        plt.show()

    def plot_reward_distribution(self, results: Dict[str, Any], save: bool = True):
        """
        Plot reward distributions for all controllers.

        Args:
            results: Experiment results
            save: Whether to save the plot
        """
        fig, ax = plt.subplots(figsize=(12, 8))
        fig.suptitle('Reward Distribution Comparison', fontsize=16)

        all_rewards = []
        agent_names = []

        for agent_name, agent_results in results.items():
            if '_evaluation' in agent_name and 'rewards' in agent_results:
                rewards = agent_results['rewards']
                all_rewards.extend(rewards)
                agent_names.extend([agent_name.replace('_evaluation', '')] * len(rewards))

        # Create DataFrame for plotting
        df = pd.DataFrame({
            'Reward': all_rewards,
            'Controller': agent_names
        })

        # Box plot
        sns.boxplot(data=df, x='Controller', y='Reward', ax=ax)
        ax.set_xlabel('Controllers')
        ax.set_ylabel('Reward')
        ax.set_title('Reward Distribution by Controller')
        ax.tick_params(axis='x', rotation=45)

        # Add individual points with some transparency
        sns.stripplot(data=df, x='Controller', y='Reward', ax=ax,
                     color='black', alpha=0.3, size=3)

        plt.tight_layout()

        if save:
            plot_file = self.figures_dir / 'reward_distribution.png'
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            pdf_file = self.figures_dir / 'reward_distribution.pdf'
            plt.savefig(pdf_file, dpi=300, bbox_inches='tight')

        plt.show()

    def plot_waiting_time_trends(self, results: Dict[str, Any], save: bool = True):
        """
        Plot waiting time trends over episodes for training.

        Args:
            results: Experiment results
            save: Whether to save the plot
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.suptitle('Waiting Time Trends During Training', fontsize=16)

        for agent_name in ['dqn', 'ppo']:
            if f'{agent_name}_training' in results:
                waiting_times = results[f'{agent_name}_training']['waiting_times']
                episodes = range(1, len(waiting_times) + 1)

                # Calculate moving average for smoother trends
                window = min(10, len(waiting_times) // 5)
                if window > 1:
                    moving_avg = pd.Series(waiting_times).rolling(window=window).mean()
                    ax.plot(episodes, moving_avg, label=f'{agent_name.upper()} (Moving Avg)',
                           linewidth=3, alpha=0.8)

                ax.scatter(episodes, waiting_times, label=f'{agent_name.upper()} (Raw)',
                          alpha=0.6, s=10)

        ax.set_xlabel('Episode')
        ax.set_ylabel('Total Waiting Time')
        ax.set_title('Waiting Time Trends')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save:
            plot_file = self.figures_dir / 'waiting_time_trends.png'
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            pdf_file = self.figures_dir / 'waiting_time_trends.pdf'
            plt.savefig(pdf_file, dpi=300, bbox_inches='tight')

        plt.show()

    def create_summary_table(self, summary_df: pd.DataFrame, save: bool = True) -> str:
        """
        Create a LaTeX table from summary results.

        Args:
            summary_df: Summary DataFrame
            save: Whether to save the table

        Returns:
            LaTeX table string
        """
        # Format the data for LaTeX
        latex_df = summary_df.copy()
        latex_df['Controller'] = latex_df['agent'].str.replace('_', ' ').str.title()
        latex_df = latex_df.drop('agent', axis=1)

        # Round numerical values
        for col in latex_df.columns:
            if col != 'Controller':
                latex_df[col] = latex_df[col].round(2)

        # Create LaTeX table
        latex_table = latex_df.to_latex(
            index=False,
            caption='Performance Comparison of Traffic Light Controllers',
            label='tab:performance_comparison',
            float_format='%.2f',
            column_format='lcccc',
            escape=False
        )

        if save:
            table_file = self.figures_dir / 'performance_table.tex'
            with open(table_file, 'w') as f:
                f.write(latex_table)
            print(f"LaTeX table saved to {table_file}")

        return latex_table

    def generate_all_plots(self, experiment_name: str):
        """
        Generate all plots for the experiment.

        Args:
            experiment_name: Name of the experiment
        """
        print(f"Generating plots for experiment: {experiment_name}")

        try:
            # Load results
            results = self.load_results(experiment_name)
            summary_df = self.load_summary(experiment_name)

            # Generate plots
            self.plot_training_curves(results)
            self.plot_evaluation_comparison(summary_df)
            self.plot_reward_distribution(results)
            self.plot_waiting_time_trends(results)

            # Generate LaTeX table
            self.create_summary_table(summary_df)

            print(f"All plots generated successfully for {experiment_name}")

        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Make sure experiment results exist before generating plots.")


def generate_figures(results_dir: str = './results/', experiment_name: str = None):
    """
    Generate all figures for experiments.

    Args:
        results_dir: Directory containing results
        experiment_name: Specific experiment name (if None, generate for all)
    """
    visualizer = ResultsVisualizer(results_dir)

    if experiment_name:
        visualizer.generate_all_plots(experiment_name)
    else:
        # Find all experiment result files
        result_files = list(visualizer.results_dir.glob('*_results.json'))
        experiment_names = [f.stem.replace('_results', '') for f in result_files]

        for exp_name in experiment_names:
            try:
                visualizer.generate_all_plots(exp_name)
            except Exception as e:
                print(f"Error generating plots for {exp_name}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate plots for traffic light control experiments')
    parser.add_argument('--results_dir', type=str, default='./results/',
                       help='Directory containing experiment results')
    parser.add_argument('--experiment_name', type=str,
                       help='Specific experiment name to plot (if not provided, plots all)')

    args = parser.parse_args()

    generate_figures(args.results_dir, args.experiment_name)
