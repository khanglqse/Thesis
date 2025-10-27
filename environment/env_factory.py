"""
Environment Factory for Traffic Light Control.

This module provides a unified interface for creating traffic environments,
supporting both mock SUMO (for testing) and real SUMO (for production).
The factory pattern allows seamless switching between simulation modes.
"""

from typing import Dict, Any, Optional
import os


def create_traffic_environment(config: Dict[str, Any], use_gui: bool = False):
    """
    Factory function to create traffic environment.

    Args:
        config: Environment configuration dictionary
        use_gui: Whether to use SUMO GUI (only for real SUMO)

    Returns:
        Configured traffic environment
    """
    use_real_sumo = config.get('use_real_sumo', False)

    if use_real_sumo:
        return create_real_sumo_environment(config, use_gui)
    else:
        return create_mock_environment(config)


def create_mock_environment(config: Dict[str, Any]):
    """
    Create mock SUMO environment for testing and development.

    Args:
        config: Environment configuration

    Returns:
        Mock traffic environment
    """
    scenario = config.get('scenario', 'single_intersection')

    if scenario == 'single_intersection':
        from .mock_traffic_env import create_single_intersection_env
        return create_single_intersection_env(
            max_steps=config.get('max_steps', 3600),
            step_length=config.get('step_length', 1.0),
            traffic_demand=config.get('traffic_demand', 0.15)
        )
    elif scenario == 'multi_intersection':
        from .mock_traffic_env import create_multi_intersection_env
        return create_multi_intersection_env(
            max_steps=config.get('max_steps', 3600),
            step_length=config.get('step_length', 1.0),
            traffic_demand=config.get('traffic_demand', 0.15),
            coordination=config.get('coordination', True)
        )
    else:
        raise ValueError(f"Unknown mock scenario: {scenario}")


def create_real_sumo_environment(config: Dict[str, Any], use_gui: bool = False):
    """
    Create real SUMO environment for production use.

    Args:
        config: Environment configuration
        use_gui: Whether to use SUMO GUI

    Returns:
        Real SUMO traffic environment
    """
    try:
        from .traffic_env import TrafficLightEnv
        return TrafficLightEnv(
            config=config,
            use_gui=use_gui,
            reward_function=config.get('reward_function', 'combined'),
            max_steps=config.get('max_steps', 3600),
            step_length=config.get('step_length', 1.0)
        )
    except ImportError as e:
        print(f"Real SUMO not available: {e}")
        print("Falling back to mock environment...")
        return create_mock_environment(config)


def create_environment_from_config(config_file: str, use_gui: bool = False):
    """
    Create environment from configuration file.

    Args:
        config_file: Path to JSON configuration file
        use_gui: Whether to use SUMO GUI

    Returns:
        Configured environment
    """
    import json

    with open(config_file, 'r') as f:
        config = json.load(f)

    return create_traffic_environment(config, use_gui)


# Predefined configurations for common scenarios
SINGLE_INTERSECTION_CONFIG = {
    'scenario': 'single_intersection',
    'use_real_sumo': False,
    'max_steps': 3600,
    'step_length': 1.0,
    'traffic_demand': 0.15,
    'reward_function': 'combined'
}

MULTI_INTERSECTION_CONFIG = {
    'scenario': 'multi_intersection',
    'use_real_sumo': False,
    'coordination': True,
    'max_steps': 3600,
    'step_length': 1.0,
    'traffic_demand': 0.15,
    'reward_function': 'combined'
}

REAL_SUMO_CONFIG = {
    'scenario': 'real_sumo',
    'use_real_sumo': True,
    'max_steps': 3600,
    'step_length': 1.0,
    'traffic_demand': 0.15,
    'reward_function': 'combined'
}


def get_available_scenarios() -> Dict[str, Dict[str, Any]]:
    """
    Get information about available scenarios.

    Returns:
        Dictionary of scenario configurations
    """
    return {
        'single_intersection': {
            'description': 'Single 4-way intersection with 8 lanes',
            'state_dim': 11,  # 8 lanes * 2 + phase + time
            'action_dim': 2,  # 2 phases
            'config': SINGLE_INTERSECTION_CONFIG
        },
        'multi_intersection': {
            'description': '3-intersection network with coordination',
            'state_dim': 33,  # 24 lanes * 2 + 3 phases + time
            'action_dim': 2,  # Coordinated control
            'config': MULTI_INTERSECTION_CONFIG
        },
        'real_sumo_single': {
            'description': 'Real SUMO single intersection',
            'state_dim': 11,
            'action_dim': 2,
            'config': {**REAL_SUMO_CONFIG, 'network_type': 'single'}
        },
        'real_sumo_multi': {
            'description': 'Real SUMO multi-intersection',
            'state_dim': 33,
            'action_dim': 2,
            'config': {**REAL_SUMO_CONFIG, 'network_type': 'multi'}
        }
    }
