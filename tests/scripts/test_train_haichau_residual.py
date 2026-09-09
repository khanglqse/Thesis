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
    assert "--mode {smoke,pilot}" in result.stdout
