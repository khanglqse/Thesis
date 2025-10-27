"""
Mock SUMO implementation for RL training without requiring SUMO installation.

This module provides realistic traffic simulation behavior for training RL agents
in a controlled environment. It mimics SUMO's TraCI interface but generates
realistic traffic patterns algorithmically.
"""

import numpy as np
import random
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass


@dataclass
class Vehicle:
    """Represents a vehicle in the simulation."""
    id: str
    route: str
    speed: float = 0.0
    waiting_time: float = 0.0
    position: float = 0.0
    arrival_time: float = 0.0


@dataclass
class Lane:
    """Represents a lane in the intersection."""
    id: str
    vehicles: List[Vehicle] = None
    length: float = 200.0
    max_speed: float = 13.9  # m/s (50 km/h)

    def __post_init__(self):
        if self.vehicles is None:
            self.vehicles = []


class MockTraCI:
    """
    Mock TraCI implementation that provides realistic traffic simulation.

    This class simulates traffic light control and traffic flow without
    requiring actual SUMO installation.
    """

    def __init__(self):
        self.simulation_time = 0.0
        self.traffic_lights = {}
        self.lanes = {}
        self.vehicles = {}
        self.intersections = []
        self.vehicle_counter = 0

    @staticmethod
    def start(cmd: List[str], **kwargs) -> None:
        """Mock TraCI start - initializes simulation."""
        print("🚦 Mock SUMO: Starting traffic simulation...")

    @staticmethod
    def close() -> None:
        """Mock TraCI close - cleanup simulation."""
        print("🚦 Mock SUMO: Closing traffic simulation...")

    def load(self, intersections: List[str]) -> None:
        """Load intersection configuration."""
        self.intersections = intersections
        self.traffic_lights = {inter_id: 0 for inter_id in intersections}

        # Initialize lanes for each intersection
        for inter_id in intersections:
            self.lanes.update(self._create_lanes_for_intersection(inter_id))

        print(f"🚦 Mock SUMO: Loaded {len(intersections)} intersections")

    def _create_lanes_for_intersection(self, inter_id: str) -> Dict[str, Lane]:
        """Create lanes for a single intersection."""
        lanes = {}
        directions = ['north_south', 'south_north', 'east_west', 'west_east']

        for direction in directions:
            for lane_num in [0, 1]:  # 2 lanes per direction
                lane_id = f'{inter_id}_{direction}_{lane_num}'
                lanes[lane_id] = Lane(id=lane_id)

        return lanes

    def simulationStep(self, step: float = 1.0) -> None:
        """Advance simulation by one step."""
        self.simulation_time += step

        # Generate new vehicles based on traffic demand
        self._generate_traffic()

        # Update vehicle positions and waiting times
        self._update_traffic_flow()

        # Update traffic light phases if needed
        self._update_traffic_lights()

    def _generate_traffic(self) -> None:
        """Generate new vehicles based on realistic traffic patterns."""
        # Traffic demand varies by time of day (rush hour effects)
        hour = (self.simulation_time / 3600) % 24

        # Higher demand during rush hours (7-9 AM, 5-7 PM)
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            base_demand = 0.3
        elif 6 <= hour <= 22:
            base_demand = 0.15
        else:
            base_demand = 0.05

        # Add some randomness
        demand = base_demand * (0.8 + 0.4 * random.random())

        for lane in self.lanes.values():
            if random.random() < demand:
                self._add_vehicle_to_lane(lane)

    def _add_vehicle_to_lane(self, lane: Lane) -> None:
        """Add a new vehicle to a lane."""
        self.vehicle_counter += 1
        vehicle_id = f'veh_{self.vehicle_counter}'

        # Random route assignment
        routes = ['north_south', 'south_north', 'east_west', 'west_east']
        route = random.choice(routes)

        vehicle = Vehicle(
            id=vehicle_id,
            route=route,
            speed=0.0,
            waiting_time=0.0,
            position=0.0,
            arrival_time=self.simulation_time
        )

        lane.vehicles.append(vehicle)
        self.vehicles[vehicle_id] = vehicle

    def _update_traffic_flow(self) -> None:
        """Update vehicle positions and waiting times."""
        for lane in self.lanes.values():
            for vehicle in lane.vehicles:
                # Update waiting time
                if vehicle.speed < 0.1:  # Vehicle is stopped
                    vehicle.waiting_time += 1.0
                else:
                    vehicle.waiting_time = 0.0

                # Update position based on traffic light state
                traffic_light = self._get_traffic_light_for_lane(lane.id)
                if traffic_light == 0:  # Green for N-S
                    if 'north_south' in lane.id or 'south_north' in lane.id:
                        vehicle.position = min(vehicle.position + vehicle.speed, lane.length)
                        vehicle.speed = min(vehicle.speed + 1.0, lane.max_speed)
                    else:
                        vehicle.speed = max(vehicle.speed - 2.0, 0.0)
                else:  # Green for E-W
                    if 'east_west' in lane.id or 'west_east' in lane.id:
                        vehicle.position = min(vehicle.position + vehicle.speed, lane.length)
                        vehicle.speed = min(vehicle.speed + 1.0, lane.max_speed)
                    else:
                        vehicle.speed = max(vehicle.speed - 2.0, 0.0)

                # Remove vehicles that have exited
                if vehicle.position >= lane.length:
                    lane.vehicles.remove(vehicle)
                    if vehicle.id in self.vehicles:
                        del self.vehicles[vehicle.id]

    def _get_traffic_light_for_lane(self, lane_id: str) -> int:
        """Get traffic light phase for a lane."""
        # Extract intersection ID from lane ID
        parts = lane_id.split('_')
        if len(parts) >= 1:
            inter_id = parts[0]
            return self.traffic_lights.get(inter_id, 0)
        return 0

    def _update_traffic_lights(self) -> None:
        """Update traffic light phases based on demand."""
        for inter_id in self.intersections:
            # Simple adaptive control based on queue lengths
            ns_lanes = [lane for lane_id, lane in self.lanes.items()
                       if lane_id.startswith(inter_id) and
                       ('north_south' in lane_id or 'south_north' in lane_id)]

            ew_lanes = [lane for lane_id, lane in self.lanes.items()
                       if lane_id.startswith(inter_id) and
                       ('east_west' in lane_id or 'west_east' in lane_id)]

            ns_queue = sum(len(lane.vehicles) for lane in ns_lanes)
            ew_queue = sum(len(lane.vehicles) for lane in ew_lanes)

            # Switch phase if one direction has significantly more traffic
            if ns_queue > ew_queue * 1.5 and self.traffic_lights[inter_id] == 1:
                self.traffic_lights[inter_id] = 0
            elif ew_queue > ns_queue * 1.5 and self.traffic_lights[inter_id] == 0:
                self.traffic_lights[inter_id] = 1

    # Properties for compatibility with TraCI interface
    @property
    def lane(self):
        """Mock lane operations."""
        return LaneOperations(self)

    @property
    def trafficlight(self):
        """Mock traffic light operations."""
        return TrafficLightOperations(self)

    @property
    def simulation(self):
        """Mock simulation operations."""
        return SimulationOperations(self)


