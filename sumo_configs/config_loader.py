"""
Configuration loader for SUMO and mock SUMO configurations.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class SumoConfigLoader:
    """Load and manage SUMO configuration files."""
    
    def __init__(self, config_type: str = "one_intersection"):
        """
        Initialize configuration loader.
        
        Args:
            config_type: Either "one_intersection" or "three_intersections"
        """
        self.config_type = config_type
        self.base_dir = Path(__file__).parent
        
    def get_network_path(self) -> str:
        """Get path to network file."""
        return str(self.base_dir / self.config_type / "network.net.xml")
    
    def get_routes_path(self) -> str:
        """Get path to routes file."""
        return str(self.base_dir / self.config_type / "routes.rou.xml")
    
    def get_config_path(self) -> str:
        """Get path to SUMO configuration file."""
        return str(self.base_dir / self.config_type / "config.sumocfg")
    
    def get_mock_config(self) -> Dict[str, Any]:
        """Load mock configuration as dictionary."""
        mock_path = self.base_dir / self.config_type / "mock_config.yaml"
        
        if not mock_path.exists():
            raise FileNotFoundError(f"Mock config not found: {mock_path}")
        
        with open(mock_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_sumo_command(self) -> list:
        """
        Get SUMO command for running simulation.
        
        Returns:
            List with sumo command and config path
        """
        return ["sumo", "-c", self.get_config_path()]
    
    def get_sumo_gui_command(self) -> list:
        """
        Get SUMO GUI command for running simulation with GUI.
        
        Returns:
            List with sumo-gui command and config path
        """
        return ["sumo-gui", "-c", self.get_config_path()]


class MockSumoEnvironment:
    """
    Mock SUMO environment for testing without full SUMO installation.
    """
    
    def __init__(self, config_type: str = "one_intersection"):
        """
        Initialize mock SUMO environment.
        
        Args:
            config_type: Either "one_intersection" or "three_intersections"
        """
        self.loader = SumoConfigLoader(config_type)
        self.config = self.loader.get_mock_config()
        self.step_count = 0
        
        # Initialize mock state
        self.initialize_mock_state()
    
    def initialize_mock_state(self):
        """Initialize mock traffic state."""
        self.lanes = {}
        
        for lane_config in self.config['network']['lanes']:
            lane_id = lane_config['id']
            self.lanes[lane_id] = {
                'vehicle_count': 0,
                'waiting_time': 0.0,
                'queue_length': 0
            }
        
        # Initialize traffic lights
        self.traffic_lights = {}
        for tl_config in self.config['traffic_light']['intersections']:
            tl_id = tl_config['id']
            self.traffic_lights[tl_id] = {
                'current_phase': tl_config['current_phase'],
                'phases': tl_config['phases']
            }
    
    def get_lane_ids(self) -> list:
        """Get list of all lane IDs."""
        return list(self.lanes.keys())
    
    def get_vehicle_count(self, lane_id: str) -> int:
        """Get vehicle count on a lane."""
        return self.lanes.get(lane_id, {}).get('vehicle_count', 0)
    
    def get_waiting_time(self, lane_id: str) -> float:
        """Get waiting time on a lane."""
        return self.lanes.get(lane_id, {}).get('waiting_time', 0.0)
    
    def get_queue_length(self, lane_id: str) -> int:
        """Get queue length on a lane."""
        return self.lanes.get(lane_id, {}).get('queue_length', 0)
    
    def get_traffic_light_phase(self, tl_id: str) -> int:
        """Get current traffic light phase."""
        return self.traffic_lights.get(tl_id, {}).get('current_phase', 0)
    
    def get_state_vector(self) -> list:
        """
        Get state vector for RL agent.
        
        Returns:
            State vector with features from all lanes
        """
        state = []
        
        # Add features for each lane
        for lane_id, lane_data in self.lanes.items():
            state.append(lane_data['vehicle_count'])
            state.append(lane_data['waiting_time'])
            state.append(lane_data['queue_length'])
        
        # Add traffic light states
        for tl_id, tl_data in self.traffic_lights.items():
            state.append(tl_data['current_phase'])
        
        return state
    
    def step(self):
        """Advance simulation by one step."""
        # Simulate simple traffic dynamics
        import numpy as np
        
        for lane_id, lane_data in self.lanes.items():
            # Random vehicle arrival/departure
            if np.random.random() < 0.1:
                lane_data['vehicle_count'] += 1
            if lane_data['vehicle_count'] > 0 and np.random.random() < 0.15:
                lane_data['vehicle_count'] -= 1
            
            # Update waiting time
            if lane_data['vehicle_count'] > 0:
                lane_data['waiting_time'] += 0.5
            else:
                lane_data['waiting_time'] = max(0, lane_data['waiting_time'] - 0.1)
            
            # Update queue length
            lane_data['queue_length'] = int(lane_data['vehicle_count'] * 0.8)
        
        self.step_count += 1


def load_config(config_type: str = "one_intersection", use_mock: bool = False) -> Any:
    """
    Load SUMO configuration.
    
    Args:
        config_type: "one_intersection" or "three_intersections"
        use_mock: If True, return mock environment instead of real config
        
    Returns:
        SumoConfigLoader or MockSumoEnvironment
    """
    if use_mock:
        return MockSumoEnvironment(config_type)
    else:
        return SumoConfigLoader(config_type)


# Example usage
if __name__ == "__main__":
    # Load real SUMO configuration
    print("Loading real SUMO configuration...")
    loader = load_config("one_intersection", use_mock=False)
    print(f"Network: {loader.get_network_path()}")
    print(f"Sumo command: {loader.get_sumo_command()}")
    
    # Load mock configuration
    print("\nLoading mock configuration...")
    mock_env = load_config("one_intersection", use_mock=True)
    print(f"Available lanes: {len(mock_env.get_lane_ids())}")
    print(f"State dimension: {len(mock_env.get_state_vector())}")
    
    # Run a few simulation steps
    print("\nRunning mock simulation...")
    for _ in range(5):
        mock_env.step()
        state = mock_env.get_state_vector()
        print(f"Step {mock_env.step_count}: Vehicle count on first lane = {state[0]}")

