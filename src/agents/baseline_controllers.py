"""
Baseline traffic light controllers for comparison with RL agents.
"""

import numpy as np
try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    print("TraCI not available. Baseline controllers will run in mock mode.")
    TRACI_AVAILABLE = False
    # Create mock traci for baseline controllers
    class MockLane:
        @staticmethod
        def getLastStepVehicleNumber(*args): return 5
        @staticmethod
        def getWaitingTime(*args): return 10.0

    class MockTraCI:
        @staticmethod
        def lane(*args, **kwargs): return MockLane()
    traci = MockTraCI()
from typing import Dict, List, Tuple, Optional, Any
from abc import ABC, abstractmethod


class TrafficController(ABC):
    """
    Abstract base class for traffic light controllers.
    """

    @abstractmethod
    def select_action(self, state: np.ndarray) -> int:
        """
        Select traffic light action based on current state.

        Args:
            state: Current traffic state

        Returns:
            Action (traffic light phase)
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset controller state."""
        pass


class FixedTimeController(TrafficController):
    """
    Fixed-time traffic light controller.
    """

    def __init__(self, phase_duration: int = 30, num_phases: int = 2):
        """
        Initialize fixed-time controller.

        Args:
            phase_duration: Duration of each phase in seconds
            num_phases: Number of traffic light phases
        """
        self.phase_duration = phase_duration
        self.num_phases = num_phases
        self.current_phase = 0
        self.phase_timer = 0

    def select_action(self, state: np.ndarray) -> int:
        """
        Select action based on fixed timing schedule.

        Args:
            state: Current traffic state (ignored)

        Returns:
            Current phase
        """
        # Update timer and phase
        self.phase_timer += 1

        if self.phase_timer >= self.phase_duration:
            self.current_phase = (self.current_phase + 1) % self.num_phases
            self.phase_timer = 0

        return self.current_phase

    def reset(self):
        """Reset controller state."""
        self.current_phase = 0
        self.phase_timer = 0


