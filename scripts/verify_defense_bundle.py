#!/usr/bin/env python3
"""Fail closed when a defense bundle asset or metric has drifted."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BUNDLE=ROOT/"results/defense_bundle/v1"
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest=json.loads((BUNDLE/"manifest.json").read_text())
records=[manifest["network"],*manifest["runs"],*manifest.get("assets",[]),*manifest.get("fallbacks",[])]
for row in records:
    rel=row.get("replay_path") or row.get("path");expected=row.get("replay_sha256") or row.get("sha256")
    if not rel or not expected:continue
    path=BUNDLE/rel
    if not path.exists() or sha(path)!=expected:raise SystemExit("hash mismatch: "+str(rel))
for run in manifest["runs"]:
    replay=json.loads((BUNDLE/run["replay_path"]).read_text())
    if replay["metrics"]!=run["metrics"]:raise SystemExit("metric mismatch: "+run["replay_path"])
    if replay["frames"][0]["t"]!=5 or replay["frames"][-1]["t"]!=3600:raise SystemExit("incomplete replay: "+run["replay_path"])
for name in ("index.html","danang_defense.css","danang_defense.js","danang_defense_core.js"):
    if re.search(r'https?://',(BUNDLE/name).read_text()):raise SystemExit("remote dependency in "+name)
print("verified",len(manifest["runs"]),"runs",len(manifest.get("assets",[])),len(manifest.get("fallbacks",[])),"fallbacks")