class LaneOperations:
    """Mock lane operations."""

    def __init__(self, mock_traci_instance):
        self.traci = mock_traci_instance

    def getIDList(self) -> List[str]:
        """Get list of all lane IDs."""
        return list(self.traci.lanes.keys())

    def getLastStepVehicleNumber(self, lane_id: str) -> int:
        """Get number of vehicles in lane."""
        if lane_id in self.traci.lanes:
            return len(self.traci.lanes[lane_id].vehicles)
        return 0

    def getWaitingTime(self, lane_id: str) -> float:
        """Get total waiting time for vehicles in lane."""
        if lane_id in self.traci.lanes:
            lane = self.traci.lanes[lane_id]
            return sum(vehicle.waiting_time for vehicle in lane.vehicles)
        return 0.0


class TrafficLightOperations:
    """Mock traffic light operations."""

    def __init__(self, mock_traci_instance):
        self.traci = mock_traci_instance

    def getPhase(self, intersection_id: str) -> int:
        """Get current phase of traffic light."""
        if intersection_id in self.traci.traffic_lights:
            return self.traci.traffic_lights[intersection_id]
        return 0

    def setPhase(self, intersection_id: str, phase: int) -> None:
        """Set traffic light phase."""
        if intersection_id in self.traci.traffic_lights:
            self.traci.traffic_lights[intersection_id] = phase


class SimulationOperations:
    """Mock simulation operations."""

    def __init__(self, mock_traci_instance):
        self.traci = mock_traci_instance

    def getTime(self) -> float:
        """Get current simulation time."""
        return self.traci.simulation_time

    def getMinExpectedNumber(self) -> int:
        """Get minimum expected number of vehicles."""
        return sum(len(lane.vehicles) for lane in self.traci.lanes.values())

    def getArrivedNumber(self) -> int:
        """Get number of vehicles that have arrived."""
        # Simplified - in real SUMO this would track completed trips
        return 0


# Global mock TraCI instance
mock_traci = MockTraCI()
