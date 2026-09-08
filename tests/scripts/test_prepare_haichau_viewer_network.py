import hashlib
import json

import pytest

from scripts.prepare_haichau_viewer_network import build_viewer
from traffic_rl.eval.network_replay import validate_network


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def test_builds_valid_geometry_in_manifest_agent_order(tmp_path):
    ids = ["N%02d" % index for index in range(53)]
    roadnet = tmp_path / "roadnet.json"
    _write(roadnet, {
        "intersections": [{"id": node, "point": {"x": i, "y": i % 4}}
                          for i, node in enumerate(ids)],
        "roads": [{"startIntersection": ids[0], "endIntersection": ids[1]}],
    })
    digest = hashlib.sha256(roadnet.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    _write(manifest, {"network": {
        "path": "roadnet.json", "sha256": digest, "agent_ids": ids,
    }})

    result = build_viewer(tmp_path, "manifest.json", "release/viewer.json")
    document = json.loads((tmp_path / result["path"]).read_text())

    assert [node["id"] for node in document["nodes"]] == ids
    assert document["nodes"][0]["neighbors"] == [ids[1]]
    assert validate_network(document) == set(ids)


def test_refuses_network_hash_drift(tmp_path):
    _write(tmp_path / "roadnet.json", {"intersections": [], "roads": []})
    _write(tmp_path / "manifest.json", {"network": {
        "path": "roadnet.json", "sha256": "0" * 64,
        "agent_ids": ["N%02d" % index for index in range(53)],
    }})

    with pytest.raises(ValueError, match="network hash drift"):
        build_viewer(tmp_path, "manifest.json", "viewer.json")
