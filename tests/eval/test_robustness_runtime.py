import json

import pytest

from traffic_rl.eval.robustness_runtime import (
    materialize_demand_plus20,
    scheduled_departures,
)


def _row(interval=6.0, start=0, end=3599):
    return {"vehicle": {"length": 5}, "route": ["r0", "r1"],
            "interval": interval, "startTime": start, "endTime": end}


def test_demand_plus20_materialization_preserves_routes_and_conserves_count(tmp_path):
    source = tmp_path / "flow.json"
    source.write_text(json.dumps([_row(6.0), _row(10.0)]))
    target = tmp_path / "runtime/scaled.json"

    record = materialize_demand_plus20(source, target, multiplier=1.2)
    scaled = json.loads(target.read_text())

    assert [row["route"] for row in scaled] == [["r0", "r1"], ["r0", "r1"]]
    assert [row["interval"] for row in scaled] == pytest.approx([5.0, 10.0 / 1.2])
    assert record["scheduled_vehicles"] == sum(scheduled_departures(row) for row in scaled)
    assert record["source_scheduled_vehicles"] == sum(
        scheduled_departures(row) for row in json.loads(source.read_text()))
    assert record["scheduled_vehicles"] > record["source_scheduled_vehicles"]

    with pytest.raises(ValueError, match="refusing to replace"):
        materialize_demand_plus20(source, target, multiplier=1.2)
