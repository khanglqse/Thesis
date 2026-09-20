#!/bin/sh
cd "$(dirname "$0")"
exec python3 launch_demo.py --bundle . "$@"
