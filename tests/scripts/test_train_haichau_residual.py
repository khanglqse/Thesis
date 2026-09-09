import os
from pathlib import Path
import subprocess
import sys


def test_residual_cli_help_works_with_standard_src_pythonpath():
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run([sys.executable, str(root / "scripts/train_haichau_residual.py"), "--help"],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--mode {smoke,pilot,final}" in result.stdout
    assert "--selected-config" in result.stdout
    assert "--selection-spec" in result.stdout


def test_final_residual_cli_fails_closed_without_selected_pilot_inputs():
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, str(root / "scripts/train_haichau_residual.py"),
         "--mode", "final", "--learning-seed", "12", "--output", "temporary"],
        cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "--selected-config and --selection-spec" in result.stderr


def test_final_residual_selector_cli_help_works_with_standard_src_pythonpath():
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, str(root / "scripts/select_haichau_residual_final.py"), "--help"],
        cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "learning-seed" in result.stdout
