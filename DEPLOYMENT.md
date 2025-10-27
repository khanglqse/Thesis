# Deployment Guide

## Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd traffic-rl
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional) Set up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running Experiments

### Basic Run
```bash
python3 run_experiment.py
```

### With Options
```bash
# Run without DQN training
python3 run_experiment.py --no-train

# Run with real SUMO (requires SUMO installation)
python3 run_experiment.py --use-sumo

# Specify config type
python3 run_experiment.py --config three_intersections
```

## File Organization

### Results Structure
```
results/
├── experiments/          # Individual experiment data
│   ├── results_*.json   # Experiment metrics
│   └── plots/           # Historical plots
├── plots/              # Latest visualizations
└── models/            # Trained model checkpoints
```

### Logs
- Logs are saved to `logs/`
- Each experiment creates a timestamped log file

## Troubleshooting

### Mock Environment Errors
If you see errors related to mock environment:
- Ensure `mock_config.yaml` exists in `sumo_configs/*/`
- Check that YAML structure matches expected format

### SUMO Connection Issues
If using real SUMO:
- Verify SUMO installation: `sumo --version`
- Check SUMO_HOME environment variable
- Ensure SUMO path is in system PATH

### Memory Issues
If running out of memory during training:
- Reduce `MAX_STEPS` in config
- Decrease `BATCH_SIZE`
- Use shorter `TRAINING_STEPS`

## Performance Tips

1. **For faster iteration**: Reduce `TRAINING_STEPS` (e.g., 500)
2. **For better results**: Increase `TRAINING_STEPS` (e.g., 2000+)
3. **For production**: Train for 5000+ steps

## Cleaning Old Results

```bash
# Clean old experiments
rm -rf results/experiments/*

# Clean old plots
rm -rf results/plots/*

# Keep directory structure
touch results/experiments/.gitkeep
touch results/plots/.gitkeep
```

