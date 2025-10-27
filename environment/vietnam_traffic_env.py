"""
Vietnam Traffic Environment for RL Training.

This module provides realistic Vietnamese traffic simulation with high motorcycle
density, chaotic traffic patterns, and urban congestion typical of Vietnamese cities.
"""

import os
import sys
import gymnasium as gym
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import random

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mock_sumo import mock_traci, MockTraCI, get_vietnam_mock_traci


class VehicleType(Enum):
    """Vietnamese vehicle types with realistic proportions."""
    MOTORCYCLE = "motorcycle"  # 65% - Xe máy
    CAR = "car"                # 25% - Ô tô
    TRUCK = "truck"            # 5% - Xe tải
    BUS = "bus"                # 5% - Xe buýt


class VietnamVehicle:
    """Vehicle in Vietnamese traffic simulation."""

    def __init__(self, vehicle_type: VehicleType, route: str):
        self.id = f"viet_{random.randint(100000, 999999)}"
        self.type = vehicle_type
        self.route = route
        self.speed = 0.0
        self.waiting_time = 0.0
        self.position = 0.0
        self.arrival_time = 0.0
        self.priority = self._get_priority()

    def _get_priority(self) -> float:
        """Get priority for different vehicle types."""
        priorities = {
            VehicleType.MOTORCYCLE: 1.0,  # Xe máy ưu tiên cao nhất
            VehicleType.CAR: 0.7,
            VehicleType.BUS: 0.8,        # Xe buýt cũng ưu tiên
            VehicleType.TRUCK: 0.5       # Xe tải ưu tiên thấp
        }
        return priorities[self.type]


class VietnamLane:
    """Lane in Vietnamese traffic system."""

    def __init__(self, lane_id: str):
        self.id = lane_id
        self.vehicles: List[VietnamVehicle] = []
        self.length = 150.0  # Đường ngắn hơn ở VN
        self.max_speed = self._get_max_speed()

    def _get_max_speed(self) -> float:
        """Get max speed based on lane type."""
        if 'highway' in self.id:
            return 16.7  # 60 km/h
        elif 'main' in self.id:
            return 13.9  # 50 km/h
        else:
            return 11.1  # 40 km/h (đường nhỏ)


