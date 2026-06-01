#!/usr/bin/env python3
"""Serve the vendored CityFlow web frontend and open it in a browser.

  python3 scripts/serve_replay.py [--port 8080] [--area full] [--no-browser]

The CityFlow frontend loads the roadnet JSON and replay TXT through in-browser
file pickers, so this just serves the repo over HTTP (CDN libs need https) and
prints which files to choose. Use the truncated demo replays so the browser can
load them (see scripts/truncate_replay.py).
"""
import argparse
import functools
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
REQUIRED = ["index.html", "script.js", "Point.js", "style.css", "spinner.css"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--area", default="full")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    missing = [f for f in REQUIRED if not (FRONTEND / f).exists()]
    if missing:
        raise SystemExit(
            "Frontend not vendored (missing: {}). Run the vendoring step in "
            "Task 6 of the plan, or scripts/truncate_replay.py docs.".format(missing))

    demo_dir = ROOT / "results" / args.area / "demo"
    roadnet = "data/danang/replay_roadnet_{}.json".format(args.area)
    os.chdir(str(ROOT))
    url = "http://localhost:{}/frontend/index.html".format(args.port)

    print("Serving {} at http://localhost:{}/".format(ROOT, args.port))
    print("Open: {}".format(url))
    print("In the page, pick:")
    print("  Roadnet file: {}".format(roadnet))
    if demo_dir.exists():
        demos = sorted(demo_dir.glob("replay_*_demo.txt"))
        if demos:
            print("  Replay file (choose one):")
            for d in demos:
                print("    {}".format(d.relative_to(ROOT)))
        else:
            print("  Replay file: results/{}/demo/  (empty — run "
                  "scripts/truncate_replay.py {})".format(args.area, args.area))
    else:
        print("  Replay file: run `python3 scripts/truncate_replay.py {}` first "
              "to create results/{}/demo/".format(args.area, args.area))
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        webbrowser.open(url)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT))
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
