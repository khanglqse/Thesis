"""
Traffic environment for training RL agents on single intersection.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Tuple, Optional, List
import sys
import os
import traci
try:
    import sumolib
    SUMO_AVAILABLE = True
except ImportError:
    SUMO_AVAILABLE = False

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sumo_configs import SumoConfigLoader, MockSumoEnvironment


class TrafficEnv(gym.Env):
    """
    Gymnasium environment for traffic light control at a single intersection.
    """
    
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, use_sumo: bool = True, config_type: str = "one_intersection", **kwargs):
        """
        Initialize traffic environment.
        
        Args:
            use_sumo: Whether to use real SUMO or mock environment
            config_type: "one_intersection" or "three_intersections"
        """
        super().__init__()
        
        self.use_sumo = use_sumo and SUMO_AVAILABLE
        self.config_type = config_type
        self.config_loader = SumoConfigLoader(config_type)
        
        if self.use_sumo:
            self.sumo_running = False
        else:
            self.mock_env = MockSumoEnvironment(config_type)
        
        # Environment parameters
        self.simulation_time = 0
        self.max_steps = 1000
        
        # Define observation and action spaces
        # For one intersection: 16 lanes × 3 features (vehicle_count, waiting_time, queue_length) + 1 phase
        self.obs_features_per_lane = 3
        self.num_lanes = 16  # 8 directions × 2 lanes each for one intersection
        
        if config_type == "three_intersections":
            self.num_lanes = 48  # 3 intersections
        
        obs_dim = (self.num_lanes * self.obs_features_per_lane) + 1
        
        self.observation_space = spaces.Box(
            low=0, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )
        
        # Action space: 0 = keep current phase, 1 = switch to other phase
        self.action_space = spaces.Discrete(2)
        
        # State tracking
        self.current_phase = 0
        self.metrics_history = []
        
    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment."""
        super().reset(seed=seed)
        
        self.simulation_time = 0
        self.current_phase = 0
        self.metrics_history = []
        
        if self.use_sumo:
            if self.sumo_running:
                traci.close()
            
            sumoCmd = self.config_loader.get_sumo_command()
            traci.start(sumoCmd)
            self.sumo_running = True
            
        else:
            self.mock_env = MockSumoEnvironment(self.config_type)
        
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step in the environment."""
        # Apply action to traffic light
        if action == 1:
            self.current_phase = 1 - self.current_phase  # Switch phase
        
        # Advance simulation
        if self.use_sumo:
            traci.simulationStep()
        else:
            self.mock_env.step()
        
        self.simulation_time += 1
        
        # Get new observation
        obs = self._get_observation()
        
        # Calculate reward
        reward = self._calculate_reward()
        
        # Check if done
        done = self.simulation_time >= self.max_steps
        truncated = False
        
        # Get info
        info = self._get_info()
        
        return obs, reward, done, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation."""
        obs = []
        
        if self.use_sumo:
            # Get lane IDs
            lane_ids = traci.lane.getIDList()
            
            # Sort for consistency
            lane_ids = sorted(lane_ids)
            
            # Extract features for each lane
            for lane_id in lane_ids:
                vehicle_count = traci.lane.getLastStepVehicleNumber(lane_id)
                waiting_time = traci.lane.getWaitingTime(lane_id)
                queue_length = traci.lane.getLastStepHaltingNumber(lane_id)
                
                obs.extend([vehicle_count, waiting_time, queue_length])
        else:
            # Use mock environment
            for lane_id in sorted(self.mock_env.get_lane_ids()):
                obs.append(self.mock_env.get_vehicle_count(lane_id))
                obs.append(self.mock_env.get_waiting_time(lane_id))
                obs.append(self.mock_env.get_queue_length(lane_id))
        
        # Add current phase
        obs.append(self.current_phase)
        
        return np.array(obs, dtype=np.float32)
    
    def _calculate_reward(self) -> float:
        """Calculate reward for current state."""
        if self.use_sumo:
            # Negative of total waiting time (maximize efficiency)
            total_waiting = sum(traci.lane.getWaitingTime(lane_id) 
                              for lane_id in traci.lane.getIDList())
            
            # Reward is negative normalized waiting time
            reward = -total_waiting / 1000.0
            
            # Penalize long queues
            total_halting = sum(traci.lane.getLastStepHaltingNumber(lane_id) 
                               for lane_id in traci.lane.getIDList())
            reward -= total_halting / 100.0
        else:
            # Mock reward
            total_waiting = sum(self.mock_env.get_waiting_time(lane_id) 
                              for lane_id in self.mock_env.get_lane_ids())
            total_halting = sum(self.mock_env.get_queue_length(lane_id) 
                              for lane_id in self.mock_env.get_lane_ids())
            
            reward = -total_waiting / 1000.0 - total_halting / 100.0
        
        return reward
    
    def _get_info(self) -> Dict:
        """Get additional information about current state."""
        if self.use_sumo:
            total_vehicles = sum(traci.lane.getLastStepVehicleNumber(lane_id) 
                                for lane_id in traci.lane.getIDList())
            total_waiting = sum(traci.lane.getWaitingTime(lane_id) 
                              for lane_id in traci.lane.getIDList())
            total_halting = sum(traci.lane.getLastStepHaltingNumber(lane_id) 
                              for lane_id in traci.lane.getIDList())
        else:
            total_vehicles = sum(self.mock_env.get_vehicle_count(lane_id) 
                                for lane_id in self.mock_env.get_lane_ids())
            total_waiting = sum(self.mock_env.get_waiting_time(lane_id) 
                              for lane_id in self.mock_env.get_lane_ids())
            total_halting = sum(self.mock_env.get_queue_length(lane_id) 
                              for lane_id in self.mock_env.get_lane_ids())
        
        info = {
            'total_vehicles': total_vehicles,
            'total_waiting_time': total_waiting,
            'total_halting': total_halting,
            'current_phase': self.current_phase,
            'simulation_time': self.simulation_time
        }
        
        self.metrics_history.append(info)
        
        return info
    
    def close(self):
        """Close environment."""
        if self.use_sumo and self.sumo_running:
            traci.close()
            self.sumo_running = False
    
    def render(self):
        """Render environment (not implemented for headless mode)."""
        pass

