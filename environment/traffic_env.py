"""
Custom OpenAI Gym environment for traffic light control using SUMO.
"""

import gymnasium as gym
import numpy as np
try:
    import traci
    import sumolib
    SUMO_AVAILABLE = True
except ImportError:
    print("SUMO/TraCI not available. Running in mock mode for testing.")
    SUMO_AVAILABLE = False
    # Create mock modules for testing
    class MockTraCI:
        @staticmethod
        def start(*args, **kwargs):
            print("Mock TraCI: start() called")
        @staticmethod
        def close():
            print("Mock TraCI: close() called")
        class lane:
            @staticmethod
            def getIDList(): return ['north_south_0', 'north_south_1', 'south_north_0', 'south_north_1', 'east_west_0', 'east_west_1', 'west_east_0', 'west_east_1']
            @staticmethod
            def getLastStepVehicleNumber(*args): return 5
            @staticmethod
            def getWaitingTime(*args): return 10.0
        class trafficlight:
            @staticmethod
            def getPhase(*args): return 0
            @staticmethod
            def setPhase(*args, **kwargs): pass
        class simulation:
            @staticmethod
            def getTime(): return 0.0
            @staticmethod
            def getMinExpectedNumber(): return 100
            @staticmethod
            def getArrivedNumber(): return 0
            @staticmethod
            def simulationStep(): pass
    traci = MockTraCI()
    sumolib = None
from typing import Dict, List, Tuple, Optional, Any
import os
import subprocess
from .sumo_utils import generate_network_xml, generate_routes_xml, generate_sumocfg, start_sumo
from .reward_functions import calculate_combined_reward


