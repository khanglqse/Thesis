# 🚦 Migration Guide: Mock SUMO → Real SUMO

## Overview

This guide explains how to migrate from the mock SUMO environment to real SUMO for production traffic light control experiments. The mock environment is designed to provide identical interfaces to real SUMO, making the transition seamless.

---

## 📋 Prerequisites

### 1. SUMO Installation
```bash
# Ubuntu/Debian
sudo apt-get install sumo sumo-tools sumo-doc

# macOS
brew install sumo

# Windows
# Download from: https://www.eclipse.org/sumo/
```

### 2. Verify Installation
```bash
sumo --version
sumo-gui --version
```

### 3. Python Dependencies
```bash
pip install eclipse-sumo  # For TraCI Python bindings
```

---

## 🔄 Migration Steps

### Step 1: Update Configuration

Change `use_real_sumo` in your configuration:

```json
{
  "experiment_name": "real_sumo_study",
  "use_real_sumo": true,
  "scenario": "single_intersection",
  "max_steps": 3600,
  "step_length": 1.0,
  "traffic_demand": 0.15,
  "reward_function": "combined"
}
```

### Step 2: Update Environment Creation

The factory pattern makes switching automatic:

```python
from environment.env_factory import create_traffic_environment

# Same code works for both mock and real SUMO
config = {"use_real_sumo": True, "scenario": "single_intersection"}
env = create_traffic_environment(config)
```

### Step 3: Network Configuration

For real SUMO, you need to provide SUMO network files:

```python
# Real SUMO configuration
config = {
    "use_real_sumo": True,
    "network_file": "path/to/network.net.xml",
    "routes_file": "path/to/routes.rou.xml",
    "sumocfg_file": "path/to/simulation.sumocfg",
    "max_steps": 3600,
    "step_length": 1.0
}
```

---

## 🏗️ Network Setup for Real SUMO

### Single Intersection Network

1. **Create Network** (using SUMO netedit or programmatically):
```xml
<!-- network.net.xml -->
<net version="1.9" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <location netOffset="-200,-200" convBoundary="0,0,400,400"/>
  <edge id="north_south" from="north" to="south" priority="1"/>
  <edge id="south_north" from="south" to="north" priority="1"/>
  <edge id="east_west" from="east" to="west" priority="1"/>
  <edge id="west_east" from="west" to="east" priority="1"/>
</net>
```

2. **Create Routes**:
```xml
<!-- routes.rou.xml -->
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <vType id="car" length="5" maxSpeed="13.9" accel="2.6" decel="4.5"/>
  <route id="north_south" edges="north_south"/>
  <route id="south_north" edges="south_north"/>
  <route id="east_west" edges="east_west"/>
  <route id="west_east" edges="west_east"/>

  <!-- Flow definitions -->
  <flow id="north_south_flow" route="north_south" begin="0" end="3600" vehsPerHour="300"/>
  <flow id="south_north_flow" route="south_north" begin="0" end="3600" vehsPerHour="300"/>
  <flow id="east_west_flow" route="east_west" begin="0" end="3600" vehsPerHour="300"/>
  <flow id="west_east_flow" route="west_east" begin="0" end="3600" vehsPerHour="300"/>
</routes>
```

3. **Create Configuration**:
```xml
<!-- simulation.sumocfg -->
<configuration>
  <input>
    <net-file value="network.net.xml"/>
    <route-files value="routes.rou.xml"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="3600"/>
    <step-length value="1.0"/>
  </time>
  <processing>
    <time-to-teleport value="-1"/>
  </processing>
</configuration>
```

### Multi-Intersection Network

For 3-intersection network, create a grid layout:

```
Intersection 1 ←→ Intersection 2 ←→ Intersection 3
     ↑                    ↑                    ↑
     ↓                    ↓                    ↓
```

**Network Generation Script**:
```python
# generate_real_network.py
from environment.sumo_utils import generate_network_xml, generate_routes_xml, generate_sumocfg

# 3-intersection grid configuration
network_config = {
    'intersections': [
        {'id': 'intersection_1', 'x': 0, 'y': 0},
        {'id': 'intersection_2', 'x': 300, 'y': 0},
        {'id': 'intersection_3', 'x': 600, 'y': 0}
    ],
    'edge_length': 200.0
}

routes_config = {
    'vehicle_types': ['car', 'bus'],
    'routes': ['horizontal', 'vertical'],
    'flow_rate': 400  # vehicles per hour per direction
}

sumo_config = {
    'end_time': 3600,
    'step_length': 1.0
}

# Generate files
generate_network_xml(network_config, 'real_network.net.xml')
generate_routes_xml(routes_config, 'real_routes.rou.xml')
generate_sumocfg(sumo_config, 'real_simulation.sumocfg')
```

---

## 🔧 Code Changes Required

### 1. Import Changes

Mock environment:
```python
from environment.mock_traffic_env import SingleIntersectionMockEnv
```

Real SUMO environment:
```python
from environment.traffic_env import TrafficLightEnv
```

