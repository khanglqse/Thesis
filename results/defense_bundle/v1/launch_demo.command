#!/bin/sh
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then exec python3 serve.py; fi
echo "Python 3 unavailable. Open fallbacks/demo-walkthrough.mp4 or fallbacks/result-summary.pdf"
read answer
