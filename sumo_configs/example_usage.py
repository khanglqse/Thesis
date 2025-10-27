"""
Example usage of SUMO configurations for Vietnam traffic simulation.
"""

from config_loader import SumoConfigLoader, MockSumoEnvironment


def example_real_sumo():
    """Example of using real SUMO configuration."""
    print("=" * 60)
    print("Example 1: Loading Real SUMO Configuration")
    print("=" * 60)
    
    # Load configuration for one intersection
    config = SumoConfigLoader("one_intersection")
    
    print(f"\nNetwork file: {config.get_network_path()}")
    print(f"Routes file: {config.get_routes_path()}")
    print(f"\nSUMOCmd: {' '.join(config.get_sumo_command())}")
    print(f"\nSUMO GUI Cmd: {' '.join(config.get_sumo_gui_command())}")
    
    # Example of using with TraCI
    print("\n# Python code to run SUMO with TraCI:")
    print("""
import traci

# Start SUMO
sumoCmd = {config.get_sumo_command()}
traci.start(sumoCmd)

# Run simulation
for step in range(100):
    traci.simulationStep()
    # Your RL agent code here
    
traci.close()
    """)


def example_mock_environment():
    """Example of using mock environment."""
    print("\n" + "=" * 60)
    print("Example 2: Using Mock SUMO Environment")
    print("=" * 60)
    
    # Create mock environment for one intersection
    mock_env = MockSumoEnvironment("one_intersection")
    
    print(f"\nNumber of lanes: {len(mock_env.get_lane_ids())}")
    print(f"State dimension: {len(mock_env.get_state_vector())}")
    print(f"\nAvailable lanes: {mock_env.get_lane_ids()[:5]}...")
    
    # Show initial state
    print("\nInitial State:")
    lane_id = mock_env.get_lane_ids()[0]
    print(f"  Lane '{lane_id}':")
    print(f"    Vehicle count: {mock_env.get_vehicle_count(lane_id)}")
    print(f"    Waiting time: {mock_env.get_waiting_time(lane_id)}")
    print(f"    Queue length: {mock_env.get_queue_length(lane_id)}")
    
    # Run simulation steps
    print("\nRunning 10 simulation steps...")
    for step in range(10):
        mock_env.step()
        state = mock_env.get_state_vector()
        vehicle_count = state[0]  # First lane vehicle count
        
        if step % 2 == 0:
            print(f"  Step {step}: Vehicle count on first lane = {vehicle_count}")
    
    # Show final state
    print(f"\nFinal State after 10 steps:")
    lane_id = mock_env.get_lane_ids()[0]
    print(f"  Lane '{lane_id}':")
    print(f"    Vehicle count: {mock_env.get_vehicle_count(lane_id)}")
    print(f"    Waiting time: {mock_env.get_waiting_time(lane_id):.2f}")
    print(f"    Queue length: {mock_env.get_queue_length(lane_id)}")


def example_three_intersections():
    """Example for three intersections."""
    print("\n" + "=" * 60)
    print("Example 3: Three Intersections Configuration")
    print("=" * 60)
    
    config = SumoConfigLoader("three_intersections")
    mock_env = MockSumoEnvironment("three_intersections")
    
    print(f"\nThree intersections configuration loaded.")
    print(f"Number of lanes: {len(mock_env.get_lane_ids())}")
    print(f"State dimension: {len(mock_env.get_state_vector())}")
    
    # Show traffic light phases
    print("\nTraffic light phases:")
    for tl_id in mock_env.traffic_lights.keys():
        current_phase = mock_env.get_traffic_light_phase(tl_id)
        print(f"  {tl_id}: Phase {current_phase}")


def example_with_dqn_agent():
    """Example of integrating with DQN agent."""
    print("\n" + "=" * 60)
    print("Example 4: Integration with DQN Agent")
    print("=" * 60)
    
    print("""
# Example code to use SUMO config with DQN agent

import traci
from agents.dqn_agent import create_dqn_agent
from sumo_configs import SumoConfigLoader

# Load configuration
config = SumoConfigLoader("one_intersection")

# Start SUMO
sumoCmd = config.get_sumo_command()
traci.start(sumoCmd)

# Create agent
# For one intersection: ~16 lane features + 1 traffic light phase
state_dim = 16 * 3 + 1  # vehicle_count, waiting_time, queue_length for each lane + phase
action_dim = 2  # Two phases (NS or EW)

agent = create_dqn_agent(
    state_dim=state_dim,
    action_dim=action_dim,
    learning_rate=5e-4,
    gamma=0.99,
    epsilon_start=1.0,
    epsilon_end=0.01
)

# Training loop
for step in range(1000):
    # Get current state
    state = []
    
    # Collect lane information
    for lane_id in traci.lane.getIDList():
        state.append(traci.lane.getLastStepVehicleNumber(lane_id))
        state.append(traci.lane.getWaitingTime(lane_id))
        state.append(traci.lane.getLastStepHaltingNumber(lane_id))
    
    # Add current phase
    state.append(traci.trafficlight.getPhase("center"))
    
    # Agent selects action
    action = agent.select_action(state)
    
    # Apply action to traffic light
    if action != traci.trafficlight.getPhase("center"):
        traci.trafficlight.setPhase("center", action)
    
    # Step simulation
    traci.simulationStep()
    
    # Calculate reward (example: minimize waiting time)
    total_waiting = sum(traci.lane.getWaitingTime(lane_id) for lane_id in traci.lane.getIDList())
    reward = -total_waiting / 100.0
    
    # Get next state and done flag
    next_state = [traci.lane.getLastStepVehicleNumber(lane_id) 
                  for lane_id in traci.lane.getIDList()]
    
    # Store experience
    agent.store_experience(state, action, reward, next_state, False)
    
    # Update agent
    if len(agent.replay_buffer) > 64:
        loss = agent.update_model()
        if step % 100 == 0:
            print(f"Step {step}, Loss: {loss:.4f}")
    
    # Update epsilon
    agent.update_epsilon()

traci.close()
print("Training complete!")
    """)


if __name__ == "__main__":
    # Run examples
    example_real_sumo()
    example_mock_environment()
    example_three_intersections()
    example_with_dqn_agent()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)

