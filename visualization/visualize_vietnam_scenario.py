#!/usr/bin/env python3
"""
Vietnam Scenario Visualization
===============================
Generate specialized visualizations for Vietnamese traffic scenario
with 12 intersections, comparing with standard 3-intersection scenario.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class VietnamScenarioVisualizer:
    """Visualizer for Vietnam traffic scenario results."""
    
    def __init__(self, vietnam_results_dir='./results/vietnam_scenario/',
                 standard_results_dir='./results/'):
        """
        Initialize visualizer.
        
        Args:
            vietnam_results_dir: Directory with Vietnam scenario results
            standard_results_dir: Directory with standard scenario results
        """
        self.vietnam_dir = vietnam_results_dir
        self.standard_dir = standard_results_dir
        self.figures_dir = os.path.join(vietnam_results_dir, 'figures')
        os.makedirs(self.figures_dir, exist_ok=True)
        
        self.vietnam_data = None
        self.standard_data = None
        self.vietnam_df = None
        self.standard_df = None
    
    def load_results(self):
        """Load both Vietnam and standard scenario results."""
        print("Loading results...")
        
        # Load Vietnam results
        vietnam_json = os.path.join(self.vietnam_dir, 'vietnam_study_results.json')
        if os.path.exists(vietnam_json):
            with open(vietnam_json, 'r') as f:
                self.vietnam_data = json.load(f)
            print(f"✓ Loaded Vietnam results: {vietnam_json}")
        else:
            print(f"✗ Vietnam results not found: {vietnam_json}")
            return False
        
        vietnam_csv = os.path.join(self.vietnam_dir, 'vietnam_study_summary.csv')
        if os.path.exists(vietnam_csv):
            self.vietnam_df = pd.read_csv(vietnam_csv)
            print(f"✓ Loaded Vietnam CSV: {vietnam_csv}")
        
        # Load standard results for comparison
        standard_json = os.path.join(self.standard_dir, 'comprehensive_study_results.json')
        if os.path.exists(standard_json):
            with open(standard_json, 'r') as f:
                self.standard_data = json.load(f)
            print(f"✓ Loaded standard results: {standard_json}")
        
        standard_csv = os.path.join(self.standard_dir, 'comprehensive_study_summary.csv')
        if os.path.exists(standard_csv):
            self.standard_df = pd.read_csv(standard_csv)
            print(f"✓ Loaded standard CSV: {standard_csv}")
        
        return True
    
    def plot_scenario_comparison(self):
        """Compare Vietnam vs Standard scenario."""
        print("\nGenerating scenario comparison chart...")
        
        if self.vietnam_df is None or self.standard_df is None:
            print("✗ Missing data for comparison")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Vietnam Scenario (12 Intersections) vs Standard Scenario (3 Intersections)',
                     fontsize=16, fontweight='bold')
        
        # Prepare comparison data - focus on DQN
        scenarios = ['Standard\n(3 intersections)', 'Vietnam\n(12 intersections)']
        
        # Get DQN and baseline data
        standard_fixed = self.standard_df[self.standard_df['Agent Name'] == 'fixed_time'].iloc[0]
        standard_dqn = self.standard_df[self.standard_df['Agent Name'] == 'dqn'].iloc[0]
        vietnam_fixed = self.vietnam_df[self.vietnam_df['Agent Name'] == 'fixed_time'].iloc[0]
        vietnam_dqn = self.vietnam_df[self.vietnam_df['Agent Name'] == 'dqn'].iloc[0]
        
        # Plot 1: Baseline Performance Comparison
        ax1 = axes[0, 0]
        x = np.arange(len(scenarios))
        width = 0.35
        
        baseline_rewards = [standard_fixed['Avg Reward'], vietnam_fixed['Avg Reward']]
        baseline_waiting = [standard_fixed['Avg Waiting Time'], vietnam_fixed['Avg Waiting Time']]
        
        ax1_twin = ax1.twinx()
        bars1 = ax1.bar(x - width/2, np.abs(baseline_rewards), width, label='Reward (lower better)',
                       color='#ff6b6b', alpha=0.7)
        bars2 = ax1_twin.bar(x + width/2, baseline_waiting, width, label='Waiting Time (s)',
                            color='#ffa07a', alpha=0.7)
        
        ax1.set_xlabel('Scenario', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Avg Reward (absolute)', fontsize=11, color='#ff6b6b')
        ax1_twin.set_ylabel('Waiting Time (s)', fontsize=11, color='#ffa07a')
        ax1.set_title('Baseline (Fixed-Time) Performance\nHigher complexity → Worse performance',
                     fontsize=12, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios)
        ax1.tick_params(axis='y', labelcolor='#ff6b6b')
        ax1_twin.tick_params(axis='y', labelcolor='#ffa07a')
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')
        ax1.grid(axis='y', alpha=0.3)
        
        # Plot 2: DQN Performance Comparison
        ax2 = axes[0, 1]
        dqn_rewards = [standard_dqn['Avg Reward'], vietnam_dqn['Avg Reward']]
        dqn_waiting = [standard_dqn['Avg Waiting Time'], vietnam_dqn['Avg Waiting Time']]
        
        ax2_twin = ax2.twinx()
        bars3 = ax2.bar(x - width/2, np.abs(dqn_rewards), width, label='Reward (lower better)',
                       color='#4ecdc4', alpha=0.7)
        bars4 = ax2_twin.bar(x + width/2, dqn_waiting, width, label='Waiting Time (s)',
                            color='#95e1d3', alpha=0.7)
        
        ax2.set_xlabel('Scenario', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Avg Reward (absolute)', fontsize=11, color='#4ecdc4')
        ax2_twin.set_ylabel('Waiting Time (s)', fontsize=11, color='#95e1d3')
        ax2.set_title('DQN (RL) Performance\nAdapts well to both scenarios',
                     fontsize=12, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(scenarios)
        ax2.tick_params(axis='y', labelcolor='#4ecdc4')
        ax2_twin.tick_params(axis='y', labelcolor='#95e1d3')
        ax2.legend(loc='upper left')
        ax2_twin.legend(loc='upper right')
        ax2.grid(axis='y', alpha=0.3)
        
        # Plot 3: Improvement Comparison
        ax3 = axes[1, 0]
        
        standard_improvement = ((standard_fixed['Avg Waiting Time'] - standard_dqn['Avg Waiting Time']) /
                               standard_fixed['Avg Waiting Time']) * 100
        vietnam_improvement = ((vietnam_fixed['Avg Waiting Time'] - vietnam_dqn['Avg Waiting Time']) /
                              vietnam_fixed['Avg Waiting Time']) * 100
        
        improvements = [standard_improvement, vietnam_improvement]
        colors = ['#4ecdc4', '#45b7d1']
        bars = ax3.bar(scenarios, improvements, color=colors, alpha=0.7)
        
        ax3.set_ylabel('Waiting Time Reduction (%)', fontsize=12, fontweight='bold')
        ax3.set_title('RL Improvement: DQN vs Baseline\nLarger improvement in complex scenarios!',
                     fontsize=12, fontweight='bold')
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax3.grid(axis='y', alpha=0.3)
        
        for bar, imp in zip(bars, improvements):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{imp:.1f}%',
                    ha='center', va='bottom', fontsize=14, fontweight='bold')
        
        # Plot 4: Scalability Analysis
        ax4 = axes[1, 1]
        
        metrics = ['Intersections', 'Baseline\nWaiting Time', 'DQN\nWaiting Time',
                  'Training Time\n(minutes)']
        standard_values = [3, standard_fixed['Avg Waiting Time'], 
                          standard_dqn['Avg Waiting Time'],
                          standard_dqn['Training Time (s)']/60]
        vietnam_values = [12, vietnam_fixed['Avg Waiting Time'],
                         vietnam_dqn['Avg Waiting Time'],
                         vietnam_dqn['Training Time (s)']/60]
        
        # Normalize for comparison
        std_norm = np.array(standard_values) / np.array(standard_values)
        vn_norm = np.array(vietnam_values) / np.array(standard_values)
        
        x_pos = np.arange(len(metrics))
        width = 0.35
        
        bars1 = ax4.bar(x_pos - width/2, std_norm, width, label='Standard', 
                       color='#4ecdc4', alpha=0.7)
        bars2 = ax4.bar(x_pos + width/2, vn_norm, width, label='Vietnam',
                       color='#f38181', alpha=0.7)
        
        ax4.set_ylabel('Relative Scale (Standard = 1.0)', fontsize=11, fontweight='bold')
        ax4.set_title('Scalability Analysis\n(Normalized to Standard Scenario)',
                     fontsize=12, fontweight='bold')
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(metrics, fontsize=10)
        ax4.legend(fontsize=11)
        ax4.grid(axis='y', alpha=0.3)
        ax4.axhline(y=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5)
        
        plt.tight_layout()
        
        fig_path = os.path.join(self.figures_dir, 'vietnam_vs_standard_comparison.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_vietnam_performance(self):
        """Plot Vietnam scenario performance details."""
        print("\nGenerating Vietnam performance chart...")
        
        if self.vietnam_df is None:
            print("✗ No Vietnam data available")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Vietnamese Traffic Scenario Performance (12 Intersections)',
                     fontsize=16, fontweight='bold')
        
        agents = self.vietnam_df['Agent Name'].tolist()
        colors = ['#ff6b6b' if t == 'Baseline' else '#4ecdc4' 
                  for t in self.vietnam_df['Agent Type']]
        
        # Plot 1: Rewards
        ax1 = axes[0, 0]
        bars = ax1.bar(agents, self.vietnam_df['Avg Reward'], color=colors, alpha=0.7)
        ax1.set_ylabel('Average Reward', fontsize=12)
        ax1.set_title('Average Reward (Higher Better)', fontsize=12, fontweight='bold')
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(axis='y', alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9)
        
        # Plot 2: Waiting Times
        ax2 = axes[0, 1]
        bars = ax2.bar(agents, self.vietnam_df['Avg Waiting Time'], color=colors, alpha=0.7)
        ax2.set_ylabel('Waiting Time (seconds)', fontsize=12)
        ax2.set_title('Average Waiting Time (Lower Better)', fontsize=12, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(axis='y', alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}s', ha='center', va='bottom', fontsize=9)
        
        # Plot 3: Throughput
        ax3 = axes[1, 0]
        bars = ax3.bar(agents, self.vietnam_df['Avg Throughput'], color=colors, alpha=0.7)
        ax3.set_ylabel('Throughput (vehicles)', fontsize=12)
        ax3.set_title('Average Throughput (Higher Better)', fontsize=12, fontweight='bold')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(axis='y', alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9)
        
        # Plot 4: Performance Summary Table
        ax4 = axes[1, 1]
        ax4.axis('tight')
        ax4.axis('off')
        
        table_data = []
        for _, row in self.vietnam_df.iterrows():
            table_data.append([
                row['Agent Name'].upper(),
                row['Agent Type'],
                f"{row['Avg Reward']:.1f}",
                f"{row['Avg Waiting Time']:.1f}s",
                f"{row['Avg Throughput']:.1f}"
            ])
        
        table = ax4.table(cellText=table_data,
                         colLabels=['Method', 'Type', 'Reward', 'Wait Time', 'Throughput'],
                         cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)
        
        for i in range(5):
            table[(0, i)].set_facecolor('#4a90e2')
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        for i, (_, row) in enumerate(self.vietnam_df.iterrows(), start=1):
            color = '#ffe6e6' if row['Agent Type'] == 'Baseline' else '#e6f7ff'
            for j in range(5):
                table[(i, j)].set_facecolor(color)
        
        ax4.set_title('Performance Summary', fontsize=12, fontweight='bold', pad=20)
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#ff6b6b', alpha=0.7, label='Baseline Methods'),
            Patch(facecolor='#4ecdc4', alpha=0.7, label='RL Method (DQN)')
        ]
        fig.legend(handles=legend_elements, loc='upper right', fontsize=11)
        
        plt.tight_layout()
        
        fig_path = os.path.join(self.figures_dir, 'vietnam_performance_details.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def plot_vietnam_training_curves(self):
        """Plot training curves for Vietnam scenario."""
        print("\nGenerating Vietnam training curves...")
        
        if not self.vietnam_data or 'rl_agents' not in self.vietnam_data:
            print("✗ No training data available")
            return
        
        dqn_data = self.vietnam_data['rl_agents'].get('dqn', {})
        if 'training_data' not in dqn_data:
            print("✗ No training data for DQN")
            return
        
        training_data = dqn_data['training_data']
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('DQN Training Progress - Vietnam Scenario (12 Intersections)',
                     fontsize=16, fontweight='bold')
        
        color = '#4ecdc4'
        
        # Plot 1: Rewards
        ax1 = axes[0, 0]
        rewards = training_data['rewards']
        episodes = range(1, len(rewards) + 1)
        ax1.plot(episodes, rewards, color=color, alpha=0.5, linewidth=1)
        
        # Moving average
        if len(rewards) >= 10:
            window = 10
            ma = np.convolve(rewards, np.ones(window)/window, mode='valid')
            ax1.plot(range(window, len(rewards) + 1), ma, color=color, 
                    linewidth=2.5, label='Moving Avg (10 episodes)')
        
        ax1.set_xlabel('Episode', fontsize=11)
        ax1.set_ylabel('Reward', fontsize=11)
        ax1.set_title('Episode Rewards\n(Learning to handle complex traffic)',
                     fontsize=12, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(alpha=0.3)
        
        # Plot 2: Waiting Times
        ax2 = axes[0, 1]
        waiting_times = training_data['waiting_times']
        ax2.plot(episodes, waiting_times, color='#f38181', alpha=0.5, linewidth=1)
        
        if len(waiting_times) >= 10:
            ma = np.convolve(waiting_times, np.ones(window)/window, mode='valid')
            ax2.plot(range(window, len(waiting_times) + 1), ma, color='#f38181',
                    linewidth=2.5, label='Moving Avg')
        
        ax2.set_xlabel('Episode', fontsize=11)
        ax2.set_ylabel('Waiting Time (s)', fontsize=11)
        ax2.set_title('Episode Waiting Times\n(Decreasing over time)',
                     fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(alpha=0.3)
        
        # Plot 3: Throughput
        ax3 = axes[1, 0]
        throughputs = training_data['throughputs']
        ax3.plot(episodes, throughputs, color='#95e1d3', alpha=0.5, linewidth=1)
        
        if len(throughputs) >= 10:
            ma = np.convolve(throughputs, np.ones(window)/window, mode='valid')
            ax3.plot(range(window, len(throughputs) + 1), ma, color='#95e1d3',
                    linewidth=2.5, label='Moving Avg')
        
        ax3.set_xlabel('Episode', fontsize=11)
        ax3.set_ylabel('Throughput', fontsize=11)
        ax3.set_title('Episode Throughput\n(Improving with learning)',
                     fontsize=12, fontweight='bold')
        ax3.legend(fontsize=9)
        ax3.grid(alpha=0.3)
        
        # Plot 4: Learning Progress Summary
        ax4 = axes[1, 1]
        
        # Calculate improvement over episodes
        early_rewards = np.mean(rewards[:20])
        late_rewards = np.mean(rewards[-20:])
        reward_improvement = ((late_rewards - early_rewards) / abs(early_rewards)) * 100
        
        early_waiting = np.mean(waiting_times[:20])
        late_waiting = np.mean(waiting_times[-20:])
        waiting_improvement = ((early_waiting - late_waiting) / early_waiting) * 100
        
        metrics = ['Reward\nImprovement', 'Waiting Time\nReduction', 
                  'Training\nEpisodes']
        values = [reward_improvement, waiting_improvement, len(rewards)]
        colors_list = ['#4ecdc4', '#f38181', '#95e1d3']
        
        bars = ax4.bar(metrics, values, color=colors_list, alpha=0.7)
        ax4.set_ylabel('Value', fontsize=11)
        ax4.set_title('Learning Progress Summary\n(First 20 vs Last 20 episodes)',
                     fontsize=12, fontweight='bold')
        ax4.grid(axis='y', alpha=0.3)
        
        for i, (bar, val, metric) in enumerate(zip(bars, values, metrics)):
            height = bar.get_height()
            suffix = "%" if "Improvement" in metric or "Reduction" in metric else ""
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f}{suffix}',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        
        fig_path = os.path.join(self.figures_dir, 'vietnam_training_curves.png')
        plt.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {fig_path}")
        
        plt.close()
    
    def generate_all_visualizations(self):
        """Generate all visualizations for Vietnam scenario."""
        print("\n" + "="*70)
        print("  GENERATING VIETNAM SCENARIO VISUALIZATIONS")
        print("="*70)
        
        if not self.load_results():
            print("\n✗ Failed to load results.")
            return False
        
        self.plot_scenario_comparison()
        self.plot_vietnam_performance()
        self.plot_vietnam_training_curves()
        
        print("\n" + "="*70)
        print("  ✓ ALL VIETNAM VISUALIZATIONS GENERATED")
        print("="*70)
        print(f"\nFigures saved to: {self.figures_dir}")
        print("\nGenerated files:")
        for filename in os.listdir(self.figures_dir):
            if filename.endswith('.png'):
                print(f"  • {filename}")
        
        return True


def main():
    """Main function."""
    visualizer = VietnamScenarioVisualizer()
    success = visualizer.generate_all_visualizations()
    
    if success:
        print("\n✓ Vietnam scenario visualization complete!")
    else:
        print("\n✗ Visualization failed. Make sure to run:")
        print("  python3 experiments/run_rl_experiment.py --config experiments/vietnam_scenario_config.json")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