class ActuatedController(TrafficController):
    """
    Actuated traffic light controller based on traffic density.
    """

    def __init__(self, threshold: float = 10.0, min_green_time: int = 15,
                 max_green_time: int = 60, yellow_time: int = 3):
        """
        Initialize actuated controller.

        Args:
            threshold: Vehicle count threshold for phase switching
            min_green_time: Minimum green time per phase
            max_green_time: Maximum green time per phase
            yellow_time: Yellow transition time
        """
        self.threshold = threshold
        self.min_green_time = min_green_time
        self.max_green_time = max_green_time
        self.yellow_time = yellow_time

        self.current_phase = 0
        self.green_timer = 0
        self.yellow_timer = 0
        self.in_yellow = False

        # Define which lanes belong to which phase
        # Phase 0: North-South, Phase 1: East-West
        self.phase_lanes = {
            0: ['north_south_0', 'north_south_1', 'south_north_0', 'south_north_1'],
            1: ['east_west_0', 'east_west_1', 'west_east_0', 'west_east_1']
        }

    def select_action(self, state: np.ndarray) -> int:
        """
        Select action based on traffic density.

        Args:
            state: Current traffic state (queue lengths, waiting times, etc.)

        Returns:
            Current phase
        """
        try:
            # Handle yellow transition
            if self.in_yellow:
                self.yellow_timer += 1
                if self.yellow_timer >= self.yellow_time:
                    self.in_yellow = False
                    self.yellow_timer = 0
                    self.current_phase = 1 - self.current_phase  # Switch phase
                    self.green_timer = 0
                return self.current_phase

            # Use simplified logic based on state for mock environment
            # State contains: [vehicle_count, waiting_time, queue_length] for each lane
            # Extract vehicle counts from state
            current_vehicles = 0
            other_vehicles = 0
            
            if len(state) > 3:
                # State contains lane data: [v1, w1, q1, v2, w2, q2, ...]
                # Approximate: lanes 0-7 for phase 0, lanes 8-15 for phase 1
                phase0_lanes = list(range(0, min(8, len(state) // 3)))
                phase1_lanes = list(range(8, min(16, len(state) // 3)))
                
                for idx in phase0_lanes:
                    if idx * 3 < len(state):
                        current_vehicles += state[idx * 3]  # vehicle_count
                
                for idx in phase1_lanes:
                    if idx * 3 < len(state):
                        other_vehicles += state[idx * 3]  # vehicle_count

            # Increment green timer
            self.green_timer += 1

            # Check switching conditions
            should_switch = False

            # Switch if max green time reached
            if self.green_timer >= self.max_green_time:
                should_switch = True

            # Switch if other phase has more vehicles and min green time passed
            elif (self.green_timer >= self.min_green_time and
                  other_vehicles > self.threshold and
                  other_vehicles > current_vehicles):
                should_switch = True

            if should_switch:
                self.in_yellow = True
                self.yellow_timer = 0

            return self.current_phase

        except Exception as e:
            print(f"Error in actuated controller: {e}")
            return self.current_phase

    def reset(self):
        """Reset controller state."""
        self.current_phase = 0
        self.green_timer = 0
        self.yellow_timer = 0
        self.in_yellow = False


class AdaptiveController(TrafficController):
    """
    Adaptive traffic light controller with dynamic phase timing.
    """

    def __init__(self, base_green_time: int = 20, max_green_time: int = 60,
                 vehicle_threshold: float = 5.0, congestion_threshold: float = 15.0):
        """
        Initialize adaptive controller.

        Args:
            base_green_time: Base green time for each phase
            max_green_time: Maximum green time per phase
            vehicle_threshold: Threshold for extending green time
            congestion_threshold: Threshold for early phase switching
        """
        self.base_green_time = base_green_time
        self.max_green_time = max_green_time
        self.vehicle_threshold = vehicle_threshold
        self.congestion_threshold = congestion_threshold

        self.current_phase = 0
        self.green_timer = 0

        # Phase lane mapping
        self.phase_lanes = {
            0: ['north_south_0', 'north_south_1', 'south_north_0', 'south_north_1'],
            1: ['east_west_0', 'east_west_1', 'west_east_0', 'west_east_1']
        }

    def select_action(self, state: np.ndarray) -> int:
        """
        Select action based on adaptive timing.

        Args:
            state: Current traffic state

        Returns:
            Current phase
        """
        try:
            # Use simplified logic based on state for mock environment
            # State contains: [vehicle_count, waiting_time, queue_length] for each lane
            current_congestion = 0
            other_congestion = 0
            
            if len(state) > 3:
                # State contains lane data: [v1, w1, q1, v2, w2, q2, ...]
                # Approximate: lanes 0-7 for phase 0, lanes 8-15 for phase 1
                phase0_lanes = list(range(0, min(8, len(state) // 3)))
                phase1_lanes = list(range(8, min(16, len(state) // 3)))
                
                for idx in phase0_lanes:
                    if idx * 3 + 1 < len(state):
                        vehicles = state[idx * 3]  # vehicle_count
                        waiting_time = state[idx * 3 + 1]  # waiting_time
                        current_congestion += vehicles + (waiting_time / 10.0)
                
                for idx in phase1_lanes:
                    if idx * 3 + 1 < len(state):
                        vehicles = state[idx * 3]  # vehicle_count
                        waiting_time = state[idx * 3 + 1]  # waiting_time
                        other_congestion += vehicles + (waiting_time / 10.0)

            self.green_timer += 1

            # Adaptive green time calculation
            if current_congestion > self.congestion_threshold:
                # High congestion - extend green time
                adaptive_green_time = min(self.max_green_time,
                                        self.base_green_time + (current_congestion / 5.0))
            else:
                adaptive_green_time = self.base_green_time

            # Check if we should switch phases
            should_switch = False

            if self.green_timer >= self.max_green_time:
                should_switch = True
            elif (self.green_timer >= adaptive_green_time and
                  other_congestion > current_congestion * 1.2):
                should_switch = True

            if should_switch:
                self.current_phase = 1 - self.current_phase
                self.green_timer = 0

            return self.current_phase

        except Exception as e:
            print(f"Error in adaptive controller: {e}")
            return self.current_phase

    def reset(self):
        """Reset controller state."""
        self.current_phase = 0
        self.green_timer = 0


class RandomController(TrafficController):
    """
    Random traffic light controller for baseline comparison.
    """

    def __init__(self, num_phases: int = 2):
        """
        Initialize random controller.

        Args:
            num_phases: Number of traffic light phases
        """
        self.num_phases = num_phases
        self.current_phase = 0
        self.switch_probability = 0.1  # Probability of switching each step

    def select_action(self, state: np.ndarray) -> int:
        """
        Select random action.

        Args:
            state: Current traffic state (ignored)

        Returns:
            Random phase
        """
        if np.random.random() < self.switch_probability:
            self.current_phase = np.random.randint(self.num_phases)
        return self.current_phase

    def reset(self):
        """Reset controller state."""
        self.current_phase = 0


def create_fixed_time_controller(**kwargs) -> FixedTimeController:
    """Factory function for fixed-time controller."""
    return FixedTimeController(**kwargs)


def create_actuated_controller(**kwargs) -> ActuatedController:
    """Factory function for actuated controller."""
    return ActuatedController(**kwargs)


def create_adaptive_controller(**kwargs) -> AdaptiveController:
    """Factory function for adaptive controller."""
    return AdaptiveController(**kwargs)


def create_random_controller(**kwargs) -> RandomController:
    """Factory function for random controller."""
    return RandomController(**kwargs)