### 2. Environment Initialization

**Mock**:
```python
env = SingleIntersectionMockEnv(
    max_steps=3600,
    traffic_demand=0.15
)
```

**Real SUMO**:
```python
env = TrafficLightEnv(
    config={'network_file': 'network.net.xml'},
    use_gui=False,
    max_steps=3600
)
```

### 3. TraCI Integration

The mock environment provides identical TraCI interface:

```python
# Both mock and real support the same API
queue_length = traci.lane.getLastStepVehicleNumber(lane_id)
waiting_time = traci.lane.getWaitingTime(lane_id)
current_phase = traci.trafficlight.getPhase(intersection_id)
traci.trafficlight.setPhase(intersection_id, action)
time_elapsed = traci.simulation.getTime()
```

---

## 📊 Validation and Testing

### 1. Interface Compatibility Test

```python
def test_interface_compatibility():
    """Test that mock and real environments have identical interfaces."""

    # Mock environment
    mock_env = create_traffic_environment({'use_real_sumo': False})

    # Real environment (if available)
    try:
        real_env = create_traffic_environment({'use_real_sumo': True})
        print("✅ Both mock and real environments available")
    except ImportError:
        print("⚠️  Real SUMO not available, using mock only")

    # Test API compatibility
    obs1, _ = mock_env.reset()
    obs2, _ = real_env.reset() if 'real_env' in locals() else (obs1, _)

    print(f"Mock observation shape: {obs1.shape}")
    print(f"Real observation shape: {obs2.shape}")
```

### 2. Performance Benchmarking

```python
def benchmark_performance():
    """Compare performance between mock and real environments."""

    import time

    # Mock performance
    start_time = time.time()
    for _ in range(100):
        mock_env.step(mock_env.action_space.sample())
    mock_time = time.time() - start_time

    # Real SUMO performance (if available)
    if 'real_env' in locals():
        start_time = time.time()
        for _ in range(100):
            real_env.step(real_env.action_space.sample())
        real_time = time.time() - start_time

        print(f"Mock time: {mock_time:.2f}s")
        print(f"Real time: {real_time:.2f}s")
        print(f"Speed ratio: {real_time/mock_time:.1f}x")
```

---

## 🚨 Common Issues and Solutions

### Issue 1: SUMO Not Found
**Error**: `ModuleNotFoundError: No module named 'traci'`

**Solution**:
```bash
pip install eclipse-sumo
# or
conda install -c conda-forge eclipse-sumo
```

### Issue 2: Network Files Missing
**Error**: `FileNotFoundError: network.net.xml not found`

**Solution**:
- Generate network files using SUMO netedit
- Use the provided generation scripts
- Ensure files are in the correct directory

### Issue 3: TraCI Connection Failed
**Error**: `TraCIException: Connection could not be established`

**Solution**:
- Check if SUMO is running
- Verify sumocfg file paths
- Ensure no other SUMO processes are running

### Issue 4: Memory Issues
**Problem**: Real SUMO uses more memory than mock

**Solution**:
- Reduce simulation duration for testing
- Use fewer vehicles in routes
- Monitor system resources

---

## 🎯 Best Practices

### 1. Gradual Migration
1. Start with single intersection on real SUMO
2. Validate results match mock environment
3. Scale to multi-intersection
4. Optimize performance

### 2. Configuration Management
- Use JSON configuration files
- Version control configurations
- Document all parameter changes

### 3. Testing Strategy
- Unit tests for individual components
- Integration tests for full pipeline
- Performance regression tests

### 4. Monitoring and Logging
- Log all experiment parameters
- Save environment state periodically
- Monitor system resources

---

## 📁 Directory Structure

```
traffic-rl/
├── environment/
│   ├── mock_sumo.py              # Mock SUMO implementation
│   ├── mock_traffic_env.py       # Mock environments
│   ├── traffic_env.py           # Real SUMO environments
│   ├── env_factory.py           # Environment factory
│   └── sumo_utils.py            # SUMO file generation
├── experiments/
│   ├── run_mock_experiments.py  # Mock experiments
│   └── run_configured_experiments.py  # Configurable experiments
├── configs/
│   ├── mock_study_config.json   # Mock configuration
│   └── real_sumo_config.json    # Real SUMO configuration
└── results/
    ├── mock_experiments/        # Mock results
    └── real_sumo_experiments/   # Real SUMO results
```

---

## 🔄 Reverting to Mock Mode

If you encounter issues with real SUMO:

```python
# Easy switch back to mock
config = {
    "use_real_sumo": False,
    "scenario": "single_intersection"
}

env = create_traffic_environment(config)
```

---

## 📚 Further Reading

- [SUMO Documentation](https://sumo.dlr.de/docs/)
- [TraCI Python API](https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html)
- [SUMO NetEdit Tutorial](https://sumo.dlr.de/docs/Netedit/index.html)

**Ready to migrate?** Start with the single intersection scenario and gradually scale up! 🚀