class TrafficLightEnv(gym.Env):
    """
    Traffic Light Control Environment using SUMO and TraCI.

    This environment simulates a traffic intersection where an RL agent
    controls traffic light phases to optimize traffic flow.
    """

    def __init__(self,
                 config: Dict[str, Any] = None,
                 use_gui: bool = False,
                 reward_function: str = 'combined',
                 max_steps: int = 3600,
                 step_length: float = 1.0):
        """
        Initialize the traffic environment.

        Args:
            config: Environment configuration parameters
            use_gui: Whether to use SUMO GUI
            reward_function: Type of reward function to use
            max_steps: Maximum steps per episode
            step_length: SUMO simulation step length in seconds
        """
        super(TrafficLightEnv, self).__init__()

        # Configuration
        self.config = config or {}
        self.use_gui = use_gui
        self.reward_function = reward_function
        self.max_steps = max_steps
        self.step_length = step_length

        # SUMO setup
        self.sumo_process = None
        self.cfg_file = None
        self.network_file = None
        self.routes_file = None

        # Environment state
        self.current_step = 0
        # Multi-intersection system with 3 intersections
        self.intersection_ids = ['intersection_1', 'intersection_2', 'intersection_3']

        # Define all lane IDs for 3-intersection system
        self.lane_ids = []
        for inter_id in self.intersection_ids:
            self.lane_ids.extend([
                f'{inter_id}_north_south_0', f'{inter_id}_north_south_1',
                f'{inter_id}_south_north_0', f'{inter_id}_south_north_1',
                f'{inter_id}_east_west_0', f'{inter_id}_east_west_1',
                f'{inter_id}_west_east_0', f'{inter_id}_west_east_1'
            ])

        # For simplicity, we'll control all intersections with the same action
        # Action space: 2 phases (0: N-S green for all, 1: E-W green for all)
        self.action_space = gym.spaces.Discrete(2)

        # Observation space: queue lengths, waiting times for all intersections + phase states + time
        obs_dim = len(self.lane_ids) * 2 + len(self.intersection_ids) + 1  # queue_lengths + waiting_times + phases + time_elapsed
        self.observation_space = gym.spaces.Box(
            low=0, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        # Initialize SUMO files
        self._setup_sumo_files()

        # Previous state for reward calculation
        self.previous_waiting_times = None
        self.previous_queue_lengths = None

    def _setup_sumo_files(self):
        """Setup SUMO network, routes, and configuration files."""
        # Network configuration
        network_config = {
            'junction_x': 0.0,
            'junction_y': 0.0,
            'edge_length': 200.0
        }

        # Route configuration
        route_config = {
            'vehicle_types': ['car'],
            'routes': ['north_south', 'south_north', 'east_west', 'west_east']
        }

        # SUMO configuration
        sumo_config = {
            'end_time': self.max_steps * self.step_length,
            'step_length': self.step_length
        }

        # Generate files
        self.network_file = generate_network_xml(network_config)
        self.routes_file = generate_routes_xml(route_config)
        self.cfg_file = generate_sumocfg(sumo_config)

    def _get_observation(self) -> np.ndarray:
        """Get current observation from SUMO for 3-intersection system."""
        try:
            # Get queue lengths for all lanes across all intersections
            queue_lengths = []
            for lane_id in self.lane_ids:
                try:
                    queue_length = traci.lane.getLastStepVehicleNumber(lane_id)
                    queue_lengths.append(queue_length)
                except:
                    queue_lengths.append(0)

            # Get waiting times for all lanes across all intersections
            waiting_times = []
            for lane_id in self.lane_ids:
                try:
                    waiting_time = traci.lane.getWaitingTime(lane_id)
                    waiting_times.append(waiting_time)
                except:
                    waiting_times.append(0)

            # Get current traffic light phases for all intersections
            phases = []
            for inter_id in self.intersection_ids:
                try:
                    current_phase = traci.trafficlight.getPhase(inter_id)
                    phases.append(current_phase)
                except:
                    phases.append(0)

            # Get time elapsed
            time_elapsed = traci.simulation.getTime()

            # Combine into observation vector
            obs = np.array(queue_lengths + waiting_times + phases + [time_elapsed],
                          dtype=np.float32)

            return obs

        except Exception as e:
            print(f"Error getting observation: {e}")
            return np.zeros(self.observation_space.shape, dtype=np.float32)

    def _calculate_reward(self, action: int) -> float:
        """Calculate reward for the current state and action across 3 intersections."""
        try:
            # Get current state from all intersections
            current_waiting_times = np.array([
                traci.lane.getWaitingTime(lane_id) for lane_id in self.lane_ids
                if lane_id in traci.lane.getIDList()
            ])

            current_queue_lengths = np.array([
                traci.lane.getLastStepVehicleNumber(lane_id) for lane_id in self.lane_ids
                if lane_id in traci.lane.getIDList()
            ])

            # Calculate throughput (vehicles that passed through all intersections)
            throughput = traci.simulation.getArrivedNumber()

            # Use combined reward function for multi-intersection system
            if self.reward_function == 'combined':
                reward = calculate_combined_reward(
                    current_waiting_times,
                    current_queue_lengths,
                    throughput,
                    self.previous_waiting_times,
                    self.previous_queue_lengths
                )
            elif self.reward_function == 'waiting_time':
                reward = -np.sum(current_waiting_times)
            elif self.reward_function == 'queue_length':
                reward = -np.sum(current_queue_lengths)
            elif self.reward_function == 'throughput':
                reward = throughput * 10.0
            else:
                reward = -np.sum(current_waiting_times)

            # Update previous state
            self.previous_waiting_times = current_waiting_times
            self.previous_queue_lengths = current_queue_lengths

            return float(reward)

        except Exception as e:
            print(f"Error calculating reward: {e}")
            return 0.0

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """
        Reset the environment.

        Args:
            seed: Random seed for reproducibility
            options: Additional options for reset

        Returns:
            Initial observation and info dictionary
        """
        super().reset(seed=seed)

        # Close existing SUMO connection if any
        try:
            traci.close()
        except:
            pass

        # Start new SUMO simulation
        self.sumo_process = start_sumo(self.cfg_file)
        if self.sumo_process is None and SUMO_AVAILABLE:
            print("WARNING: SUMO process could not start, continuing in mock mode")
        elif self.sumo_process is None:
            # Mock mode - process is None but that's OK for testing
            pass

        # Connect to TraCI
        if SUMO_AVAILABLE:
            try:
                # Try to find sumo in PATH
                import shutil
                sumo_binary = shutil.which("sumo")
                if sumo_binary:
                    traci.start([sumo_binary, "-c", self.cfg_file])
                else:
                    raise FileNotFoundError("sumo")
            except (FileNotFoundError, Exception) as e:
                # If SUMO not found, run in mock mode
                print(f"SUMO not found: {e}")
                print("Running in mock mode - no real simulation")
                # Create a minimal mock sumo process
                self.sumo_process = None
        else:
            # Mock mode - just print that we're starting
            print("Mock mode: Simulation started")

        # Reset state
        self.current_step = 0
        self.previous_waiting_times = None
        self.previous_queue_lengths = None

        # Set traffic lights to initial phase for all intersections
        for inter_id in self.intersection_ids:
            try:
                traci.trafficlight.setPhase(inter_id, 0)
            except:
                pass

        # Get initial observation
        obs = self._get_observation()

        return obs, {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one step in the environment.

        Args:
            action: Traffic light phase to set (0 or 1)

        Returns:
            Next observation, reward, terminated, truncated, info
        """
        try:
            # Set traffic light phase for all intersections (same action for all)
            for inter_id in self.intersection_ids:
                traci.trafficlight.setPhase(inter_id, action)

            # Advance simulation by one step
            if SUMO_AVAILABLE:
                traci.simulationStep()
            else:
                # In mock mode, just increment time
                pass

            # Get next state
            obs = self._get_observation()

            # Calculate reward
            reward = self._calculate_reward(action)

            # Check termination conditions
            terminated = traci.simulation.getMinExpectedNumber() <= 0
            truncated = self.current_step >= self.max_steps

            self.current_step += 1

            info = {
                'step': self.current_step,
                'simulation_time': traci.simulation.getTime(),
                'total_vehicles': traci.simulation.getArrivedNumber(),
                'intersections': len(self.intersection_ids)
            }

            return obs, reward, terminated, truncated, info

        except Exception as e:
            print(f"Error in step: {e}")
            # Return default values
            obs = np.zeros(self.observation_space.shape, dtype=np.float32)
            return obs, 0.0, True, False, {}

    def render(self, mode: str = 'human'):
        """Render the environment (placeholder for compatibility)."""
        pass

    def close(self):
        """Close the environment and clean up resources."""
        if SUMO_AVAILABLE:
            try:
                traci.close()
            except:
                pass

        if self.sumo_process:
            try:
                self.sumo_process.terminate()
                self.sumo_process.wait()
            except:
                pass

        # Clean up generated files
        for file_path in [self.network_file, self.routes_file, self.cfg_file]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.close()


def create_env(use_gui: bool = False, **kwargs) -> TrafficLightEnv:
    """
    Factory function to create traffic light environment.

    Args:
        use_gui: Whether to use SUMO GUI
        **kwargs: Additional arguments for TrafficLightEnv

    Returns:
        Configured TrafficLightEnv instance
    """
    return TrafficLightEnv(use_gui=use_gui, **kwargs)