class VietnamMockTraCI:
    """
    Vietnam-specific mock TraCI implementation.

    Simulates Vietnamese traffic with:
    - High motorcycle density (65%)
    - Chaotic traffic patterns
    - Aggressive driving behavior
    - High congestion periods
    """

    def __init__(self):
        self.simulation_time = 0.0
        self.traffic_lights = {}
        self.lanes: Dict[str, VietnamLane] = {}
        self.vehicles: Dict[str, VietnamVehicle] = {}
        self.intersections = []
        self.vehicle_counter = 0

        # Vietnam traffic characteristics
        self.motorcycle_ratio = 0.65
        self.rush_hour_multiplier = 2.5
        self.base_demand = 0.25  # Higher than standard (0.15)

    @staticmethod
    def start(cmd: List[str], **kwargs) -> None:
        """Mock TraCI start for Vietnam traffic."""
        print("🏍️  Vietnam Mock SUMO: Starting Vietnamese traffic simulation...")

    @staticmethod
    def close() -> None:
        """Mock TraCI close."""
        print("🏍️  Vietnam Mock SUMO: Closing Vietnamese traffic simulation...")

    def load(self, intersections: List[str]) -> None:
        """Load Vietnam intersection configuration."""
        self.intersections = intersections
        self.traffic_lights = {inter_id: 0 for inter_id in intersections}

        # Initialize lanes for each intersection
        for inter_id in intersections:
            self.lanes.update(self._create_vietnam_lanes_for_intersection(inter_id))

        print(f"🏍️  Vietnam Mock SUMO: Loaded {len(intersections)} intersections for Vietnam traffic")

    def _create_vietnam_lanes_for_intersection(self, inter_id: str) -> Dict[str, VietnamLane]:
        """Create Vietnam-specific lanes for intersection."""
        lanes = {}

        # Vietnamese intersections typically have more complex lane configurations
        directions = ['north_south', 'south_north', 'east_west', 'west_east']

        for direction in directions:
            # More lanes per direction in Vietnam (3 instead of 2)
            for lane_num in [0, 1, 2]:
                lane_id = f'{inter_id}_{direction}_{lane_num}'

                # Leftmost lane for motorcycles only
                if lane_num == 0:
                    lane_id = f'{inter_id}_{direction}_motorcycle'
                    lanes[lane_id] = VietnamLane(lane_id)
                else:
                    lanes[f'{inter_id}_{direction}_{lane_num}'] = VietnamLane(f'{inter_id}_{direction}_{lane_num}')

        return lanes

    def simulationStep(self, step: float = 1.0) -> None:
        """Advance Vietnamese traffic simulation."""
        self.simulation_time += step

        # Generate Vietnam traffic
        self._generate_vietnam_traffic()

        # Update traffic flow with Vietnamese characteristics
        self._update_vietnam_traffic_flow()

        # Update traffic lights with Vietnam patterns
        self._update_vietnam_traffic_lights()

    def _generate_vietnam_traffic(self) -> None:
        """Generate Vietnamese traffic with high motorcycle density."""
        # Vietnam rush hour: 6-9 AM, 11-14 PM, 16-20 PM
        hour = (self.simulation_time / 3600) % 24

        # High demand during extended rush hours
        if (6 <= hour <= 9) or (11 <= hour <= 14) or (16 <= hour <= 20):
            demand_multiplier = self.rush_hour_multiplier
        elif 7 <= hour <= 21:
            demand_multiplier = 1.5
        else:
            demand_multiplier = 0.8

        current_demand = self.base_demand * demand_multiplier

        # Generate traffic for each lane
        for lane in self.lanes.values():
            if random.random() < current_demand:
                self._add_vietnam_vehicle_to_lane(lane)

    def _add_vietnam_vehicle_to_lane(self, lane: VietnamLane) -> None:
        """Add Vietnamese vehicle to lane."""
        self.vehicle_counter += 1
        vehicle_id = f'viet_{self.vehicle_counter}'

        # Vietnam vehicle distribution
        rand = random.random()
        if rand < self.motorcycle_ratio:
            vehicle_type = VehicleType.MOTORCYCLE
        elif rand < self.motorcycle_ratio + 0.25:
            vehicle_type = VehicleType.CAR
        elif rand < self.motorcycle_ratio + 0.30:
            vehicle_type = VehicleType.BUS
        else:
            vehicle_type = VehicleType.TRUCK

        # Vietnam route patterns (more turning, complex routes)
        routes = ['north_south', 'south_north', 'east_west', 'west_east',
                 'north_east', 'south_west', 'east_north', 'west_south']
        route = random.choice(routes)

        vehicle = VietnamVehicle(vehicle_type, route)
        vehicle.arrival_time = self.simulation_time

        lane.vehicles.append(vehicle)
        self.vehicles[vehicle.id] = vehicle

    def _update_vietnam_traffic_flow(self) -> None:
        """Update Vietnamese traffic with aggressive behavior."""
        for lane in self.lanes.values():
            # Sort vehicles by priority (motorcycles first)
            lane.vehicles.sort(key=lambda v: v.priority, reverse=True)

            for vehicle in lane.vehicles:
                # Update waiting time
                if vehicle.speed < 0.1:
                    vehicle.waiting_time += 1.0
                else:
                    vehicle.waiting_time = 0.0

                # Vietnamese driving behavior
                traffic_light = self._get_traffic_light_for_lane(lane.id)
                max_speed = self._get_max_speed_for_vehicle(vehicle, lane)

                if traffic_light == 0:  # Green for N-S
                    if self._can_go_vietnam(vehicle, lane, 'north_south'):
                        vehicle.speed = min(vehicle.speed + 2.0, max_speed)
                        vehicle.position = min(vehicle.position + vehicle.speed, lane.length)
                    else:
                        vehicle.speed = max(vehicle.speed - 1.5, 0.0)
                else:  # Green for E-W
                    if self._can_go_vietnam(vehicle, lane, 'east_west'):
                        vehicle.speed = min(vehicle.speed + 2.0, max_speed)
                        vehicle.position = min(vehicle.position + vehicle.speed, lane.length)
                    else:
                        vehicle.speed = max(vehicle.speed - 1.5, 0.0)

                # Aggressive Vietnamese behavior: motorcycles can filter through
                if vehicle.type == VehicleType.MOTORCYCLE and vehicle.speed < 0.1:
                    # Motorcycles can move even when cars are stopped
                    vehicle.position = min(vehicle.position + 1.0, lane.length)

                # Remove vehicles that have exited
                if vehicle.position >= lane.length:
                    lane.vehicles.remove(vehicle)
                    if vehicle.id in self.vehicles:
                        del self.vehicles[vehicle.id]

    def _can_go_vietnam(self, vehicle: VietnamVehicle, lane: VietnamLane, direction: str) -> bool:
        """Check if vehicle can proceed in Vietnamese traffic."""
        # Motorcycles can go in their direction
        if vehicle.type == VehicleType.MOTORCYCLE:
            return direction in lane.id or 'motorcycle' in lane.id

        # Cars and trucks follow standard rules
        return direction in lane.id

    def _get_max_speed_for_vehicle(self, vehicle: VietnamVehicle, lane: VietnamLane) -> float:
        """Get max speed for Vietnamese vehicle types."""
        speeds = {
            VehicleType.MOTORCYCLE: lane.max_speed * 1.2,  # Xe máy đi nhanh hơn
            VehicleType.CAR: lane.max_speed * 0.9,
            VehicleType.BUS: lane.max_speed * 0.8,        # Xe buýt chậm hơn
            VehicleType.TRUCK: lane.max_speed * 0.7       # Xe tải chậm nhất
        }
        return speeds[vehicle.type]

    def _get_traffic_light_for_lane(self, lane_id: str) -> int:
        """Get traffic light phase for Vietnamese lane."""
        parts = lane_id.split('_')
        if len(parts) >= 1:
            inter_id = parts[0]
            return self.traffic_lights.get(inter_id, 0)
        return 0

    def _update_vietnam_traffic_lights(self) -> None:
        """Update traffic lights with Vietnamese patterns."""
        for inter_id in self.intersections:
            # Vietnamese adaptive control - prioritize motorcycle lanes
            ns_lanes = [lane for lane_id, lane in self.lanes.items()
                       if lane_id.startswith(inter_id) and
                       ('north_south' in lane_id or 'south_north' in lane_id)]

            ew_lanes = [lane for lane_id, lane in self.lanes.items()
                       if lane_id.startswith(inter_id) and
                       ('east_west' in lane_id or 'west_east' in lane_id)]

            # Count motorcycles vs cars
            ns_motorcycles = sum(1 for lane in ns_lanes for v in lane.vehicles
                               if v.type == VehicleType.MOTORCYCLE)
            ew_motorcycles = sum(1 for lane in ew_lanes for v in lane.vehicles
                               if v.type == VehicleType.MOTORCYCLE)

            ns_total = sum(len(lane.vehicles) for lane in ns_lanes)
            ew_total = sum(len(lane.vehicles) for lane in ew_lanes)

            # Vietnamese logic: prioritize direction with more motorcycles
            if ns_motorcycles > ew_motorcycles * 1.3 and self.traffic_lights[inter_id] == 1:
                self.traffic_lights[inter_id] = 0
            elif ew_motorcycles > ns_motorcycles * 1.3 and self.traffic_lights[inter_id] == 0:
                self.traffic_lights[inter_id] = 1

    # Properties for compatibility
    @property
    def lane(self):
        """Mock lane operations for Vietnam."""
        return VietnamLaneOperations(self)

    @property
    def trafficlight(self):
        """Mock traffic light operations for Vietnam."""
        return VietnamTrafficLightOperations(self)

    @property
    def simulation(self):
        """Mock simulation operations for Vietnam."""
        return VietnamSimulationOperations(self)


