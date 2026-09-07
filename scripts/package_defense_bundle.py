#!/usr/bin/env python3
"""Copy the self-contained viewer and evidence into the generated bundle."""
import hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/defense_bundle/v1"
for source,target in (("danang_defense.html","index.html"),("danang_defense.css","danang_defense.css"),("danang_defense.js","danang_defense.js"),("danang_defense_core.js","danang_defense_core.js")):
    shutil.copy2(ROOT/"frontend"/source,OUT/target)
shutil.copy2(ROOT/"results/danang_protocol_v1/summary/final-summary.json",OUT/"aggregate-summary.json")
(OUT/"serve.py").write_text("""from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler\nfrom pathlib import Path\nimport os,webbrowser\nos.chdir(Path(__file__).parent)\nserver=None\nfor port in range(8765,8776):\n    try:\n        server=ThreadingHTTPServer(('127.0.0.1',port),SimpleHTTPRequestHandler);break\n    except OSError:\n        pass\nif server is None: raise SystemExit('No free demo port from 8765 to 8775')\nurl='http://127.0.0.1:%d/'%server.server_port\nwebbrowser.open(url);print('Defense replay: '+url);server.serve_forever()\n""")
(OUT/"launch_demo.command").write_text("""#!/bin/sh\ncd \"$(dirname \"$0\")\"\nif command -v python3 >/dev/null 2>&1; then exec python3 serve.py; fi\necho \"Python 3 unavailable. Open fallbacks/demo-walkthrough.mp4 or fallbacks/result-summary.pdf\"\nread answer\n""")
(OUT/"launch_demo.command").chmod(0o755)
(OUT/"README.txt").write_text("""DA NANG THESIS DEFENSE DEMO\n\n1. Double-click launch_demo.command.\n2. The browser opens http://127.0.0.1:8765/.\n3. Start on PM peak at 30:00, press Play, then switch to Normal to show the limitation.\n4. If the browser path fails, open fallbacks/demo-walkthrough.mp4.\n5. If video fails, open fallbacks/result-summary.pdf.\n\nThis is an offline replay of frozen SUMO runs, not live training.\n""")
manifest=json.loads((OUT/"manifest.json").read_text())
manifest["assets"]=[]
for name in ("index.html","danang_defense.css","danang_defense.js","danang_defense_core.js","aggregate-summary.json","serve.py","launch_demo.command","README.txt"):
    path=OUT/name
    manifest["assets"].append({"path":name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(OUT)
