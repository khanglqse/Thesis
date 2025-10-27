"""
Baseline Traffic Environment for evaluating traditional controllers.

This module provides environments specifically designed for testing and
evaluating baseline traffic light controllers (fixed-time, actuated, adaptive, random)
against RL agents in both single and multi-intersection scenarios.
"""

import gymnasium as gym
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from agents.baseline_controllers import (
    TrafficController,
    FixedTimeController,
    ActuatedController,
    AdaptiveController,
    RandomController
)

from .mock_sumo import mock_traci


class BaselineSingleIntersectionEnv(gym.Env):
    """
    Environment for testing baseline controllers on single intersection.
    """

    def __init__(self,
                 controller: TrafficController,
                 max_steps: int = 3600,
                 step_length: float = 1.0,
                 traffic_demand: float = 0.15):
        """
        Initialize baseline single intersection environment.

        Args:
            controller: Baseline controller to evaluate
            max_steps: Maximum steps per episode
            step_length: Simulation step length in seconds
            traffic_demand: Base traffic demand rate
        """
        super(BaselineSingleIntersectionEnv, self).__init__()

        self.controller = controller
        self.max_steps = max_steps
        self.step_length = step_length
        self.traffic_demand = traffic_demand

        # Single intersection setup
        self.intersection_id = 'single_intersection'
        self.intersections = [self.intersection_id]

        # Initialize mock SUMO
        mock_traci.load(self.intersections)

        # Define lane IDs for single intersection
        self.lane_ids = [
            'single_intersection_north_south_0', 'single_intersection_north_south_1',
            'single_intersection_south_north_0', 'single_intersection_south_north_1',
            'single_intersection_east_west_0', 'single_intersection_east_west_1',
            'single_intersection_west_east_0', 'single_intersection_west_east_1'
        ]

        # Action space: 2 phases (0: N-S green, 1: E-W green)
        self.action_space = gym.spaces.Discrete(2)

        # Observation space: queue lengths + waiting times + phase + time
        obs_dim = len(self.lane_ids) * 2 + 1 + 1  # 8 lanes * 2 + phase + time
        self.observation_space = gym.spaces.Box(
            low=0, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        # Environment state
        self.current_step = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        # Reset simulation state
        self.current_step = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

        # Reset controller
        self.controller.reset()

        # Clear mock simulation
        mock_traci.traffic_lights = {self.intersection_id: 0}
        mock_traci.lanes = mock_traci._create_lanes_for_intersection(self.intersection_id)
        mock_traci.simulation_time = 0.0
        mock_traci.vehicles = {}
        mock_traci.vehicle_counter = 0

        # Get initial observation
        obs = self._get_observation()

        return obs, {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step in the environment."""
        # Apply action using baseline controller
        self.controller.select_action(self._get_observation())
        applied_action = self.controller.select_action(self._get_observation())

        # Set traffic light phase
        mock_traci.trafficlight.setPhase(self.intersection_id, applied_action)

        # Advance simulation
        mock_traci.simulationStep(self.step_length)
        self.current_step += 1

        # Get observation
        obs = self._get_observation()

        # Calculate reward
        reward = self._calculate_reward(applied_action)

        # Check if episode is done
        done = self.current_step >= self.max_steps

        # Get info
        info = self._get_info()

        # Store metrics
        self.episode_rewards.append(reward)
        self.episode_waiting_times.append(self._get_total_waiting_time())
        self.episode_throughput.append(self._get_throughput())

        return obs, reward, done, False, info

    def _get_observation(self) -> np.ndarray:
        """Get current observation from mock simulation."""
        # Queue lengths (number of vehicles)
        queue_lengths = [mock_traci.lane.getLastStepVehicleNumber(lane_id)
                        for lane_id in self.lane_ids]

        # Waiting times
        waiting_times = [mock_traci.lane.getWaitingTime(lane_id)
                        for lane_id in self.lane_ids]

        # Current phase and time
        current_phase = mock_traci.trafficlight.getPhase(self.intersection_id)
        current_time = mock_traci.simulation.getTime()

        # Combine into observation
        obs = np.array(queue_lengths + waiting_times + [current_phase, current_time],
                      dtype=np.float32)

        return obs

    def _calculate_reward(self, action: int) -> float:
        """Calculate reward based on traffic efficiency."""
        total_waiting_time = self._get_total_waiting_time()
        throughput = self._get_throughput()

        # Reward function: minimize waiting time, maximize throughput
        reward = -0.1 * total_waiting_time + 0.01 * throughput

        return float(reward)

    def _get_total_waiting_time(self) -> float:
        """Get total waiting time across all lanes."""
        return sum(mock_traci.lane.getWaitingTime(lane_id) for lane_id in self.lane_ids)

    def _get_throughput(self) -> int:
        """Get number of vehicles that have passed through."""
        throughput = 0
        for lane in mock_traci.lanes.values():
            for vehicle in lane.vehicles:
                if vehicle.position >= lane.length * 0.8:
                    throughput += 1
        return throughput

    def _get_info(self) -> Dict[str, Any]:
        """Get additional information about the environment."""
        return {
            'step': self.current_step,
            'controller': type(self.controller).__name__,
            'total_waiting_time': self._get_total_waiting_time(),
            'throughput': self._get_throughput(),
            'avg_reward': np.mean(self.episode_rewards) if self.episode_rewards else 0.0
        }

    def render(self, mode: str = 'human') -> None:
        """Render environment state."""
        if mode == 'human':
            total_waiting = self._get_total_waiting_time()
            throughput = self._get_throughput()
            print(f"Step {self.current_step}: Controller={type(self.controller).__name__}, "
                  f"Waiting={total_waiting:.1f}, Throughput={throughput}")

    def close(self) -> None:
        """Close environment."""
        mock_traci.close()


class BaselineMultiIntersectionEnv(gym.Env):
    """
    Environment for testing baseline controllers on multi-intersection network.
    """

    def __init__(self,
                 controller: TrafficController,
                 max_steps: int = 3600,
                 step_length: float = 1.0,
                 traffic_demand: float = 0.15,
                 coordination: bool = True):
        """
        Initialize baseline multi-intersection environment.

        Args:
            controller: Baseline controller to evaluate
            max_steps: Maximum steps per episode
            step_length: Simulation step length in seconds
            traffic_demand: Base traffic demand rate
            coordination: Whether intersections should coordinate
        """
        super(BaselineMultiIntersectionEnv, self).__init__()

        self.controller = controller
        self.max_steps = max_steps
        self.step_length = step_length
        self.traffic_demand = traffic_demand
        self.coordination = coordination

        # Multi-intersection setup
        self.intersection_ids = ['intersection_1', 'intersection_2', 'intersection_3']
        self.intersections = self.intersection_ids

        # Initialize mock SUMO
        mock_traci.load(self.intersections)

        # Define lane IDs for all intersections
        self.lane_ids = []
        for inter_id in self.intersection_ids:
            self.lane_ids.extend([
                f'{inter_id}_north_south_0', f'{inter_id}_north_south_1',
                f'{inter_id}_south_north_0', f'{inter_id}_south_north_1',
                f'{inter_id}_east_west_0', f'{inter_id}_east_west_1',
                f'{inter_id}_west_east_0', f'{inter_id}_west_east_1'
            ])

        # Action space: Each intersection has 2 phases
        if coordination:
            self.action_space = gym.spaces.Discrete(2)
        else:
            self.action_space = gym.spaces.MultiDiscrete([2, 2, 2])

        # Observation space: queue lengths + waiting times + phases + time
        obs_dim = len(self.lane_ids) * 2 + len(self.intersection_ids) + 1
        self.observation_space = gym.spaces.Box(
            low=0, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        # Environment state
        self.current_step = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        # Reset simulation state
        self.current_step = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

        # Reset controller
        self.controller.reset()

        # Clear mock simulation
        mock_traci.traffic_lights = {inter_id: 0 for inter_id in self.intersection_ids}
        mock_traci.lanes = {}
        for inter_id in self.intersection_ids:
            mock_traci.lanes.update(mock_traci._create_lanes_for_intersection(inter_id))
        mock_traci.simulation_time = 0.0
        mock_traci.vehicles = {}
        mock_traci.vehicle_counter = 0

        # Get initial observation
        obs = self._get_observation()

        return obs, {}

    def step(self, action: Any) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step in the environment."""
        # Apply action(s) using baseline controller
        obs = self._get_observation()

        if self.coordination:
            # All intersections use the same phase
            for inter_id in self.intersection_ids:
                mock_traci.trafficlight.setPhase(inter_id, action)
        else:
            # Each intersection has independent control
            if hasattr(action, '__len__'):
                for i, inter_id in enumerate(self.intersection_ids):
                    if i < len(action):
                        mock_traci.trafficlight.setPhase(inter_id, action[i])

        # Let controller decide actions based on state
        if self.coordination:
            applied_action = self.controller.select_action(obs)
            for inter_id in self.intersection_ids:
                mock_traci.trafficlight.setPhase(inter_id, applied_action)
        else:
            # For independent control, use individual controller decisions
            applied_action = action

        # Advance simulation
        mock_traci.simulationStep(self.step_length)
        self.current_step += 1

        # Get observation
        obs = self._get_observation()

        # Calculate reward
        reward = self._calculate_reward(applied_action)

        # Check if episode is done
        done = self.current_step >= self.max_steps

        # Get info
        info = self._get_info()

        # Store metrics
        self.episode_rewards.append(reward)
        self.episode_waiting_times.append(self._get_total_waiting_time())
        self.episode_throughput.append(self._get_throughput())

        return obs, reward, done, False, info

    def _get_observation(self) -> np.ndarray:
        """Get current observation from mock simulation."""
        # Queue lengths (number of vehicles)
        queue_lengths = [mock_traci.lane.getLastStepVehicleNumber(lane_id)
                        for lane_id in self.lane_ids]

        # Waiting times
        waiting_times = [mock_traci.lane.getWaitingTime(lane_id)
                        for lane_id in self.lane_ids]

        # Current phases and time
        current_phases = [mock_traci.trafficlight.getPhase(inter_id)
                         for inter_id in self.intersection_ids]
        current_time = mock_traci.simulation.getTime()

        # Combine into observation
        obs = np.array(queue_lengths + waiting_times + current_phases + [current_time],
                      dtype=np.float32)

        return obs

    def _calculate_reward(self, action: Any) -> float:
        """Calculate reward based on traffic efficiency across all intersections."""
        total_waiting_time = self._get_total_waiting_time()
        throughput = self._get_throughput()

        # Base reward: minimize waiting time, maximize throughput
        reward = -0.1 * total_waiting_time + 0.01 * throughput

        return float(reward)

    def _get_total_waiting_time(self) -> float:
        """Get total waiting time across all lanes."""
        return sum(mock_traci.lane.getWaitingTime(lane_id) for lane_id in self.lane_ids)

    def _get_throughput(self) -> int:
        """Get number of vehicles that have passed through."""
        throughput = 0
        for lane in mock_traci.lanes.values():
            for vehicle in lane.vehicles:
                if vehicle.position >= lane.length * 0.8:
                    throughput += 1
        return throughput

    def _get_info(self) -> Dict[str, Any]:
        """Get additional information about the environment."""
        return {
            'step': self.current_step,
            'controller': type(self.controller).__name__,
            'total_waiting_time': self._get_total_waiting_time(),
            'throughput': self._get_throughput(),
            'avg_reward': np.mean(self.episode_rewards) if self.episode_rewards else 0.0,
            'coordination': self.coordination
        }

    def render(self, mode: str = 'human') -> None:
        """Render environment state."""
        if mode == 'human':
            total_waiting = self._get_total_waiting_time()
            throughput = self._get_throughput()
            print(f"Step {self.current_step}: Controller={type(self.controller).__name__}, "
                  f"Waiting={total_waiting:.1f}, Throughput={throughput}")

    def close(self) -> None:
        """Close environment."""
        mock_traci.close()


def create_baseline_single_env(controller: TrafficController, **kwargs) -> BaselineSingleIntersectionEnv:
    """Factory function for baseline single intersection environment."""
    return BaselineSingleIntersectionEnv(controller, **kwargs)


def create_baseline_multi_env(controller: TrafficController, **kwargs) -> BaselineMultiIntersectionEnv:
    """Factory function for baseline multi-intersection environment."""
    return BaselineMultiIntersectionEnv(controller, **kwargs)
