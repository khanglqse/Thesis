# SUMO Configuration for Vietnam Traffic Simulation

This directory contains SUMO (Simulation of Urban MObility) and mock SUMO configurations for simulating Vietnam traffic scenarios.

## Directory Structure

```
sumo_configs/
├── one_intersection/       # Single intersection configuration
│   ├── network.net.xml    # Network topology
│   ├── routes.rou.xml     # Vehicle routes and flows
│   ├── config.sumocfg     # SUMO simulation configuration
│   └── mock_config.yaml   # Mock configuration (for testing without SUMO)
│
└── three_intersections/    # Three intersection configuration
    ├── network.net.xml
    ├── routes.rou.xml
    ├── config.sumocfg
    └── mock_config.yaml
```

## Features

### Vietnam Traffic Characteristics

- **High motorcycle presence**: 40% of vehicles are motorcycles
- **Mixed vehicle types**: Cars, motorcycles, trucks, buses, and taxis
- **Typical speeds**: 40-50 km/h in urban areas
- **2-lane roads**: Each direction with 2 lanes (right lane for trucks/buses)
- **Traffic light controlled**: 4-phase traffic lights

### One Intersection

- Single 4-way intersection (North-South and East-West)
- 16 lanes total (4 directions × 2 lanes each × 2 directions)
- Suitable for basic RL agent training
- Lower computational requirements

### Three Intersections

- Linear chain of 3 intersections along a main arterial road
- Complex coordination between traffic lights
- Higher traffic density
- More realistic Vietnam road network pattern
- Suitable for advanced multi-intersection RL control

## Usage

### With SUMO (Real Simulation)

1. Install SUMO:
   ```bash
   # Using conda (recommended)
   conda install -c conda-forge eclipse-sumo
   
   # Or download from: https://www.eclipse.org/sumo/
   ```

2. Run simulation:
   ```bash
   cd one_intersection  # or three_intersections
   sumo -c config.sumocfg
   
   # With GUI
   sumo-gui -c config.sumocfg
   ```

3. With Python/TraCI:
   ```python
   import sumolib
   import traci
   
   # Start SUMO
   sumoCmd = ["sumo", "-c", "config.sumocfg"]
   traci.start(sumoCmd)
   
   # Your RL agent code here
   
   traci.close()
   ```

### Mock Mode (Without SUMO)

Use the `mock_config.yaml` file when SUMO is not available. This provides a simplified traffic environment for testing RL agents without full SUMO simulation.

```python
import yaml

with open('one_intersection/mock_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    
# Access network configuration
intersections = config['network']['intersections']
lanes = config['network']['lanes']

# Access traffic light configuration
traffic_lights = config['traffic_light']['intersections']
```

## Vehicle Types

| Type | Length (m) | Max Speed | Speed Factor | Probability | Typical Use |
|------|------------|-----------|--------------|-------------|-------------|
| Car | 4.5 | 13.89 (50 km/h) | 1.0 | 40% | Passengers |
| Motorcycle | 2.0 | 11.11 (40 km/h) | 1.1 | 40% | Motorcycles (common in Vietnam) |
| Truck | 7.5 | 11.11 (40 km/h) | 0.9 | 10% | Heavy goods |
| Bus | 12.0 | 11.11 (40 km/h) | 0.95 | 5% | Public transport |
| Taxi | 4.5 | 13.89 (50 km/h) | 1.0 | 5% | Taxis |

## Traffic Light Phases

### Phase Structure
- **Phase 0**: North-South Green (30 seconds)
- **Phase 1**: Yellow transition (3 seconds)
- **Phase 2**: East-West Green (30 seconds)
- **Phase 3**: Yellow transition (3 seconds)

### State Codes
- `G`: Green light
- `y`: Yellow light
- `r`: Red light

## Lane Naming Convention

Lanes are named using the pattern: `{origin}_{destination}_{lane_index}`

For example:
- `north_center_0`: From North to Center, first lane
- `center_south_1`: From Center to South, second lane
- `east_center_0`: From East to Center, first lane

## Integration with RL Agents

The configurations are designed to work with:
- DQN agents (`agents/dqn_agent.py`)
- PPO agents (`agents/ppo_agent.py`)
- Baseline controllers (`agents/baseline_controllers.py`)

### Example: Using with DQN Agent

```python
import sumolib
import traci
from agents.dqn_agent import create_dqn_agent

# Start SUMO
sumoCmd = ["sumo", "-c", "sumo_configs/one_intersection/config.sumocfg"]
traci.start(sumoCmd)

# Create agent
state_dim = 52  # 4 intersections × 13 features
action_dim = 4  # Number of intersections
agent = create_dqn_agent(state_dim, action_dim)

# Training loop
for step in range(1000):
    # Get state (lane vehicle counts, waiting times, etc.)
    state = get_traffic_state()
    
    # Agent selects action
    action = agent.select_action(state)
    
    # Apply action to traffic light
    apply_traffic_light_action(action)
    
    # Step simulation
    traci.simulationStep()
    
    # Get reward
    reward = calculate_reward()
    
    # Store experience
    agent.store_experience(state, action, reward, next_state, done)
    
    # Update agent
    if step % 100 == 0:
        agent.update_model()

traci.close()
```

## Metrics Tracked

The mock configuration tracks:
- Vehicle count per lane
- Average speed
- Waiting time
- Queue length
- Total delay
- Intersection coordination (for multi-intersection scenarios)

## Tips for Vietnam Traffic Simulation

1. **Motorcycle behavior**: Motorcycles tend to weave through traffic and have higher maneuverability
2. **Mixed traffic**: Passenger cars, motorcycles, and large vehicles share the same lanes
3. **Right-hand traffic**: Vehicles drive on the right side of the road
4. **Bus priority**: Buses have dedicated right lane access
5. **Slower speeds**: Urban speed limits are typically 40-50 km/h

## Troubleshooting

### SUMO not found
- Install SUMO using conda: `conda install -c conda-forge eclipse-sumo`
- Or download from https://www.eclipse.org/sumo/

### Lane ID errors
- Check that lane IDs in your Python code match the network definition
- Use `traci.lane.getIDList()` to see available lanes

### Traffic light control
- Use `traci.trafficlight.*` methods to control traffic lights
- Traffic light IDs match intersection IDs (e.g., "center1", "center2", "center3")

## References

- SUMO Documentation: https://sumo.dlr.de/docs/
- SUMO User Guide: https://sumo.dlr.de/docs/Users/User_Manual.html
- TraCI API: https://sumo.dlr.de/docs/TraCI.html

