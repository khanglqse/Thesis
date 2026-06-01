#!/usr/bin/env python3
"""Render docs/chapter4_results.md from the real result files.

  PYTHONPATH=src python3 scripts/export_chapter4.py [area]

`area` defaults to "full" and selects results/<area>/comparison.json and
results/<area>/train_log_<area>.json. Figures are referenced relative to the
output document, pointing at the existing PNGs under results/<area>/.
"""
import os
import sys
from pathlib import Path

from traffic_rl.report.loader import load_json
from traffic_rl.report.chapter4 import build_chapter4

ROOT = Path(__file__).resolve().parent.parent


def main():
    os.chdir(str(ROOT))
    area = sys.argv[1] if len(sys.argv) > 1 else "full"
    results_dir = ROOT / "results" / area
    comparison = load_json(str(results_dir / "comparison.json"))
    train_log = load_json(str(results_dir / "train_log_{}.json".format(area)))
    # Figures live in results/<area>/; the doc lives in docs/ -> ../results/<area>
    fig_dir = "../results/{}".format(area)
    md = build_chapter4(comparison, train_log, fig_dir=fig_dir)
    out = ROOT / "docs" / "chapter4_results.md"
    out.write_text(md)
    print("wrote {} ({} chars)".format(out, len(md)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
