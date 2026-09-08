"""Shared validation contract for bounded Hai Chau network replays."""

import math


METRIC_KEYS = (
    "queue_integral_vehicle_seconds", "completion_rate", "arrived",
    "running", "pending",
)


class NetworkReplayObserver(object):
    """Record compact node states on the five-second defense time grid."""

    def __init__(self, agent_ids, incoming_lanes, sample_seconds=5):
        self.agent_ids = list(agent_ids)
        if len(self.agent_ids) != len(set(self.agent_ids)):
            raise ValueError("replay agent IDs must be unique")
        self.incoming_lanes = dict(
            (node, list(incoming_lanes[node])) for node in self.agent_ids)
        self.sample_seconds = int(sample_seconds)
        if self.sample_seconds <= 0:
            raise ValueError("replay sample_seconds must be positive")
        self.frames = []

    def _frame(self, elapsed_seconds, waiting_counts, phases):
        if set(phases) != set(self.agent_ids):
            raise ValueError("replay phases must cover every controlled signal")
        nodes = {}
        for node_id in self.agent_ids:
            queue = sum(float(waiting_counts.get(lane_id, 0.0))
                        for lane_id in self.incoming_lanes[node_id])
            nodes[node_id] = {"queue": queue, "phase": int(phases[node_id])}
        return {"t": int(elapsed_seconds), "nodes": nodes, "vehicles": []}

    def reset(self, waiting_counts, phases):
        self.frames = [self._frame(0, waiting_counts, phases)]

    def observe(self, elapsed_seconds, waiting_counts, phases):
        elapsed = int(elapsed_seconds)
        if elapsed % self.sample_seconds == 0:
            self.frames.append(self._frame(elapsed, waiting_counts, phases))

    def finalize(self, metrics):
        return {
            "sample_seconds": self.sample_seconds,
            "frames": list(self.frames),
            "metrics": dict((key, metrics.get(key)) for key in METRIC_KEYS
                            if key in metrics),
        }


def validate_network(network):
    nodes = network.get("nodes", [])
    if network.get("controlled_signals") != 53 or len(nodes) != 53:
        raise ValueError("offline network must contain exactly 53 controlled signals")
    node_ids = [node.get("id") for node in nodes]
    if any(not isinstance(node_id, str) or not node_id for node_id in node_ids) \
            or len(set(node_ids)) != 53:
        raise ValueError("offline network node IDs must be present and unique")
    known = set(node_ids)
    for node in nodes:
        try:
            coordinates_valid = all(
                math.isfinite(float(node.get(axis))) for axis in ("x", "y"))
        except (TypeError, ValueError):
            coordinates_valid = False
        if not coordinates_valid:
            raise ValueError("offline network nodes require finite x/y coordinates")
        neighbors = node.get("neighbors")
        if not isinstance(neighbors, list):
            raise ValueError("offline network node neighbors must be a neighbor list")
        if any(neighbor not in known for neighbor in neighbors):
            raise ValueError("offline network node references an unknown neighbor")
        if len(neighbors) != len(set(neighbors)):
            raise ValueError("offline network neighbor IDs must be unique")
    links = network.get("links", [])
    if not isinstance(links, list):
        raise ValueError("offline network links must be a list")
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("offline network links must be objects")
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
