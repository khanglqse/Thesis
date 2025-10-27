"""
PPO agent for traffic light control using stable-baselines3.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
import os
from stable_baselines3 import PPO
from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from gymnasium import spaces


class TrafficLightPolicy(ActorCriticPolicy):
    """
    Custom policy for traffic light control.
    """

    def __init__(self, observation_space: spaces.Space, action_space: spaces.Space,
                 net_arch: Optional[List[Union[int, Dict[str, List[int]]]]] = None,
                 activation_fn: type = None, *args, **kwargs):
        """
        Initialize custom policy.

        Args:
            observation_space: Observation space
            action_space: Action space
            net_arch: Network architecture
            activation_fn: Activation function
            *args, **kwargs: Additional arguments
        """
        if net_arch is None:
            # Larger network for multi-intersection state space (~52 dimensions)
            net_arch = [dict(pi=[128, 64], vf=[128, 64])]

        if activation_fn is None:
            activation_fn = "ReLU"

        super().__init__(observation_space, action_space, net_arch, activation_fn, *args, **kwargs)


class PPOCallback(BaseCallback):
    """
    Custom callback for PPO training monitoring.
    """

    def __init__(self, eval_freq: int = 1000, verbose: int = 0):
        """
        Initialize callback.

        Args:
            eval_freq: Frequency of evaluation
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.eval_freq = eval_freq
        self.episode_rewards = []
        self.episode_lengths = []

    def _on_step(self) -> bool:
        """Called at each step."""
        if self.eval_freq > 0 and self.n_calls % self.eval_freq == 0:
            if self.verbose > 0:
                print(f"Step {self.n_calls}: Mean reward = {np.mean(self.episode_rewards) if self.episode_rewards else 0}")

        return True

    def _on_rollout_end(self) -> None:
        """Called at the end of each rollout."""
        if self.locals.get("infos"):
            for info in self.locals["infos"]:
                if "episode" in info:
                    self.episode_rewards.append(info["episode"]["r"])
                    self.episode_lengths.append(info["episode"]["l"])


class PPOAgent:
    """
    PPO agent for traffic light control using stable-baselines3.
    """

    def __init__(self,
                 env,
                 config: Dict[str, Any] = None):
        """
        Initialize PPO agent.

        Args:
            env: Environment to train on
            config: Agent configuration parameters
        """
        self.env = env
        self.config = config or {}

        # PPO hyperparameters
        self.learning_rate = self.config.get('learning_rate', 3e-4)
        self.n_steps = self.config.get('n_steps', 2048)
        self.batch_size = self.config.get('batch_size', 64)
        self.n_epochs = self.config.get('n_epochs', 10)
        self.gamma = self.config.get('gamma', 0.99)
        self.gae_lambda = self.config.get('gae_lambda', 0.95)
        self.clip_range = self.config.get('clip_range', 0.2)
        self.ent_coef = self.config.get('ent_coef', 0.0)
        self.vf_coef = self.config.get('vf_coef', 0.5)
        self.max_grad_norm = self.config.get('max_grad_norm', 0.5)
        self.total_timesteps = self.config.get('total_timesteps', 100000)

        # Model path for saving/loading
        self.model_path = self.config.get('model_path', 'ppo_model.zip')

        # Initialize model
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize PPO model."""
        # Create model
        self.model = PPO(
            TrafficLightPolicy,
            self.env,
            learning_rate=self.learning_rate,
            n_steps=self.n_steps,
            batch_size=self.batch_size,
            n_epochs=self.n_epochs,
            gamma=self.gamma,
            gae_lambda=self.gae_lambda,
            clip_range=self.clip_range,
            ent_coef=self.ent_coef,
            vf_coef=self.vf_coef,
            max_grad_norm=self.max_grad_norm,
            verbose=1,
            tensorboard_log="./ppo_tensorboard/"
        )

    def train(self, total_timesteps: Optional[int] = None) -> Dict[str, List[float]]:
        """
        Train the PPO agent.

        Args:
            total_timesteps: Total number of timesteps to train for

        Returns:
            Training statistics
        """
        if total_timesteps is None:
            total_timesteps = self.total_timesteps

        # Create callback for monitoring
        callback = PPOCallback(eval_freq=1000, verbose=1)

        # Train the model
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback
        )

        # Return training stats
        return {
            'episode_rewards': callback.episode_rewards,
            'episode_lengths': callback.episode_lengths
        }

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[int, Optional[float]]:
        """
        Predict action for given observation.

        Args:
            observation: Current observation
            deterministic: Whether to use deterministic policy

        Returns:
            Action and action probability (if available)
        """
        action, state = self.model.predict(observation, deterministic=deterministic)
        return action.item(), None

    def save_model(self, filepath: Optional[str] = None):
        """
        Save the trained model.

        Args:
            filepath: Path to save the model (optional)
        """
        save_path = filepath or self.model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self.model.save(save_path)
        print(f"Model saved to {save_path}")

    def load_model(self, filepath: Optional[str] = None):
        """
        Load a trained model.

        Args:
            filepath: Path to load the model from (optional)
        """
        load_path = filepath or self.model_path
        if os.path.exists(load_path):
            self.model = PPO.load(load_path, env=self.env)
            print(f"Model loaded from {load_path}")
        else:
            print(f"Model file not found: {load_path}")

    def set_training_mode(self, training: bool = True):
        """
        Set training/evaluation mode.

        Args:
            training: Whether agent is in training mode
        """
        if training:
            self.model.policy.set_training_mode(True)
        else:
            self.model.policy.set_training_mode(False)


class PPOAgentWrapper:
    """
    Wrapper for PPO agent to match the interface of other agents.
    """

    def __init__(self, env, config: Dict[str, Any] = None):
        """
        Initialize PPO agent wrapper.

        Args:
            env: Environment to train on
            config: Agent configuration parameters
        """
        self.agent = PPOAgent(env, config or {})
        self.training_mode = True

    def select_action(self, state: np.ndarray) -> int:
        """
        Select action for given state.

        Args:
            state: Current state

        Returns:
            Selected action
        """
        action, _ = self.agent.predict(state, deterministic=not self.training_mode)
        return action

    def store_experience(self, state: np.ndarray, action: int, reward: float,
                        next_state: np.ndarray, done: bool):
        """Store experience (not used for PPO)."""
        pass

    def update_model(self) -> float:
        """Update model (not used for PPO)."""
        return 0.0

    def save_model(self, filepath: str):
        """Save model."""
        self.agent.save_model(filepath)

    def load_model(self, filepath: str):
        """Load model."""
        self.agent.load_model(filepath)

    def set_training_mode(self, training: bool = True):
        """Set training mode."""
        self.training_mode = training
        self.agent.set_training_mode(training)


def create_ppo_agent(env, config: Dict[str, Any] = None, **kwargs) -> PPOAgentWrapper:
    """
    Factory function to create PPO agent.

    Args:
        env: Environment to train on
        config: Agent configuration (will be merged with kwargs)
        **kwargs: Additional arguments for PPOAgent

    Returns:
        Configured PPOAgentWrapper instance
    """
    # Merge config and kwargs
    merged_config = config.copy() if config else {}
    merged_config.update(kwargs)
    return PPOAgentWrapper(env, merged_config)
