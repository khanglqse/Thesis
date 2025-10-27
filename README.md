# Traffic Control with Reinforcement Learning

A traffic signal control system using Deep Q-Network (DQN) for optimizing intersection performance.

## 📁 Project Structure

```
traffic-rl/
├── src/                          # Core source code
│   ├── agents/                   # RL agents and controllers
│   │   ├── baseline_controllers.py
│   │   ├── dqn_agent.py
│   │   └── ppo_agent.py
│   ├── environment.py            # Traffic environment
│   └── visualization.py          # Plotting utilities
│
├── experiments/                  # Experiment scripts
│   ├── experiment.py             # Experiment runner
│   ├── run_one_intersection_mock.py
│   ├── run_one_intersection_sumo.py
│   ├── run_three_intersections_mock.py
│   └── run_three_intersections_sumo.py
│
├── sumo_configs/                 # SUMO configurations
│   ├── one_intersection/
│   └── three_intersections/
│
├── results/                      # Experiment results
│   ├── one_intersection/
│   │   ├── experiments/          # JSON results
│   │   └── plots/               # Visualizations
│   └── three_intersections/
│       ├── experiments/
│       └── plots/
│
├── paper/                        # LaTeX thesis files
├── logs/                         # Log files
└── README.md                     # This file
```

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running Experiments

**One Intersection with Mock Environment:**
```bash
cd experiments
python3 run_one_intersection_mock.py
```

**One Intersection with Real SUMO:**
```bash
python3 run_one_intersection_sumo.py
```

**Three Intersections with Mock Environment:**
```bash
python3 run_three_intersections_mock.py
```

**Three Intersections with Real SUMO:**
```bash
python3 run_three_intersections_sumo.py
```

## 🧪 Experiments

The system compares multiple traffic control methods:

1. **Fixed-Time Controller**: Predefined phase durations
2. **Actuated Controller**: Vehicle-actuated signal control
3. **Adaptive Controller**: Dynamic phase adjustment
4. **Random Controller**: Random phase switching (baseline)
5. **DQN Agent**: Deep Reinforcement Learning approach

## 📊 Results

Results are automatically saved to:
- `results/{one_intersection|three_intersections}/experiments/` - JSON data
- `results/{one_intersection|three_intersections}/plots/` - Visualizations

Each experiment includes:
- Comparison plots
- Time series visualizations
- Performance metrics
- Statistical summaries

## ⚙️ Configuration

### Mock vs SUMO

- **Mock Environment**: No SUMO installation required, faster for development
- **Real SUMO**: Requires SUMO installation for realistic simulation

To install SUMO: https://www.eclipse.org/sumo/

## 🔧 Development

```bash
# Run mock experiments (no SUMO needed)
python3 experiments/run_one_intersection_mock.py

# Run with real SUMO
python3 experiments/run_one_intersection_sumo.py
```

## 📝 License

See paper/ for thesis documents.
