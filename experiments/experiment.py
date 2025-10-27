"""
Experiment script to compare different traffic control methods.
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
import os
import sys
import json
from datetime import datetime
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.environment import TrafficEnv
from src.agents.dqn_agent import create_dqn_agent
from src.agents.baseline_controllers import (
    FixedTimeController,
    ActuatedController,
    AdaptiveController,
    RandomController,
    TrafficController
)
from src.visualization import create_comprehensive_comparison, create_real_world_impact_visualization

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


class ExperimentRunner:
    """Run experiments comparing different traffic control methods."""
    
    def __init__(self, use_sumo: bool = False, config_type: str = "one_intersection"):
        """
        Initialize experiment runner.
        
        Args:
            use_sumo: Whether to use real SUMO (False uses mock)
            config_type: "one_intersection" or "three_intersections"
        """
        self.use_sumo = use_sumo
        self.config_type = config_type
        self.env = TrafficEnv(use_sumo=use_sumo, config_type=config_type)
        
        # Results storage
        self.results = {}
        
    def run_baseline(self, controller_name: str, controller: object) -> Dict:
        """Run a baseline controller."""
        print(f"\n{'='*60}")
        print(f"Running {controller_name}")
        print(f"{'='*60}")
        
        obs, info = self.env.reset()
        metrics_history = []
        step_count = 0
        
        # Reset controller if it has reset method
        if hasattr(controller, 'reset'):
            controller.reset()
        
        while True:
            # Get state for controller
            state = self._extract_state_from_obs(obs)
            
            # Controller selects action
            action = controller.select_action(state)
            
            # Step environment
            obs, reward, done, truncated, info = self.env.step(action)
            
            # Record metrics
            metrics_history.append({
                'step': step_count,
                'total_waiting_time': info['total_waiting_time'],
                'total_vehicles': info['total_vehicles'],
                'total_halting': info['total_halting'],
                'reward': reward
            })
            
            step_count += 1
            
            if done or truncated:
                break
        
        # Calculate aggregate metrics
        metrics_history = pd.DataFrame(metrics_history)
        
        results = {
            'avg_waiting_time': metrics_history['total_waiting_time'].mean(),
            'total_waiting_time': metrics_history['total_waiting_time'].sum(),
            'avg_vehicles': metrics_history['total_vehicles'].mean(),
            'max_vehicles': metrics_history['total_vehicles'].max(),
            'avg_halting': metrics_history['total_halting'].mean(),
            'max_halting': metrics_history['total_halting'].max(),
            'cumulative_reward': metrics_history['reward'].sum(),
            'metrics_history': metrics_history.to_dict('records')
        }
        
        self.results[controller_name] = results
        
        print(f"Completed: Avg waiting time = {results['avg_waiting_time']:.2f}")
        
        return results
    
    def _extract_state_from_obs(self, obs: np.ndarray) -> np.ndarray:
        """Extract relevant state from observation."""
        # Return observation as-is for baseline controllers
        return obs
    
    def run_dqn(self, training_steps: int = 1000, eval_steps: int = 500) -> Dict:
        """Train and evaluate DQN agent."""
        print(f"\n{'='*60}")
        print("Training DQN Agent")
        print(f"{'='*60}")
        
        # Create agent
        state_dim = self.env.observation_space.shape[0]
        action_dim = self.env.action_space.n
        
        agent = create_dqn_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            learning_rate=5e-4,
            gamma=0.99,
            epsilon_start=1.0,
            epsilon_end=0.01,
            epsilon_decay=0.995,
            batch_size=64
        )
        
        # Training phase
        print("Training phase...")
        obs, info = self.env.reset()
        training_history = []
        
        for step in range(training_steps):
            state = obs.copy()
            
            # Agent selects action
            action = agent.select_action(obs)
            
            # Step environment
            obs, reward, done, truncated, info = self.env.step(action)
            next_state = obs.copy()
            
            # Store experience
            agent.store_experience(state, action, reward, next_state, done or truncated)
            
            # Update agent
            if len(agent.replay_buffer) > agent.batch_size:
                loss = agent.update_model()
                if step % 100 == 0:
                    print(f"  Step {step}/{training_steps}, Loss: {loss:.4f}")
            
            agent.update_epsilon()
            
            if done or truncated:
                obs, info = self.env.reset()
                if hasattr(agent, 'reset'):
                    agent.reset()
        
        print("Training complete!")
        
        # Evaluation phase
        print("\nEvaluation phase...")
        agent.set_training_mode(False)
        obs, info = self.env.reset()
        
        metrics_history = []
        step_count = 0
        
        for step in range(eval_steps):
            action = agent.select_action(obs)
            obs, reward, done, truncated, info = self.env.step(action)
            
            metrics_history.append({
                'step': step_count,
                'total_waiting_time': info['total_waiting_time'],
                'total_vehicles': info['total_vehicles'],
                'total_halting': info['total_halting'],
                'reward': reward
            })
            
            step_count += 1
            
            if done or truncated:
                obs, info = self.env.reset()
        
        # Calculate aggregate metrics
        metrics_history = pd.DataFrame(metrics_history)
        
        results = {
            'avg_waiting_time': metrics_history['total_waiting_time'].mean(),
            'total_waiting_time': metrics_history['total_waiting_time'].sum(),
            'avg_vehicles': metrics_history['total_vehicles'].mean(),
            'max_vehicles': metrics_history['total_vehicles'].max(),
            'avg_halting': metrics_history['total_halting'].mean(),
            'max_halting': metrics_history['total_halting'].max(),
            'cumulative_reward': metrics_history['reward'].sum(),
            'metrics_history': metrics_history.to_dict('records')
        }
        
        self.results['DQN'] = results
        
        print(f"Completed: Avg waiting time = {results['avg_waiting_time']:.2f}")
        
        return results
    
    def run_all_experiments(self, train_dqn: bool = True):
        """Run all experiment methods."""
        print("\n" + "="*60)
        print("Running Traffic Control Experiments")
        print("="*60)
        
        # Run baseline controllers
        self.run_baseline("Fixed-Time", FixedTimeController(phase_duration=30))
        self.run_baseline("Actuated", ActuatedController(
            threshold=10.0, min_green_time=15, max_green_time=60))
        self.run_baseline("Adaptive", AdaptiveController(
            base_green_time=20, max_green_time=60))
        self.run_baseline("Random", RandomController(num_phases=2))
        
        # Run DQN if requested
        if train_dqn:
            self.run_dqn(training_steps=1000, eval_steps=500)
        
        # Close environment after all experiments
        self.env.close()
    
    def _convert_to_json_serializable(self, obj):
        """Convert numpy/pandas types to JSON-serializable types."""
        if isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def save_results(self, filename: str = None):
        """Save results to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results_{timestamp}.json"
        
        # Save to config-specific directory
        results_dir = f"results/{self.config_type}/experiments"
        os.makedirs(results_dir, exist_ok=True)
        filepath = os.path.join(results_dir, filename)
        
        # Convert to JSON-serializable format
        results_dict = {}
        for method, data in self.results.items():
            results_dict[method] = {
                k: self._convert_to_json_serializable(v) 
                for k, v in data.items() if k != 'metrics_history'
            }
            # Save metrics history separately or skip for size
        
        with open(filepath, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"\nResults saved to: {filepath}")
        return filepath
    
    def plot_comparison(self, save_dir: str = None):
        """Create comparison plots."""
        if save_dir is None:
            save_dir = f"results/{self.config_type}/plots"
        os.makedirs(save_dir, exist_ok=True)
        
        if not self.results:
            print("No results to plot.")
            return
        
        # Create comprehensive visualization
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        create_comprehensive_comparison(self.results, 
                                       f"{save_dir}/comprehensive_{timestamp}.png")
        create_real_world_impact_visualization(self.results,
                                              f"{save_dir}/real_world_impact_{timestamp}.png")
        
        # Extract metrics
        methods = []
        avg_waiting = []
        avg_vehicles = []
        avg_halting = []
        cumulative_reward = []
        
        for method, data in self.results.items():
            methods.append(method)
            avg_waiting.append(data['avg_waiting_time'])
            avg_vehicles.append(data['avg_vehicles'])
            avg_halting.append(data['avg_halting'])
            cumulative_reward.append(data['cumulative_reward'])
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Plot 1: Average Waiting Time
        ax1 = axes[0, 0]
        colors = sns.color_palette("husl", len(methods))
        bars = ax1.bar(range(len(methods)), avg_waiting, color=colors)
        ax1.set_xlabel('Method')
        ax1.set_ylabel('Average Waiting Time (s)')
        ax1.set_title('Average Waiting Time per Vehicle')
        ax1.set_xticks(range(len(methods)))
        ax1.set_xticklabels(methods, rotation=45, ha='right')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 2: Average Queue Length
        ax2 = axes[0, 1]
        bars = ax2.bar(range(len(methods)), avg_halting, color=colors)
        ax2.set_xlabel('Method')
        ax2.set_ylabel('Average Queue Length')
        ax2.set_title('Average Vehicles in Queue')
        ax2.set_xticks(range(len(methods)))
        ax2.set_xticklabels(methods, rotation=45, ha='right')
        
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 3: Total Reward
        ax3 = axes[1, 0]
        bars = ax3.bar(range(len(methods)), cumulative_reward, color=colors)
        ax3.set_xlabel('Method')
        ax3.set_ylabel('Cumulative Reward')
        ax3.set_title('Total Cumulative Reward')
        ax3.set_xticks(range(len(methods)))
        ax3.set_xticklabels(methods, rotation=45, ha='right')
        
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=9)
        
        # Plot 4: Time Series Comparison
        ax4 = axes[1, 1]
        for method, data in self.results.items():
            if 'metrics_history' in data and data['metrics_history']:
                history = pd.DataFrame(data['metrics_history'])
                ax4.plot(history['step'], history['total_waiting_time'], 
                        label=method, linewidth=2)
        
        ax4.set_xlabel('Simulation Step')
        ax4.set_ylabel('Total Waiting Time (s)')
        ax4.set_title('Waiting Time Over Time')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"comparison_{timestamp}.png")
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Comparison plot saved to: {filename}")
        
        plt.close()
    
    def plot_detailed_metrics(self, save_dir: str = None):
        """Create detailed metric visualizations."""
        if save_dir is None:
            save_dir = f"results/{self.config_type}/plots"
        os.makedirs(save_dir, exist_ok=True)
        
        if not self.results:
            return
        
        # Extract all metrics for all methods
        all_metrics = {}
        for method, data in self.results.items():
            if 'metrics_history' in data and data['metrics_history']:
                df = pd.DataFrame(data['metrics_history'])
                all_metrics[method] = df
        
        if not all_metrics:
            return
        
        # Create detailed comparison
        fig = plt.figure(figsize=(16, 10))
        
        # Plot 1: Waiting Time
        ax1 = plt.subplot(2, 2, 1)
        for method, df in all_metrics.items():
            ax1.plot(df['step'], df['total_waiting_time'], label=method, linewidth=2)
        ax1.set_xlabel('Step')
        ax1.set_ylabel('Total Waiting Time (s)')
        ax1.set_title('Waiting Time Over Time')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Vehicle Count
        ax2 = plt.subplot(2, 2, 2)
        for method, df in all_metrics.items():
            ax2.plot(df['step'], df['total_vehicles'], label=method, linewidth=2)
        ax2.set_xlabel('Step')
        ax2.set_ylabel('Total Vehicles')
        ax2.set_title('Vehicle Count Over Time')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Queue Length
        ax3 = plt.subplot(2, 2, 3)
        for method, df in all_metrics.items():
            ax3.plot(df['step'], df['total_halting'], label=method, linewidth=2)
        ax3.set_xlabel('Step')
        ax3.set_ylabel('Total Halting Vehicles')
        ax3.set_title('Queue Length Over Time')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Reward
        ax4 = plt.subplot(2, 2, 4)
        for method, df in all_metrics.items():
            ax4.plot(df['step'], df['reward'], label=method, linewidth=2)
        ax4.set_xlabel('Step')
        ax4.set_ylabel('Reward')
        ax4.set_title('Reward Over Time')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"detailed_metrics_{timestamp}.png")
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Detailed metrics plot saved to: {filename}")
        
        plt.close()


def main():
    """Main function to run experiments."""
    # Run experiments without SUMO (using mock environment)
    runner = ExperimentRunner(use_sumo=False, config_type="one_intersection")
    
    print("\nRunning experiments on single intersection...")
    print("Using mock environment (no SUMO required)")
    
    # Run all experiments
    runner.run_all_experiments(train_dqn=True)
    
    # Save results
    runner.save_results()
    
    # Create plots
    print("\nGenerating visualizations...")
    runner.plot_comparison()
    runner.plot_detailed_metrics()
    
    # Print summary
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)
    for method, data in runner.results.items():
        print(f"\n{method}:")
        print(f"  Avg Waiting Time: {data['avg_waiting_time']:.2f}s")
        print(f"  Avg Queue Length: {data['avg_halting']:.2f} vehicles")
        print(f"  Cumulative Reward: {data['cumulative_reward']:.2f}")
    
    print("\nExperiment completed!")


if __name__ == "__main__":
    main()

