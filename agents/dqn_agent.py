"""
Deep Q-Network (DQN) agent for traffic light control.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import random
from collections import deque
from typing import Dict, List, Tuple, Optional, Any
import os


class DQN(nn.Module):
    """
    Deep Q-Network neural network architecture for multi-intersection traffic control.
    """

    def __init__(self, input_dim: int, output_dim: int, hidden_dims: List[int] = None):
        """
        Initialize DQN network.

        Args:
            input_dim: Dimension of input state (now ~52 for 3 intersections)
            output_dim: Dimension of output actions
            hidden_dims: List of hidden layer dimensions
        """
        super(DQN, self).__init__()

        if hidden_dims is None:
            # Larger network for complex multi-intersection state space
            hidden_dims = [256, 128, 64]

        layers = []
        prev_dim = input_dim

        # Hidden layers
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.1))  # Add dropout for regularization
            prev_dim = hidden_dim

        # Output layer
        layers.append(nn.Linear(prev_dim, output_dim))

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through the network."""
        return self.network(x)


class ReplayBuffer:
    """
    Experience replay buffer for DQN training.
    """

    def __init__(self, capacity: int = 10000):
        """
        Initialize replay buffer.

        Args:
            capacity: Maximum number of experiences to store
        """
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)

    def push(self, state: np.ndarray, action: int, reward: float,
             next_state: np.ndarray, done: bool):
        """
        Add experience to buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple[torch.Tensor, ...]:
        """
        Sample batch of experiences.

        Args:
            batch_size: Size of batch to sample

        Returns:
            Tuple of tensors (states, actions, rewards, next_states, dones)
        """
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (torch.FloatTensor(np.array(states)),
                torch.LongTensor(actions),
                torch.FloatTensor(rewards),
                torch.FloatTensor(np.array(next_states)),
                torch.BoolTensor(dones))

    def __len__(self) -> int:
        """Return current buffer size."""
        return len(self.buffer)


class DQNAgent:
    """
    Deep Q-Network agent for traffic light control.
    """

    def __init__(self,
                 state_dim: int,
                 action_dim: int,
                 config: Dict[str, Any] = None):
        """
        Initialize DQN agent.

        Args:
            state_dim: Dimension of state space
            action_dim: Dimension of action space
            config: Agent configuration parameters
        """
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Configuration for multi-intersection system
        self.config = config or {}
        self.learning_rate = self.config.get('learning_rate', 5e-4)  # Lower LR for complex state space
        self.gamma = self.config.get('gamma', 0.99)
        self.epsilon_start = self.config.get('epsilon_start', 1.0)
        self.epsilon_end = self.config.get('epsilon_end', 0.01)
        self.epsilon_decay = self.config.get('epsilon_decay', 0.995)
        self.target_update_freq = self.config.get('target_update_freq', 1000)
        self.batch_size = self.config.get('batch_size', 128)  # Larger batch for complex system
        self.buffer_capacity = self.config.get('buffer_capacity', 20000)  # Larger buffer
        self.device = torch.device(self.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu'))

        # Networks
        self.policy_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())

        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)

        # Replay buffer
        self.replay_buffer = ReplayBuffer(self.buffer_capacity)

        # Training state
        self.epsilon = self.epsilon_start
        self.step_count = 0
        self.training_mode = True

        # Loss function
        self.criterion = nn.SmoothL1Loss()

    def select_action(self, state: np.ndarray) -> int:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current state

        Returns:
            Selected action
        """
        if self.training_mode and np.random.random() < self.epsilon:
            # Random action (exploration)
            return np.random.randint(self.action_dim)
        else:
            # Greedy action (exploitation)
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.policy_net(state_tensor)
                return q_values.argmax().item()

    def update_epsilon(self):
        """Update epsilon value for epsilon-greedy exploration."""
        self.epsilon = max(self.epsilon_end,
                          self.epsilon * self.epsilon_decay)

    def store_experience(self, state: np.ndarray, action: int, reward: float,
                        next_state: np.ndarray, done: bool):
        """
        Store experience in replay buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        self.replay_buffer.push(state, action, reward, next_state, done)

    def update_model(self) -> float:
        """
        Update the DQN model using experience replay.

        Returns:
            Loss value
        """
        if len(self.replay_buffer) < self.batch_size:
            return 0.0

        # Sample batch from replay buffer
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.batch_size)

        # Move tensors to device
        states = states.to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device)
        next_states = next_states.to(self.device)
        dones = dones.to(self.device)

        # Current Q values
        current_q_values = self.policy_net(states).gather(1, actions.unsqueeze(1))

        # Target Q values
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0]
            target_q_values = rewards + (self.gamma * next_q_values * (~dones))

        # Compute loss
        loss = self.criterion(current_q_values.squeeze(), target_q_values)

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # Update target network periodically
        self.step_count += 1
        if self.step_count % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def save_model(self, filepath: str):
        """
        Save the model to file.

        Args:
            filepath: Path to save the model
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'step_count': self.step_count,
            'config': self.config
        }, filepath)

    def load_model(self, filepath: str):
        """
        Load model from file.

        Args:
            filepath: Path to load the model from
        """
        if os.path.exists(filepath):
            checkpoint = torch.load(filepath, map_location=self.device)
            self.policy_net.load_state_dict(checkpoint['policy_net'])
            self.target_net.load_state_dict(checkpoint['target_net'])
            self.optimizer.load_state_dict(checkpoint['optimizer'])
            self.epsilon = checkpoint.get('epsilon', self.epsilon)
            self.step_count = checkpoint.get('step_count', self.step_count)

    def set_training_mode(self, training: bool = True):
        """
        Set training/evaluation mode.

        Args:
            training: Whether agent is in training mode
        """
        self.training_mode = training
        if not training:
            self.epsilon = 0.0  # No exploration during evaluation


def create_dqn_agent(state_dim: int, action_dim: int, **kwargs) -> DQNAgent:
    """
    Factory function to create DQN agent.

    Args:
        state_dim: Dimension of state space
        action_dim: Dimension of action space
        **kwargs: Additional arguments for DQNAgent

    Returns:
        Configured DQNAgent instance
    """
    return DQNAgent(state_dim, action_dim, config=kwargs)
