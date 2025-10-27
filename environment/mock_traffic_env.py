"""
Mock Traffic Environment for RL Training.

This module provides realistic traffic simulation environments for training
RL agents without requiring SUMO installation. It includes both single
and multi-intersection scenarios.
"""

import gymnasium as gym
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import os
from .mock_sumo import mock_traci, MockTraCI


class SingleIntersectionMockEnv(gym.Env):
    """
    Mock traffic environment for a single intersection.

    This environment simulates a single 4-way intersection with realistic
    traffic patterns for training RL agents.
    """

    def __init__(self,
                 config: Dict[str, Any] = None,
                 max_steps: int = 3600,
                 step_length: float = 1.0,
                 traffic_demand: float = 0.15):
        """
        Initialize single intersection environment.

        Args:
            config: Environment configuration
            max_steps: Maximum steps per episode
            step_length: Simulation step length in seconds
            traffic_demand: Base traffic demand rate
        """
        super(SingleIntersectionMockEnv, self).__init__()

        self.config = config or {}
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
        self.current_phase = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        # Reset simulation state
        self.current_step = 0
        self.current_phase = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

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
        # Apply action (set traffic light phase)
        mock_traci.trafficlight.setPhase(self.intersection_id, action)
        self.current_phase = action

        # Advance simulation
        mock_traci.simulationStep(self.step_length)
        self.current_step += 1

        # Get observation
        obs = self._get_observation()

        # Calculate reward
        reward = self._calculate_reward(action)

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
        # Simplified throughput measure
        return sum(len(lane.vehicles) for lane in mock_traci.lanes.values()
                  if lane.vehicles and any(v.position >= lane.length * 0.8 for v in lane.vehicles))

    def _get_info(self) -> Dict[str, Any]:
        """Get additional information about the environment."""
        return {
            'step': self.current_step,
            'phase': self.current_phase,
            'total_waiting_time': self._get_total_waiting_time(),
            'throughput': self._get_throughput(),
            'avg_reward': np.mean(self.episode_rewards) if self.episode_rewards else 0.0
        }

    def render(self, mode: str = 'human') -> None:
        """Render environment state."""
        if mode == 'human':
            total_waiting = self._get_total_waiting_time()
            throughput = self._get_throughput()
            print(f"Step {self.current_step}: Phase={self.current_phase}, "
                  f"Waiting={total_waiting:.1f}, Throughput={throughput}")

    def close(self) -> None:
        """Close environment."""
        mock_traci.close()


class MultiIntersectionMockEnv(gym.Env):
    """
    Mock traffic environment for multiple intersections (3 intersections).

    This environment simulates a 3-intersection network with realistic
    traffic coordination challenges for training RL agents.
    """

    def __init__(self,
                 config: Dict[str, Any] = None,
                 max_steps: int = 3600,
                 step_length: float = 1.0,
                 traffic_demand: float = 0.15,
                 coordination: bool = True):
        """
        Initialize multi-intersection environment.

        Args:
            config: Environment configuration
            max_steps: Maximum steps per episode
            step_length: Simulation step length in seconds
            traffic_demand: Base traffic demand rate
            coordination: Whether intersections should coordinate
        """
        super(MultiIntersectionMockEnv, self).__init__()

        self.config = config or {}
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
        # If coordination=True, all intersections use same action
        # If coordination=False, each intersection has independent control
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
        self.current_phases = [0] * len(self.intersection_ids)
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        # Reset simulation state
        self.current_step = 0
        self.current_phases = [0] * len(self.intersection_ids)
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

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
        # Apply action(s)
        if self.coordination:
            # All intersections use the same phase
            for inter_id in self.intersection_ids:
                mock_traci.trafficlight.setPhase(inter_id, action)
                self.current_phases = [action] * len(self.intersection_ids)
        else:
            # Each intersection has independent control
            if hasattr(action, '__len__'):
                for i, inter_id in enumerate(self.intersection_ids):
                    if i < len(action):
                        mock_traci.trafficlight.setPhase(inter_id, action[i])
                        self.current_phases[i] = action[i]

        # Advance simulation
        mock_traci.simulationStep(self.step_length)
        self.current_step += 1

        # Get observation
        obs = self._get_observation()

        # Calculate reward
        reward = self._calculate_reward(action)

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

        # Coordination penalty if not coordinated
        if not self.coordination:
            # Penalize if adjacent intersections have conflicting phases
            coordination_penalty = 0
            if len(self.current_phases) >= 2:
                # Simple coordination: adjacent intersections should not have opposite phases
                for i in range(len(self.current_phases) - 1):
                    if self.current_phases[i] != self.current_phases[i + 1]:
                        coordination_penalty += 5.0
            reward -= coordination_penalty

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
            'phases': self.current_phases,
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
            print(f"Step {self.current_step}: Phases={self.current_phases}, "
                  f"Waiting={total_waiting:.1f}, Throughput={throughput}")

    def close(self) -> None:
        """Close environment."""
        mock_traci.close()


def create_single_intersection_env(**kwargs) -> SingleIntersectionMockEnv:
    """Factory function for single intersection environment."""
    return SingleIntersectionMockEnv(**kwargs)


def create_multi_intersection_env(**kwargs) -> MultiIntersectionMockEnv:
    """Factory function for multi-intersection environment."""
    return MultiIntersectionMockEnv(**kwargs)
