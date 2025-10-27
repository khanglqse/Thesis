"""
Advanced visualization utilities for traffic experiments.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from typing import Dict, List


def create_comprehensive_comparison(results: Dict, save_path: str = "results/plots/comprehensive.png"):
    """
    Create comprehensive comparison visualization with multiple metrics.
    
    Args:
        results: Dictionary of results from experiment
        save_path: Path to save the figure
    """
    # Prepare data
    methods = list(results.keys())
    
    # Extract metrics
    metrics = {
        'avg_waiting_time': [],
        'avg_vehicles': [],
        'avg_halting': [],
        'cumulative_reward': [],
        'total_waiting_time': []
    }
    
    for method in methods:
        data = results[method]
        metrics['avg_waiting_time'].append(data['avg_waiting_time'])
        metrics['avg_vehicles'].append(data['avg_vehicles'])
        metrics['avg_halting'].append(data['avg_halting'])
        metrics['cumulative_reward'].append(data['cumulative_reward'])
        metrics['total_waiting_time'].append(data['total_waiting_time'])
    
    # Create figure with 3x2 subplots
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle('Comprehensive Traffic Control Comparison\n(Single Intersection - Vietnam Traffic)', 
                 fontsize=16, fontweight='bold')
    
    colors = sns.color_palette("husl", len(methods))
    
    # Plot 1: Average Waiting Time (bar chart)
    ax1 = axes[0, 0]
    bars = ax1.bar(range(len(methods)), metrics['avg_waiting_time'], color=colors)
    ax1.set_ylabel('Average Waiting Time (s)', fontsize=11)
    ax1.set_title('A) Average Waiting Time per Vehicle', fontsize=12, fontweight='bold')
    ax1.set_xticks(range(len(methods)))
    ax1.set_xticklabels(methods, rotation=45, ha='right')
    ax1.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s', ha='center', va='bottom', fontsize=10)
    
    # Plot 2: Average Queue Length
    ax2 = axes[0, 1]
    bars = ax2.bar(range(len(methods)), metrics['avg_halting'], color=colors)
    ax2.set_ylabel('Average Queue Length', fontsize=11)
    ax2.set_title('B) Average Vehicles in Queue', fontsize=12, fontweight='bold')
    ax2.set_xticks(range(len(methods)))
    ax2.set_xticklabels(methods, rotation=45, ha='right')
    ax2.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=10)
    
    # Plot 3: Cumulative Reward
    ax3 = axes[1, 0]
    bars = ax3.bar(range(len(methods)), metrics['cumulative_reward'], color=colors)
    ax3.set_ylabel('Cumulative Reward', fontsize=11)
    ax3.set_title('C) Total Cumulative Reward', fontsize=12, fontweight='bold')
    ax3.set_xticks(range(len(methods)))
    ax3.set_xticklabels(methods, rotation=45, ha='right')
    ax3.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10)
    
    # Plot 4: Total Waiting Time
    ax4 = axes[1, 1]
    bars = ax4.bar(range(len(methods)), metrics['total_waiting_time'], color=colors)
    ax4.set_ylabel('Total Waiting Time (s)', fontsize=11)
    ax4.set_title('D) Total Waiting Time', fontsize=12, fontweight='bold')
    ax4.set_xticks(range(len(methods)))
    ax4.set_xticklabels(methods, rotation=45, ha='right')
    ax4.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}s', ha='center', va='bottom', fontsize=10)
    
    # Plot 5: Normalized Comparison (stacked)
    ax5 = axes[2, 0]
    
    # Normalize metrics for comparison
    normalized_wait = np.array(metrics['avg_waiting_time'])
    normalized_wait = normalized_wait / normalized_wait.max()
    
    normalized_queue = np.array(metrics['avg_halting'])
    normalized_queue = normalized_queue / normalized_queue.max() if normalized_queue.max() > 0 else normalized_queue
    
    # Plot as grouped bars
    x = np.arange(len(methods))
    width = 0.35
    
    ax5.bar(x - width/2, normalized_wait, width, label='Waiting Time', color='coral', alpha=0.7)
    ax5.bar(x + width/2, normalized_queue, width, label='Queue Length', color='skyblue', alpha=0.7)
    
    ax5.set_ylabel('Normalized Score (0-1)', fontsize=11)
    ax5.set_title('E) Normalized Performance Comparison', fontsize=12, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels(methods, rotation=45, ha='right')
    ax5.legend()
    ax5.grid(axis='y', alpha=0.3)
    
    # Plot 6: Time Series - Waiting Time Over Time
    ax6 = axes[2, 1]
    
    for method, data in results.items():
        if 'metrics_history' in data and data['metrics_history']:
            history = pd.DataFrame(data['metrics_history'])
            if len(history) > 0:
                # Sample for smoother plot
                sample_size = min(100, len(history))
                sampled = history.sample(n=sample_size) if len(history) > sample_size else history
                ax6.plot(sampled['step'], sampled['total_waiting_time'], 
                        label=method, linewidth=2, alpha=0.8)
    
    ax6.set_xlabel('Simulation Step', fontsize=11)
    ax6.set_ylabel('Total Waiting Time (s)', fontsize=11)
    ax6.set_title('F) Waiting Time Evolution', fontsize=12, fontweight='bold')
    ax6.legend(loc='best', fontsize=9)
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Comprehensive visualization saved to: {save_path}")


def create_real_world_impact_visualization(results: Dict, save_path: str = "results/plots/real_world_impact.png"):
    """
    Create visualization focusing on real-world impact metrics.
    
    Args:
        results: Dictionary of results
        save_path: Path to save figure
    """
    methods = list(results.keys())
    
    # Extract real-world impact metrics
    avg_wait = [results[m]['avg_waiting_time'] for m in methods]
    total_wait = [results[m]['total_waiting_time'] for m in methods]
    avg_queue = [results[m]['avg_halting'] for m in methods]
    
    # Calculate improvement vs baseline
    baseline_wait = avg_wait[0]  # First method as baseline (Fixed-Time)
    improvements = [((baseline_wait - w) / baseline_wait * 100) for w in avg_wait]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Real-World Impact Analysis\n(Traffic Control Methods)', 
                 fontsize=16, fontweight='bold')
    
    colors = sns.color_palette("husl", len(methods))
    
    # Plot 1: Average waiting time with improvement percentage
    ax1 = axes[0, 0]
    bars = ax1.bar(range(len(methods)), avg_wait, color=colors)
    ax1.set_ylabel('Average Waiting Time (s)', fontsize=11)
    ax1.set_title('Average Waiting Time per Vehicle', fontsize=12, fontweight='bold')
    ax1.set_xticks(range(len(methods)))
    ax1.set_xticklabels(methods, rotation=45, ha='right')
    ax1.axhline(y=baseline_wait, color='r', linestyle='--', alpha=0.5, label='Baseline')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Add improvement annotations
    for i, (bar, improvement) in enumerate(zip(bars, improvements)):
        height = bar.get_height()
        if improvement > 0:
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}s\n({improvement:+.1f}%)',
                    ha='center', va='bottom', fontsize=9)
        else:
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}s',
                    ha='center', va='bottom', fontsize=9)
    
    # Plot 2: Total impact (total waiting time)
    ax2 = axes[0, 1]
    bars = ax2.bar(range(len(methods)), total_wait, color=colors)
    ax2.set_ylabel('Total Waiting Time (s)', fontsize=11)
    ax2.set_title('Total Waiting Time (System Impact)', fontsize=12, fontweight='bold')
    ax2.set_xticks(range(len(methods)))
    ax2.set_xticklabels(methods, rotation=45, ha='right')
    ax2.grid(axis='y', alpha=0.3)
    
    for bar, wait in zip(bars, total_wait):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{wait:.0f}s', ha='center', va='bottom', fontsize=10)
    
    # Plot 3: Queue length comparison
    ax3 = axes[1, 0]
    bars = ax3.bar(range(len(methods)), avg_queue, color=colors)
    ax3.set_ylabel('Average Queue Length', fontsize=11)
    ax3.set_title('Average Vehicles in Queue (Congestion)', fontsize=12, fontweight='bold')
    ax3.set_xticks(range(len(methods)))
    ax3.set_xticklabels(methods, rotation=45, ha='right')
    ax3.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=10)
    
    # Plot 4: Efficiency score (combined metric)
    ax4 = axes[1, 1]
    
    # Calculate efficiency score (lower is better, normalized)
    # Combine waiting time and queue length
    efficiency_scores = []
    for i, method in enumerate(methods):
        # Normalized to 0-1 scale
        wait_norm = avg_wait[i] / max(avg_wait)
        queue_norm = avg_queue[i] / max(avg_queue) if max(avg_queue) > 0 else 0
        
        # Efficiency = weighted combination (lower is better)
        efficiency = 0.7 * wait_norm + 0.3 * queue_norm
        efficiency_scores.append(efficiency)
    
    bars = ax4.bar(range(len(methods)), efficiency_scores, color=colors)
    ax4.set_ylabel('Efficiency Score (Lower is Better)', fontsize=11)
    ax4.set_title('Combined Efficiency Score', fontsize=12, fontweight='bold')
    ax4.set_xticks(range(len(methods)))
    ax4.set_xticklabels(methods, rotation=45, ha='right')
    ax4.grid(axis='y', alpha=0.3)
    
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Real-world impact visualization saved to: {save_path}")

