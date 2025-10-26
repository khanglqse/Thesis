#!/usr/bin/env python3
"""
SUMO GUI Demo Script - Visual Comparison
==========================================
This script runs a visual demonstration comparing:
1. Baseline Fixed-Time Control (BEFORE RL)
2. DQN Agent Control (AFTER RL)

The GUI allows you to see the difference in traffic flow in real-time.
"""

import os
import sys
import time
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from environment.traffic_env import create_env
from agents.baseline_controllers import create_fixed_time_controller
from agents.dqn_agent import create_dqn_agent


def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def run_baseline_demo(duration=300):
    """
    Run baseline (Fixed-Time) controller demo with GUI.
    
    Args:
        duration: Duration in seconds (default 300 = 5 minutes)
    """
    print_header("PHASE 1: BASELINE FIXED-TIME CONTROL (BEFORE RL)")
    print("This demonstrates traditional fixed-time traffic signal control.")
    print("Notice:")
    print("  • Signals change at fixed 30-second intervals")
    print("  • No adaptation to traffic conditions")
    print("  • May see queue buildup during high demand")
    print("\nStarting SUMO GUI...\n")
    
    try:
        # Create environment with GUI
        env = create_env(use_gui=True, max_steps=duration)
        
        # Create fixed-time controller
        controller = create_fixed_time_controller(phase_duration=30)
        
        # Reset environment
        state, _ = env.reset()
        
        total_reward = 0
        total_waiting_time = 0
        step = 0
        
        print("Demo running... (Close SUMO GUI window to stop)")
        print("-" * 70)
        
        done = False
        truncated = False
        
        while not (done or truncated) and step < duration:
            # Select action from baseline controller
            action = controller.select_action(state)
            
            # Execute action
            state, reward, done, truncated, info = env.step(action)
            
            total_reward += reward
            if 'total_waiting_time' in info:
                total_waiting_time += info['total_waiting_time']
            
            step += 1
            
            # Print progress every 30 steps
            if step % 30 == 0:
                avg_reward = total_reward / step
                print(f"Step {step:4d}: Avg Reward = {avg_reward:8.2f}, "
                      f"Cumulative Waiting Time = {total_waiting_time:8.1f}s")
        
        env.close()
        
        print("\n" + "-" * 70)
        print("BASELINE DEMO COMPLETED")
        print(f"Total Steps: {step}")
        print(f"Average Reward: {total_reward/step:.2f}")
        print(f"Total Waiting Time: {total_waiting_time:.1f}s")
        print("-" * 70)
        
        return {
            'total_reward': total_reward,
            'avg_reward': total_reward / step,
            'total_waiting_time': total_waiting_time
        }
        
    except Exception as e:
        print(f"\n✗ Error in baseline demo: {e}")
        print("\nNote: If SUMO is not installed, this demo cannot run.")
        print("Please install SUMO or use the generated demo results instead.")
        import traceback
        traceback.print_exc()
        return None


def run_rl_demo(duration=300, model_path='./results/dqn_model.zip'):
    """
    Run RL (DQN) agent demo with GUI.
    
    Args:
        duration: Duration in seconds
        model_path: Path to trained DQN model
    """
    print_header("PHASE 2: RL-BASED DQN CONTROL (AFTER RL)")
    print("This demonstrates intelligent RL-based traffic signal control.")
    print("Notice:")
    print("  • Signals adapt dynamically to traffic conditions")
    print("  • Learned policy optimizes for reduced waiting time")
    print("  • Better handling of varying traffic demand")
    print("\nStarting SUMO GUI...\n")
    
    try:
        # Create environment with GUI
        env = create_env(use_gui=True, max_steps=duration)
        
        # Create DQN agent
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n
        agent = create_dqn_agent(state_dim, action_dim)
        
        # Try to load trained model
        if os.path.exists(model_path):
            print(f"Loading trained model from: {model_path}")
            agent.load_model(model_path)
            agent.set_training_mode(False)  # Evaluation mode
            print("✓ Model loaded successfully")
        else:
            print(f"⚠ Trained model not found at: {model_path}")
            print("Using untrained agent for demonstration purposes.")
            print("Note: Performance will be similar to baseline without training.")
        
        # Reset environment
        state, _ = env.reset()
        
        total_reward = 0
        total_waiting_time = 0
        step = 0
        
        print("\nDemo running... (Close SUMO GUI window to stop)")
        print("-" * 70)
        
        done = False
        truncated = False
        
        while not (done or truncated) and step < duration:
            # Select action from RL agent
            action = agent.select_action(state)
            
            # Execute action
            state, reward, done, truncated, info = env.step(action)
            
            total_reward += reward
            if 'total_waiting_time' in info:
                total_waiting_time += info['total_waiting_time']
            
            step += 1
            
            # Print progress every 30 steps
            if step % 30 == 0:
                avg_reward = total_reward / step
                print(f"Step {step:4d}: Avg Reward = {avg_reward:8.2f}, "
                      f"Cumulative Waiting Time = {total_waiting_time:8.1f}s")
        
        env.close()
        
        print("\n" + "-" * 70)
        print("RL DEMO COMPLETED")
        print(f"Total Steps: {step}")
        print(f"Average Reward: {total_reward/step:.2f}")
        print(f"Total Waiting Time: {total_waiting_time:.1f}s")
        print("-" * 70)
        
        return {
            'total_reward': total_reward,
            'avg_reward': total_reward / step,
            'total_waiting_time': total_waiting_time
        }
        
    except Exception as e:
        print(f"\n✗ Error in RL demo: {e}")
        print("\nNote: If SUMO is not installed, this demo cannot run.")
        import traceback
        traceback.print_exc()
        return None