class VietnamLaneOperations:
    """Vietnam-specific lane operations."""

    def __init__(self, vietnam_traci):
        self.traci = vietnam_traci

    def getIDList(self) -> List[str]:
        """Get list of all lane IDs."""
        return list(self.traci.lanes.keys())

    def getLastStepVehicleNumber(self, lane_id: str) -> int:
        """Get number of vehicles in Vietnamese lane."""
        if lane_id in self.traci.lanes:
            return len(self.traci.lanes[lane_id].vehicles)
        return 0

    def getWaitingTime(self, lane_id: str) -> float:
        """Get total waiting time for vehicles in Vietnamese lane."""
        if lane_id in self.traci.lanes:
            lane = self.traci.lanes[lane_id]
            # Weight waiting time by vehicle type (motorcycles more important)
            total_waiting = 0
            for vehicle in lane.vehicles:
                if vehicle.type == VehicleType.MOTORCYCLE:
                    total_waiting += vehicle.waiting_time * 1.5  # Motorcycles more important
                else:
                    total_waiting += vehicle.waiting_time
            return total_waiting
        return 0.0


class VietnamTrafficLightOperations:
    """Vietnam-specific traffic light operations."""

    def __init__(self, vietnam_traci):
        self.traci = vietnam_traci

    def getPhase(self, intersection_id: str) -> int:
        """Get current phase of Vietnamese traffic light."""
        if intersection_id in self.traci.traffic_lights:
            return self.traci.traffic_lights[intersection_id]
        return 0

    def setPhase(self, intersection_id: str, phase: int) -> None:
        """Set Vietnamese traffic light phase."""
        if intersection_id in self.traci.traffic_lights:
            self.traci.traffic_lights[intersection_id] = phase


