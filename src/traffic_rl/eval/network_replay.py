"""Shared validation contract for bounded Hai Chau network replays."""

import math


METRIC_KEYS = (
    "queue_integral_vehicle_seconds", "completion_rate", "arrived",
    "running", "pending",
)


def validate_network(network):
    nodes = network.get("nodes", [])
    if network.get("controlled_signals") != 53 or len(nodes) != 53:
        raise ValueError("offline network must contain exactly 53 controlled signals")
    node_ids = [node.get("id") for node in nodes]
    if None in node_ids or len(set(node_ids)) != 53:
        raise ValueError("offline network node IDs must be present and unique")
    known = set(node_ids)
    for link in network.get("links", []):
        if link.get("source") not in known or link.get("target") not in known:
            raise ValueError("offline network link references an unknown node")
    return known


def validate_replay(run, metrics, replay, node_ids):
    if replay.get("sample_seconds") != 5:
        raise ValueError("replay frames must use a five-second sample interval")
    horizon = int(run["horizon_steps"])
    if horizon % 5:
        raise ValueError("replay horizon must be divisible by five seconds")
    expected_times = list(range(0, horizon + 1, 5))
    frames = replay.get("frames", [])
    times = [int(frame.get("t", -1)) for frame in frames]
    if times != expected_times:
        raise ValueError("replay frames must cover the full horizon every five seconds")
    for frame in frames:
        states = frame.get("nodes", {})
        if set(states) != node_ids:
            raise ValueError("every replay frame must contain all 53 signal states")
        for state in states.values():
            queue = float(state.get("queue", -1))
            if not math.isfinite(queue) or queue < 0 or state.get("phase") is None:
                raise ValueError("replay node state requires queue and phase")
        for vehicle in frame.get("vehicles", []):
            try:
                valid_position = all(math.isfinite(float(vehicle.get(axis)))
                                     for axis in ("x", "y"))
            except (TypeError, ValueError):
                valid_position = False
            if not valid_position:
                raise ValueError("visible vehicle requires finite x and y")
    replay_metrics = replay.get("metrics", {})
    for key in METRIC_KEYS:
        if key in metrics and replay_metrics.get(key) != metrics[key]:
            raise ValueError("replay metric mismatch: %s" % key)
