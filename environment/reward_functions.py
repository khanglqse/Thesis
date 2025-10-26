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