def compare_results(baseline_results, rl_results):
    """Compare and print results from both demos."""
    if baseline_results is None or rl_results is None:
        print("\n⚠ Cannot compare results - one or both demos failed.")
        return
    
    print_header("COMPARISON: BASELINE vs RL")
    
    print(f"{'Metric':<30} {'Baseline':<15} {'RL (DQN)':<15} {'Improvement':<15}")
    print("-" * 75)
    
    # Average Reward
    baseline_reward = baseline_results['avg_reward']
    rl_reward = rl_results['avg_reward']
    reward_improvement = ((rl_reward - baseline_reward) / abs(baseline_reward)) * 100
    print(f"{'Average Reward':<30} {baseline_reward:<15.2f} {rl_reward:<15.2f} {reward_improvement:+.2f}%")
    
    # Total Waiting Time
    baseline_waiting = baseline_results['total_waiting_time']
    rl_waiting = rl_results['total_waiting_time']
    waiting_improvement = ((baseline_waiting - rl_waiting) / baseline_waiting) * 100
    print(f"{'Total Waiting Time (s)':<30} {baseline_waiting:<15.1f} {rl_waiting:<15.1f} {waiting_improvement:+.2f}%")
    
    print("-" * 75)
    
    if reward_improvement > 0:
        print("\n✓ RL agent shows BETTER performance than baseline!")
    else:
        print("\n⚠ Note: RL agent requires trained model for optimal performance.")
        print("Run training first: python3 experiments/run_comprehensive_study.py")


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(
        description='SUMO GUI Demo - Visual comparison of Baseline vs RL'
    )
    parser.add_argument('--duration', type=int, default=300,
                       help='Duration of each demo in seconds (default: 300 = 5 min)')
    parser.add_argument('--baseline-only', action='store_true',
                       help='Run only baseline demo')
    parser.add_argument('--rl-only', action='store_true',
                       help='Run only RL demo')
    parser.add_argument('--model-path', type=str, default='./results/dqn_model.zip',
                       help='Path to trained DQN model')
    
    args = parser.parse_args()
    
    print_header("SUMO GUI VISUAL DEMONSTRATION")
    print("This demo compares traffic signal control BEFORE and AFTER using RL.")
    print("\nRequirements:")
    print("  • SUMO must be installed and in PATH")
    print("  • For best RL performance, run training first")
    print("\nControls:")
    print("  • Use SUMO GUI controls to pause/resume simulation")
    print("  • Close GUI window to end demo early")
    print("\n" + "="*70)
    
    input("\nPress ENTER to start the demonstration...")
    
    baseline_results = None
    rl_results = None
    
    # Run demos based on flags
    if not args.rl_only:
        baseline_results = run_baseline_demo(duration=args.duration)
        if baseline_results:
            input("\nPress ENTER to continue to RL demo...")
    
    if not args.baseline_only:
        rl_results = run_rl_demo(duration=args.duration, model_path=args.model_path)
    
    # Compare results
    if baseline_results and rl_results:
        compare_results(baseline_results, rl_results)
    
    print_header("DEMO COMPLETE")
    print("Thank you for watching the demonstration!")
    print("\nFor detailed analysis, see:")
    print("  • Results: ./results/comprehensive_study_summary.csv")
    print("  • Figures: ./results/figures/*.png")
    print("  • Paper: ./paper/chapter4_experiments_results.tex")


if __name__ == "__main__":
    main()

