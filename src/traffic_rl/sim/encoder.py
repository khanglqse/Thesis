"""Fixed-size, normalized observations + action masks for a shared policy.

Different intersections have different #lanes / #phases. We pad to the global
maxima so one network input/output shape fits every agent. 3.6-safe.
"""
import numpy as np


class ObservationEncoder:
    def __init__(self, roadnet, count_norm=10.0):
        self.count_norm = float(count_norm)
        ids = roadnet.signalized_ids()
        self._incoming = {i: roadnet.incoming_lanes(i) for i in ids}
        self._outgoing = {i: roadnet.outgoing_lanes(i) for i in ids}
        self._greens = {i: roadnet.green_phases(i) for i in ids}
        self.max_in = max(len(self._incoming[i]) for i in ids)
        self.max_out = max(len(self._outgoing[i]) for i in ids)
        self.max_green = max(len(self._greens[i]) for i in ids)
        # [incoming counts | outgoing counts | green one-hot]. Including the
        # downstream (outgoing) occupancy gives the agent the pressure signal
        # (incoming - outgoing) that Max-Pressure exploits.
        self.obs_dim = self.max_in + self.max_out + self.max_green

    def num_greens(self, inter_id):
        return len(self._greens[inter_id])

    def encode(self, inter_id, lane_counts, green_index):
        v = np.zeros(self.obs_dim, dtype=np.float32)
        for k, lane in enumerate(self._incoming[inter_id]):
            v[k] = lane_counts.get(lane, 0) / self.count_norm
        for k, lane in enumerate(self._outgoing[inter_id]):
            v[self.max_in + k] = lane_counts.get(lane, 0) / self.count_norm
        if 0 <= green_index < self.num_greens(inter_id):
            v[self.max_in + self.max_out + green_index] = 1.0
        return v

    def action_mask(self, inter_id):
        m = np.zeros(self.max_green, dtype=np.bool_)
        m[: self.num_greens(inter_id)] = True
        return m
