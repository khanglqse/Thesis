#!/usr/bin/env python3
"""
Comprehensive Visualization Script for Thesis
==============================================
This script generates professional visualizations for comparing
traffic light control methods in the thesis.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Optional

# Set style for professional plots
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class ThesisVisualizer:
    """Generate visualizations for thesis presentation."""
    
    def __init__(self, results_dir: str = "./results/"):
        """
        Initialize visualizer.
        
        Args:
            results_dir: Directory containing results
        """
        self.results_dir = results_dir
        self.figures_dir = os.path.join(results_dir, 'figures')
        os.makedirs(self.figures_dir, exist_ok=True)
        
        self.results_data = None
        self.summary_df = None
    
    def load_results(self):
        """Load results from files."""
        print("Loading results...")
        
        # Load JSON results
        json_path = os.path.join(self.results_dir, 'comprehensive_study_results.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                self.results_data = json.load(f)
            print(f"✓ Loaded JSON results: {json_path}")
        else:
            print(f"✗ JSON results not found: {json_path}")
            return False
        
        # Load CSV summary
        csv_path = os.path.join(self.results_dir, 'comprehensive_study_summary.csv')
        if os.path.exists(csv_path):
            self.summary_df = pd.read_csv(csv_path)
            print(f"✓ Loaded CSV summary: {csv_path}")
        else:
            print(f"✗ CSV summary not found: {csv_path}")
            return False
        
        return True
    
    def plot_performance_comparison(self):
        """Plot performance comparison bar chart."""
        print("\nGenerating performance comparison chart...")
        
        if self.summary_df is None:
            print("✗ No data available")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Traffic Control Performance Comparison', 
                     fontsize=16, fontweight='bold')
        
        # Prepare data
        agents = self.summary_df['Agent Name'].tolist()
        colors = ['#ff6b6b' if t == 'Baseline' else '#4ecdc4' 
                  for t in self.summary_df['Agent Type']]
        
        # Plot 1: Average Reward
        ax1 = axes[0, 0]
        bars1 = ax1.bar(agents, self.summary_df['Avg Reward'], color=colors, alpha=0.7)
        ax1.set_ylabel('Average Reward', fontsize=12)
        ax1.set_title('Average Reward (Higher is Better)', fontsize=12, fontweight='bold')
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 2: Average Waiting Time
        ax2 = axes[0, 1]
        bars2 = ax2.bar(agents, self.summary_df['Avg Waiting Time'], color=colors, alpha=0.7)
        ax2.set_ylabel('Average Waiting Time (s)', fontsize=12)
        ax2.set_title('Average Waiting Time (Lower is Better)', fontsize=12, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(axis='y', alpha=0.3)
        
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 3: Average Throughput
        ax3 = axes[1, 0]
        bars3 = ax3.bar(agents, self.summary_df['Avg Throughput'], color=colors, alpha=0.7)
        ax3.set_ylabel('Average Throughput', fontsize=12)
        ax3.set_title('Average Throughput (Higher is Better)', fontsize=12, fontweight='bold')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(axis='y', alpha=0.3)
        
        for bar in bars3:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 4: Training Time Comparison
        ax4 = axes[1, 1]
        training_times = self.summary_df['Training Time (s)'].tolist()
        bars4 = ax4.bar(agents, training_times, color=colors, alpha=0.7)
        ax4.set_ylabel('Training Time (seconds)', fontsize=12)
        ax4.set_title('Training Time Comparison', fontsize=12, fontweight='bold')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(axis='y', alpha=0.3)
        
        for bar in bars4:
            height = bar.get_height()
            if height > 0:
                ax4.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.0f}',
                        ha='center', va='bottom', fontsize=9)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#ff6b6b', alpha=0.7, label='Baseline Methods'),
            Patch(facecolor='#4ecdc4', alpha=0.7, label='RL Methods')
        ]
        fig.legend(handles=legend_elements, loc='upper right', fontsize=11)
        
        plt.tight_layout()
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'performance_comparison.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_improvement_metrics(self):
        """Plot improvement percentages of RL vs baselines."""
        print("\nGenerating improvement metrics chart...")
        
        if not self.results_data or 'comparison' not in self.results_data:
            print("✗ No comparison data available")
            return
        
        comparison = self.results_data['comparison']
        
        if not comparison:
            print("✗ No comparison data found")
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Prepare data
        agents = list(comparison.keys())
        metrics = ['avg_reward_improvement', 'avg_waiting_time_improvement', 
                   'avg_throughput_improvement']
        metric_labels = ['Reward', 'Waiting Time Reduction', 'Throughput']
        
        x = np.arange(len(agents))
        width = 0.25
        
        colors_map = ['#4ecdc4', '#95e1d3', '#f38181']
        
        for i, (metric, label) in enumerate(zip(metrics, metric_labels)):
            values = [comparison[agent].get(metric, 0) for agent in agents]
            bars = ax.bar(x + i * width, values, width, label=label, 
                         color=colors_map[i], alpha=0.8)
            
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:+.1f}%',
                       ha='center', va='bottom' if height >= 0 else 'top', 
                       fontsize=9, fontweight='bold')
        
        ax.set_xlabel('RL Agent', fontsize=13, fontweight='bold')
        ax.set_ylabel('Improvement vs Fixed-Time Baseline (%)', fontsize=13, fontweight='bold')
        ax.set_title('Performance Improvement: RL Agents vs Traditional Fixed-Time Control', 
                     fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x + width)
        ax.set_xticklabels([a.upper() for a in agents], fontsize=12)
        ax.legend(fontsize=11, loc='best')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.5)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'improvement_metrics.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_training_curves(self):
        """Plot training curves for RL agents."""
        print("\nGenerating training curves...")
        
        if not self.results_data or 'rl_agents' not in self.results_data:
            print("✗ No RL agent data available")
            return
        
        rl_agents = self.results_data['rl_agents']
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('RL Agent Training Progress', fontsize=16, fontweight='bold')
        
        colors_list = ['#4ecdc4', '#f38181', '#95e1d3']
        
        for idx, (agent_name, agent_data) in enumerate(rl_agents.items()):
            if 'training_data' not in agent_data:
                continue
            
            training_data = agent_data['training_data']
            color = colors_list[idx % len(colors_list)]
            
            # Plot 1: Episode Rewards
            if 'rewards' in training_data:
                ax1 = axes[0, 0]
                rewards = training_data['rewards']
                episodes = range(1, len(rewards) + 1)
                ax1.plot(episodes, rewards, label=agent_name.upper(), 
                        color=color, alpha=0.7, linewidth=2)
                
                # Add moving average
                if len(rewards) >= 5:
                    window = min(5, len(rewards))
                    moving_avg = np.convolve(rewards, np.ones(window)/window, mode='valid')
                    ax1.plot(range(window, len(rewards) + 1), moving_avg, 
                            color=color, linewidth=2.5, alpha=0.9, 
                            linestyle='--', label=f'{agent_name.upper()} (MA)')
                
                ax1.set_xlabel('Episode', fontsize=11)
                ax1.set_ylabel('Reward', fontsize=11)
                ax1.set_title('Episode Rewards', fontsize=12, fontweight='bold')
                ax1.legend(fontsize=9)
                ax1.grid(alpha=0.3)
            
            # Plot 2: Waiting Times
            if 'waiting_times' in training_data:
                ax2 = axes[0, 1]
                waiting_times = training_data['waiting_times']
                episodes = range(1, len(waiting_times) + 1)
                ax2.plot(episodes, waiting_times, label=agent_name.upper(), 
                        color=color, alpha=0.7, linewidth=2)
                
                ax2.set_xlabel('Episode', fontsize=11)
                ax2.set_ylabel('Waiting Time (s)', fontsize=11)
                ax2.set_title('Episode Waiting Times', fontsize=12, fontweight='bold')
                ax2.legend(fontsize=9)
                ax2.grid(alpha=0.3)
            
            # Plot 3: Throughput
            if 'throughputs' in training_data:
                ax3 = axes[1, 0]
                throughputs = training_data['throughputs']
                episodes = range(1, len(throughputs) + 1)
                ax3.plot(episodes, throughputs, label=agent_name.upper(), 
                        color=color, alpha=0.7, linewidth=2)
                
                ax3.set_xlabel('Episode', fontsize=11)
                ax3.set_ylabel('Throughput', fontsize=11)
                ax3.set_title('Episode Throughput', fontsize=12, fontweight='bold')
                ax3.legend(fontsize=9)
                ax3.grid(alpha=0.3)
            
            # Plot 4: Episode Lengths
            if 'lengths' in training_data:
                ax4 = axes[1, 1]
                lengths = training_data['lengths']
                episodes = range(1, len(lengths) + 1)
                ax4.plot(episodes, lengths, label=agent_name.upper(), 
                        color=color, alpha=0.7, linewidth=2)
                
                ax4.set_xlabel('Episode', fontsize=11)
                ax4.set_ylabel('Episode Length', fontsize=11)
                ax4.set_title('Episode Lengths', fontsize=12, fontweight='bold')
                ax4.legend(fontsize=9)
                ax4.grid(alpha=0.3)
        
        plt.tight_layout()
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'training_curves.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_comparison_radar(self):
        """Plot radar chart comparing all methods."""
        print("\nGenerating radar chart comparison...")
        
        if self.summary_df is None:
            print("✗ No data available")
            return
        
        from math import pi
        
        # Prepare data - normalize metrics for radar chart
        agents = self.summary_df['Agent Name'].tolist()
        
        # Normalize metrics (0-1 scale, higher is better for all)
        rewards = self.summary_df['Avg Reward'].values
        waiting_times = self.summary_df['Avg Waiting Time'].values
        throughputs = self.summary_df['Avg Throughput'].values
        
        # Normalize to 0-1 (higher is better)
        def normalize_higher_better(values):
            vmin, vmax = values.min(), values.max()
            if vmax == vmin:
                return np.ones_like(values)
            return (values - vmin) / (vmax - vmin)
        
        def normalize_lower_better(values):
            vmin, vmax = values.min(), values.max()
            if vmax == vmin:
                return np.ones_like(values)
            return 1 - (values - vmin) / (vmax - vmin)
        
        norm_rewards = normalize_higher_better(rewards)
        norm_waiting = normalize_lower_better(waiting_times)
        norm_throughput = normalize_higher_better(throughputs)
        
        # Categories
        categories = ['Reward\n(Higher Better)', 'Waiting Time\n(Lower Better)', 
                     'Throughput\n(Higher Better)']
        N = len(categories)
        
        # Create figure
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='polar')
        
        # Compute angle for each category
        angles = [n / float(N) * 2 * pi for n in range(N)]
        angles += angles[:1]
        
        # Plot each agent
        colors_map = {
            'fixed_time': '#ff6b6b',
            'actuated': '#ffa07a',
            'adaptive': '#ffb347',
            'random': '#ff1744',
            'dqn': '#4ecdc4',
            'ppo': '#45b7d1'
        }
        
        for i, agent in enumerate(agents):
            values = [norm_rewards[i], norm_waiting[i], norm_throughput[i]]
            values += values[:1]
            
            color = colors_map.get(agent, '#808080')
            ax.plot(angles, values, 'o-', linewidth=2, label=agent.upper(), 
                   color=color, alpha=0.7)
            ax.fill(angles, values, alpha=0.15, color=color)
        
        # Fix axis to go in the right order and start at 12 o'clock
        ax.set_theta_offset(pi / 2)
        ax.set_theta_direction(-1)
        
        # Draw axis lines for each angle and label
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        
        # Set y-axis limits
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=9)
        ax.grid(True)
        
        # Add legend
        plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        
        plt.title('Performance Comparison - Normalized Metrics', 
                 fontsize=14, fontweight='bold', pad=20)
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'radar_comparison.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_statistical_analysis(self):
        """Plot statistical analysis with error bars."""
        print("\nGenerating statistical analysis chart...")
        
        if self.summary_df is None:
            print("✗ No data available")
            return
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Statistical Analysis of Controller Performance', 
                     fontsize=16, fontweight='bold')
        
        agents = self.summary_df['Agent Name'].tolist()
        colors = ['#ff6b6b' if t == 'Baseline' else '#4ecdc4' 
                  for t in self.summary_df['Agent Type']]
        
        # Plot 1: Reward with error bars
        ax1 = axes[0]
        avg_rewards = self.summary_df['Avg Reward'].values
        std_rewards = self.summary_df['Std Reward'].values
        
        bars1 = ax1.bar(agents, avg_rewards, yerr=std_rewards, 
                       color=colors, alpha=0.7, capsize=5, error_kw={'linewidth': 2})
        ax1.set_ylabel('Average Reward', fontsize=12)
        ax1.set_title('Average Reward ± Std Dev', fontsize=13, fontweight='bold')
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(axis='y', alpha=0.3)
        
        for i, (bar, val, std) in enumerate(zip(bars1, avg_rewards, std_rewards)):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f}\n±{std:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 2: Waiting Time with error bars
        ax2 = axes[1]
        avg_waiting = self.summary_df['Avg Waiting Time'].values
        std_waiting = self.summary_df['Std Waiting Time'].values
        
        bars2 = ax2.bar(agents, avg_waiting, yerr=std_waiting, 
                       color=colors, alpha=0.7, capsize=5, error_kw={'linewidth': 2})
        ax2.set_ylabel('Average Waiting Time (s)', fontsize=12)
        ax2.set_title('Average Waiting Time ± Std Dev', fontsize=13, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(axis='y', alpha=0.3)
        
        for i, (bar, val, std) in enumerate(zip(bars2, avg_waiting, std_waiting)):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f}\n±{std:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'statistical_analysis.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def create_summary_table(self):
        """Create a formatted summary table for thesis."""
        print("\nGenerating summary table...")
        
        if self.summary_df is None:
            print("✗ No data available")
            return
        
        # Create figure for table
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.axis('tight')
        ax.axis('off')
        
        # Prepare table data
        table_data = []
        headers = ['Method', 'Type', 'Avg Reward', 'Avg Waiting Time (s)', 
                  'Avg Throughput', 'Std Reward', 'Training Time (s)']
        
        for _, row in self.summary_df.iterrows():
            table_data.append([
                row['Agent Name'].upper(),
                row['Agent Type'],
                f"{row['Avg Reward']:.2f}",
                f"{row['Avg Waiting Time']:.2f}",
                f"{row['Avg Throughput']:.2f}",
                f"{row['Std Reward']:.2f}",
                f"{row['Training Time (s)']:.0f}" if row['Training Time (s)'] > 0 else 'N/A'
            ])
        
        # Create table
        table = ax.table(cellText=table_data, colLabels=headers, 
                        cellLoc='center', loc='center')
        
        # Style table
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        
        # Color header
        for i in range(len(headers)):
            cell = table[(0, i)]
            cell.set_facecolor('#4a90e2')
            cell.set_text_props(weight='bold', color='white')
        
        # Color rows based on type
        for i, (_, row) in enumerate(self.summary_df.iterrows(), start=1):
            color = '#ffe6e6' if row['Agent Type'] == 'Baseline' else '#e6f7ff'
            for j in range(len(headers)):
                table[(i, j)].set_facecolor(color)
        
        plt.title('Comprehensive Performance Summary', 
                 fontsize=14, fontweight='bold', pad=20)
        
        # Save figure
        fig_path = os.path.join(self.figures_dir, 'summary_table.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def generate_all_visualizations(self):
        """Generate all visualizations for thesis."""
        print("\n" + "="*60)
        print("  GENERATING THESIS VISUALIZATIONS")
        print("="*60)
        
        if not self.load_results():
            print("\n✗ Failed to load results. Cannot generate visualizations.")
            return False
        
        # Generate all plots
        self.plot_performance_comparison()
        self.plot_improvement_metrics()
        self.plot_training_curves()
        self.plot_comparison_radar()
        self.plot_statistical_analysis()
        self.create_summary_table()
        
        print("\n" + "="*60)
        print("  ✓ ALL VISUALIZATIONS GENERATED SUCCESSFULLY")
        print("="*60)
        print(f"\nFigures saved to: {self.figures_dir}")
        print("\nGenerated files:")
        for filename in os.listdir(self.figures_dir):
            if filename.endswith('.png'):
                print(f"  • {filename}")
        
        return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate visualizations for thesis'
    )
    parser.add_argument('--results-dir', type=str, default='./results/',
                       help='Directory containing results')
    
    args = parser.parse_args()
    
    # Create visualizer and generate all plots
    visualizer = ThesisVisualizer(results_dir=args.results_dir)
    success = visualizer.generate_all_visualizations()
    
    if success:
        print("\n✓ Visualization generation complete!")
        print("You can now use these figures in your thesis presentation.")
    else:
        print("\n✗ Visualization generation failed.")
        print("Make sure to run the experiments first using run_comprehensive_study.py")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
