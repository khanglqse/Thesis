#!/bin/bash

# Thesis Experiments Runner Script
# This script runs all experiments needed for the master's thesis

echo "========================================================================"
echo "  TRAFFIC LIGHT CONTROL - MASTER'S THESIS EXPERIMENTS"
echo "========================================================================"
echo ""
echo "This script will:"
echo "  1. Run baseline controllers (Fixed-Time, Actuated, Adaptive, Random)"
echo "  2. Train and evaluate RL agents (DQN)"
echo "  3. Generate comprehensive visualizations"
echo "  4. Create summary reports for thesis"
echo ""

# Check if running in quick test mode
QUICK_MODE=""
if [ "$1" == "--quick" ]; then
    QUICK_MODE="--quick-test"
    echo "⚡ QUICK TEST MODE - Using minimal episodes for testing"
    echo ""
fi

# Navigate to experiments directory
cd "$(dirname "$0")"

echo "------------------------------------------------------------------------"
echo "Step 1: Running Comprehensive Study"
echo "------------------------------------------------------------------------"
python3 experiments/run_comprehensive_study.py $QUICK_MODE

if [ $? -ne 0 ]; then
    echo ""
    echo "✗ Experiments failed! Check the error messages above."
    exit 1
fi

echo ""
echo "------------------------------------------------------------------------"
echo "Step 2: Generating Visualizations"
echo "------------------------------------------------------------------------"
python3 visualization/comprehensive_visualization.py

if [ $? -ne 0 ]; then
    echo ""
    echo "✗ Visualization generation failed! Check the error messages above."
    exit 1
fi

echo ""
echo "========================================================================"
echo "  ✓ ALL THESIS EXPERIMENTS COMPLETED SUCCESSFULLY!"
echo "========================================================================"
echo ""
echo "Results Location:"
echo "  • Data: ./results/"
echo "  • Figures: ./results/figures/"
echo "  • Summary: ./results/comprehensive_study_summary.csv"
echo ""
echo "You can now use these results in your thesis!"
echo ""

