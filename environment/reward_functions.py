"""
Reward function definitions for traffic light control optimization.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional


def calculate_waiting_time_reward(waiting_times: np.ndarray,
                                 previous_waiting_times: Optional[np.ndarray] = None) -> float:
    """
    Calculate reward based on total waiting time.

    Args:
        waiting_times: Current waiting times for all lanes
        previous_waiting_times: Previous waiting times for delta calculation

    Returns:
        Reward value (negative for minimization)
    """
    total_waiting_time = np.sum(waiting_times)

    if previous_waiting_times is not None:
        # Reward improvement in waiting time
        waiting_time_delta = np.sum(previous_waiting_times) - total_waiting_time
        return -total_waiting_time + 0.1 * waiting_time_delta
    else:
        return -total_waiting_time


def calculate_queue_length_reward(queue_lengths: np.ndarray,
                                 previous_queue_lengths: Optional[np.ndarray] = None) -> float:
    """
    Calculate reward based on queue lengths.

    Args:
        queue_lengths: Current queue lengths for all lanes
        previous_queue_lengths: Previous queue lengths for delta calculation

    Returns:
        Reward value (negative for minimization)
    """
    total_queue_length = np.sum(queue_lengths)

    if previous_queue_lengths is not None:
        # Reward reduction in queue length
        queue_delta = np.sum(previous_queue_lengths) - total_queue_length
        return -total_queue_length + 0.1 * queue_delta
    else:
        return -total_queue_length


def calculate_throughput_reward(throughput: int,
                              max_throughput: float = 100.0) -> float:
    """
    Calculate reward based on throughput (vehicles passed per step).

    Args:
        throughput: Number of vehicles that passed through the intersection
        max_throughput: Maximum expected throughput for normalization

    Returns:
        Reward value (positive for maximization)
    """
    normalized_throughput = throughput / max_throughput
    return normalized_throughput * 10.0  # Scale the reward


def calculate_delay_reward(delays: np.ndarray,
                          previous_delays: Optional[np.ndarray] = None) -> float:
    """
    Calculate reward based on vehicle delays.

    Args:
        delays: Current delays for all vehicles
        previous_delays: Previous delays for delta calculation

    Returns:
        Reward value (negative for minimization)
    """
    total_delay = np.sum(delays)

    if previous_delays is not None:
        # Reward improvement in delay
        delay_delta = np.sum(previous_delays) - total_delay
        return -total_delay + 0.1 * delay_delta
    else:
        return -total_delay


def calculate_combined_reward(waiting_times: np.ndarray,
                            queue_lengths: np.ndarray,
                            throughput: int,
                            previous_waiting_times: Optional[np.ndarray] = None,
                            previous_queue_lengths: Optional[np.ndarray] = None,
                            weights: Dict[str, float] = None) -> float:
    """
    Calculate combined reward using multiple metrics.

    Args:
        waiting_times: Current waiting times for all lanes
        queue_lengths: Current queue lengths for all lanes
        throughput: Number of vehicles that passed through
        previous_waiting_times: Previous waiting times for delta calculation
        previous_queue_lengths: Previous queue lengths for delta calculation
        weights: Weights for different reward components

    Returns:
        Combined reward value
    """
    if weights is None:
        weights = {
            'waiting_time': 0.5,
            'queue_length': 0.3,
            'throughput': 0.2
        }

    waiting_reward = calculate_waiting_time_reward(
        waiting_times, previous_waiting_times
    )

    queue_reward = calculate_queue_length_reward(
        queue_lengths, previous_queue_lengths
    )

    throughput_reward = calculate_throughput_reward(throughput)

    combined_reward = (
        weights['waiting_time'] * waiting_reward +
        weights['queue_length'] * queue_reward +
        weights['throughput'] * throughput_reward
    )

    return combined_reward


def calculate_pressure_reward(lane_pressures: np.ndarray) -> float:
    """
    Calculate reward based on lane pressure (difference between incoming and outgoing flow).

    Args:
        lane_pressures: Pressure values for each lane (incoming - outgoing vehicles)

    Returns:
        Reward value (negative for minimization)
    """
    total_pressure = np.sum(np.abs(lane_pressures))
    return -total_pressure


def calculate_efficiency_reward(waiting_times: np.ndarray,
                              throughput: int,
                              max_waiting_time: float = 100.0) -> float:
    """
    Calculate reward based on traffic efficiency.

    Args:
        waiting_times: Current waiting times for all lanes
        throughput: Number of vehicles that passed through
        max_waiting_time: Maximum expected waiting time for normalization

    Returns:
        Reward value
    """
    if throughput == 0:
        return -np.sum(waiting_times)

    efficiency = throughput / (1 + np.sum(waiting_times) / max_waiting_time)
    return efficiency * 10.0  # Scale the reward


def calculate_vietnam_reward(waiting_times: np.ndarray,
                           queue_lengths: np.ndarray,
                           throughput: int,
                           motorcycle_waiting: Optional[np.ndarray] = None,
                           time_elapsed: float = 0.0,
                           vehicle_types: Optional[List[str]] = None) -> float:
    """
    Vietnam-specific reward function prioritizing motorcycles and urban efficiency.

    This reward function is optimized for Vietnamese traffic characteristics:
    - High motorcycle density (65%)
    - Chaotic traffic patterns
    - Priority for motorcycles
    - Higher penalties for congestion during rush hours

    Args:
        waiting_times: Current waiting times for all lanes
        queue_lengths: Current queue lengths for all lanes
        throughput: Number of vehicles that passed through
        motorcycle_waiting: Motorcycle-specific waiting times
        time_elapsed: Time elapsed in simulation (for rush hour detection)
        vehicle_types: Types of vehicles in each lane

    Returns:
        Vietnam-optimized reward value
    """
    # Base weights (higher for Vietnam traffic intensity)
    weights = {
        'waiting_time': 0.6,    # Higher penalty for waiting
        'queue_length': 0.3,    # Moderate penalty for queues
        'throughput': 0.1,      # Lower bonus for throughput
        'motorcycle_priority': 0.8  # High priority for motorcycles
    }

    # Rush hour detection (Vietnam has longer rush hours)
    hour = (time_elapsed / 3600) % 24
    is_rush_hour = (6 <= hour <= 9) or (11 <= hour <= 14) or (16 <= hour <= 20)

    # Rush hour multiplier
    rush_multiplier = 1.8 if is_rush_hour else 1.0

    # Base reward calculation
    waiting_penalty = weights['waiting_time'] * np.sum(waiting_times)
    queue_penalty = weights['queue_length'] * np.sum(queue_lengths)
    throughput_bonus = weights['throughput'] * throughput

    # Vietnam-specific: motorcycle priority
    motorcycle_penalty = 0
    if motorcycle_waiting is not None:
        motorcycle_penalty = weights['motorcycle_priority'] * np.sum(motorcycle_waiting)

    # Congestion penalty (more severe in Vietnam)
    total_vehicles = np.sum(queue_lengths)
    congestion_penalty = 0.2 * (total_vehicles ** 1.3)  # Exponential penalty

    # Combine rewards
    vietnam_reward = -waiting_penalty - queue_penalty - motorcycle_penalty + throughput_bonus
    vietnam_reward -= congestion_penalty

    # Apply rush hour scaling
    vietnam_reward *= rush_multiplier

    return vietnam_reward


def calculate_vietnam_motorcycle_priority_reward(waiting_times: np.ndarray,
                                               queue_lengths: np.ndarray,
                                               motorcycle_waiting: np.ndarray,
                                               car_waiting: np.ndarray) -> float:
    """
    Reward function specifically prioritizing motorcycle flow in Vietnamese traffic.

    Args:
        waiting_times: All waiting times
        queue_lengths: All queue lengths
        motorcycle_waiting: Motorcycle waiting times
        car_waiting: Car waiting times

    Returns:
        Motorcycle-priority reward
    """
    # Base reward
    base_reward = calculate_combined_reward(waiting_times, queue_lengths, 0)

    # Motorcycle priority bonus
    motorcycle_priority = 2.0  # Motorcycles 2x more important

    # Penalty ratio: if motorcycles wait longer than cars, higher penalty
    if np.sum(car_waiting) > 0:
        waiting_ratio = np.sum(motorcycle_waiting) / np.sum(car_waiting)
        motorcycle_penalty = motorcycle_priority * waiting_ratio
    else:
        motorcycle_penalty = motorcycle_priority * np.sum(motorcycle_waiting)

    return base_reward - motorcycle_penalty


def calculate_vietnam_urban_efficiency_reward(waiting_times: np.ndarray,
                                            throughput: int,
                                            intersection_efficiency: float = 1.0) -> float:
    """
    Calculate reward for urban traffic efficiency in Vietnamese context.

    Args:
        waiting_times: Current waiting times
        throughput: Current throughput
        intersection_efficiency: Intersection efficiency factor

    Returns:
        Urban efficiency reward
    """
    # Vietnam urban efficiency considers high-density traffic
    total_waiting = np.sum(waiting_times)

    if throughput == 0:
        return -total_waiting * 0.3  # Higher penalty when no throughput

    # Efficiency calculation for dense urban traffic
    urban_efficiency = throughput / (1 + total_waiting / 50.0)  # Normalize by 50s average waiting

    # Scale for Vietnamese traffic density
    vietnam_factor = 1.5  # Vietnamese traffic is more challenging

    return urban_efficiency * 15.0 * vietnam_factor * intersection_efficiency