class VietnamSimulationOperations:
    """Vietnam-specific simulation operations."""

    def __init__(self, vietnam_traci):
        self.traci = vietnam_traci

    def getTime(self) -> float:
        """Get current Vietnamese simulation time."""
        return self.traci.simulation_time

    def getMinExpectedNumber(self) -> int:
        """Get minimum expected number of vehicles in Vietnamese traffic."""
        return sum(len(lane.vehicles) for lane in self.traci.lanes.values())

    def getArrivedNumber(self) -> int:
        """Get number of vehicles that have arrived in Vietnamese traffic."""
        return 0


# Global Vietnam mock TraCI instance


class VietnamSingleIntersectionEnv(gym.Env):
    """
    Vietnamese traffic environment for single intersection.

    Simulates typical Vietnamese urban intersection with high motorcycle density
    and chaotic traffic patterns.
    """

    def __init__(self,
                 config: Dict[str, Any] = None,
                 max_steps: int = 3600,
                 step_length: float = 1.0,
                 traffic_demand: float = 0.25):
        """
        Initialize Vietnamese single intersection environment.

        Args:
            config: Environment configuration
            max_steps: Maximum steps per episode
            step_length: Simulation step length in seconds
            traffic_demand: Base traffic demand rate (higher for Vietnam)
        """
        super(VietnamSingleIntersectionEnv, self).__init__()

        self.config = config or {}
        self.max_steps = max_steps
        self.step_length = step_length
        self.traffic_demand = traffic_demand

        # Single intersection setup
        self.intersection_id = 'vietnam_single'
        self.intersections = [self.intersection_id]

        # Initialize Vietnam mock SUMO
        self.vietnam_traci = get_vietnam_mock_traci()
        self.vietnam_traci.load(self.intersections)

        # Define lane IDs for Vietnamese intersection
        self.lane_ids = [
            'vietnam_single_north_south_motorcycle',
            'vietnam_single_north_south_1', 'vietnam_single_north_south_2',
            'vietnam_single_south_north_motorcycle',
            'vietnam_single_south_north_1', 'vietnam_single_south_north_2',
            'vietnam_single_east_west_motorcycle',
            'vietnam_single_east_west_1', 'vietnam_single_east_west_2',
            'vietnam_single_west_east_motorcycle',
            'vietnam_single_west_east_1', 'vietnam_single_west_east_2'
        ]

        # Action space: 2 phases (0: N-S green, 1: E-W green)
        self.action_space = gym.spaces.Discrete(2)

        # Vietnam observation space: more complex due to motorcycle lanes
        obs_dim = len(self.lane_ids) * 2 + 1 + 1  # 12 lanes * 2 + phase + time
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
        """Reset Vietnamese environment."""
        super().reset(seed=seed)

        # Reset simulation state
        self.current_step = 0
        self.current_phase = 0
        self.episode_rewards = []
        self.episode_waiting_times = []
        self.episode_throughput = []

        # Clear Vietnam mock simulation
        self.vietnam_traci.traffic_lights = {self.intersection_id: 0}
        self.vietnam_traci.lanes = self.vietnam_traci._create_vietnam_lanes_for_intersection(self.intersection_id)
        self.vietnam_traci.simulation_time = 0.0
        self.vietnam_traci.vehicles = {}
        self.vietnam_traci.vehicle_counter = 0

        obs = self._get_observation()
        return obs, {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute step in Vietnamese environment."""
        # Apply action
        self.vietnam_traci.trafficlight.setPhase(self.intersection_id, action)
        self.current_phase = action

        # Advance simulation
        self.vietnam_traci.simulationStep(self.step_length)
        self.current_step += 1

        obs = self._get_observation()
        reward = self._calculate_vietnam_reward(action)
        done = self.current_step >= self.max_steps

        info = self._get_info()

        # Store metrics
        self.episode_rewards.append(reward)
        self.episode_waiting_times.append(self._get_total_waiting_time())
        self.episode_throughput.append(self._get_throughput())

        return obs, reward, done, False, info

    def _get_observation(self) -> np.ndarray:
        """Get Vietnamese observation."""
        # Queue lengths
        queue_lengths = [self.vietnam_traci.lane.getLastStepVehicleNumber(lane_id)
                        for lane_id in self.lane_ids]

        # Waiting times (weighted for Vietnam)
        waiting_times = [self.vietnam_traci.lane.getWaitingTime(lane_id)
                        for lane_id in self.lane_ids]

        # Current phase and time
        current_phase = self.vietnam_traci.trafficlight.getPhase(self.intersection_id)
        current_time = self.vietnam_traci.simulation.getTime()

        obs = np.array(queue_lengths + waiting_times + [current_phase, current_time],
                      dtype=np.float32)
        return obs

    def _calculate_vietnam_reward(self, action: int) -> float:
        """Calculate Vietnam-specific reward using optimized function."""
        from .reward_functions import calculate_vietnam_reward

        total_waiting_time = self._get_total_waiting_time()
        throughput = self._get_throughput()
        motorcycle_waiting = self._get_motorcycle_waiting_time()
        current_time = self.vietnam_traci.simulation.getTime()

        # Use Vietnam-optimized reward function
        waiting_times = np.array([self.vietnam_traci.lane.getWaitingTime(lane_id)
                                 for lane_id in self.lane_ids])
        queue_lengths = np.array([self.vietnam_traci.lane.getLastStepVehicleNumber(lane_id)
                                 for lane_id in self.lane_ids])

        reward = calculate_vietnam_reward(
            waiting_times=waiting_times,
            queue_lengths=queue_lengths,
            throughput=throughput,
            motorcycle_waiting=np.array([motorcycle_waiting]),
            time_elapsed=current_time
        )

        return float(reward)

    def _get_total_waiting_time(self) -> float:
        """Get total waiting time."""
        return sum(self.vietnam_traci.lane.getWaitingTime(lane_id) for lane_id in self.lane_ids)

    def _get_motorcycle_waiting_time(self) -> float:
        """Get motorcycle-specific waiting time."""
        motorcycle_waiting = 0
        for lane in self.vietnam_traci.lanes.values():
            for vehicle in lane.vehicles:
                if vehicle.type == VehicleType.MOTORCYCLE:
                    motorcycle_waiting += vehicle.waiting_time
        return motorcycle_waiting

    def _get_throughput(self) -> int:
        """Get throughput in Vietnamese traffic."""
        throughput = 0
        for lane in self.vietnam_traci.lanes.values():
            for vehicle in lane.vehicles:
                if vehicle.position >= lane.length * 0.8:
                    # Weight by vehicle type
                    if vehicle.type == VehicleType.MOTORCYCLE:
                        throughput += 1.5  # Motorcycles count more
                    else:
                        throughput += 1.0
        return int(throughput)

    def _get_info(self) -> Dict[str, Any]:
        """Get Vietnamese environment info."""
        return {
            'step': self.current_step,
            'phase': self.current_phase,
            'total_waiting_time': self._get_total_waiting_time(),
            'motorcycle_waiting_time': self._get_motorcycle_waiting_time(),
            'throughput': self._get_throughput(),
            'avg_reward': np.mean(self.episode_rewards) if self.episode_rewards else 0.0
        }

    def render(self, mode: str = 'human') -> None:
        """Render Vietnamese environment."""
        if mode == 'human':
            total_waiting = self._get_total_waiting_time()
            motorcycle_waiting = self._get_motorcycle_waiting_time()
            throughput = self._get_throughput()
            print(f"Vietnam Traffic - Step {self.current_step}: Phase={self.current_phase}, "
                  f"Total Waiting={total_waiting:.1f}, Motorcycle Waiting={motorcycle_waiting:.1f}, "
                  f"Throughput={throughput:.1f}")

    def close(self) -> None:
        """Close Vietnamese environment."""
        self.vietnam_traci.close()


def create_vietnam_single_env(**kwargs) -> VietnamSingleIntersectionEnv:
    """Factory function for Vietnamese single intersection environment."""
    return VietnamSingleIntersectionEnv(**kwargs)


def create_vietnam_multi_env(**kwargs) -> None:
    """Factory function for Vietnamese multi-intersection environment."""
    # TODO: Implement Vietnamese multi-intersection environment
    pass
