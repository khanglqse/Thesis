"""Fixed-size, normalized observations + action masks for a shared policy.

Different intersections have different #lanes / #phases. We pad to the global
maxima so one network input/output shape fits every agent. 3.6-safe.

Two state modes:
  "basic" - [incoming counts | outgoing counts | green one-hot]. The incoming/
            outgoing occupancy gives the pressure signal Max-Pressure exploits.
  "ats"   - Advanced-XLight-style traffic state (arXiv 2112.10107): per incoming
            lane we separate QUEUED vehicles from RUNNING (moving) vehicles, and
            add outgoing queues. Layout: [incoming queue | incoming running |
            outgoing queue | green one-hot]. The running-vehicle channel is
            approaching demand that has not queued yet - the signal Max-Pressure
            is blind to - which is why it lets the learned policy beat MP.
"""
import numpy as np


class ObservationEncoder:
    def __init__(self, roadnet, count_norm=10.0, state_mode="basic"):
        self.count_norm = float(count_norm)
        self.state_mode = state_mode
        ids = roadnet.signalized_ids()
        self._incoming = {i: roadnet.incoming_lanes(i) for i in ids}
        self._outgoing = {i: roadnet.outgoing_lanes(i) for i in ids}
        self._greens = {i: roadnet.green_phases(i) for i in ids}
        self.max_in = max(len(self._incoming[i]) for i in ids)
        self.max_out = max(len(self._outgoing[i]) for i in ids)
        self.max_green = max(len(self._greens[i]) for i in ids)
        if state_mode == "ats":
            # incoming queue + incoming running + outgoing queue + phase one-hot
            self.obs_dim = 2 * self.max_in + self.max_out + self.max_green
        elif state_mode == "basic":
            self.obs_dim = self.max_in + self.max_out + self.max_green
            self.feature_order = (
                ["incoming_lane_count_%d" % index for index in range(self.max_in)]
                + ["outgoing_lane_count_%d" % index for index in range(self.max_out)]
                + ["green_phase_%d" % index for index in range(self.max_green)])
        elif state_mode == "neighbor":
            # basic + 2 mean-pooled upstream-neighbour features (CoLight-lite).
            self.obs_dim = self.max_in + self.max_out + self.max_green + 2
            self._nb_in = {}
            self._nb_out = {}
            for i in ids:
                nbs = roadnet.upstream_neighbors(i)
                nin, nout = [], []
                for n in nbs:
                    nin.extend(roadnet.incoming_lanes(n))
                    nout.extend(roadnet.outgoing_lanes(n))
                self._nb_in[i] = nin
                self._nb_out[i] = nout
        else:
            raise ValueError("unknown state_mode %r (basic|ats|neighbor)" % state_mode)

    def num_greens(self, inter_id):
        return len(self._greens[inter_id])

    def encode(self, inter_id, lane_counts, green_index, waiting_counts=None):
        """Encode one agent's observation.

        lane_counts: ALL vehicles per lane (get_lane_vehicle_count).
        waiting_counts: QUEUED vehicles per lane (get_lane_waiting_vehicle_count);
        required for "ats" mode (running = all - waiting).
        """
        if self.state_mode == "ats":
            return self._encode_ats(inter_id, lane_counts, waiting_counts, green_index)
        v = np.zeros(self.obs_dim, dtype=np.float32)
        for k, lane in enumerate(self._incoming[inter_id]):
            v[k] = lane_counts.get(lane, 0) / self.count_norm
        for k, lane in enumerate(self._outgoing[inter_id]):
            v[self.max_in + k] = lane_counts.get(lane, 0) / self.count_norm
        if 0 <= green_index < self.num_greens(inter_id):
            v[self.max_in + self.max_out + green_index] = 1.0
        if self.state_mode == "neighbor":
            base = self.max_in + self.max_out + self.max_green
            nin = self._nb_in[inter_id]
            nout = self._nb_out[inter_id]
            if nin:
                v[base] = sum(lane_counts.get(l, 0) for l in nin) / len(nin) / self.count_norm
            if nout:
                v[base + 1] = sum(lane_counts.get(l, 0) for l in nout) / len(nout) / self.count_norm
        return v

    def _encode_ats(self, inter_id, lane_counts, waiting_counts, green_index):
        waiting_counts = waiting_counts or {}
        v = np.zeros(self.obs_dim, dtype=np.float32)
        base_run = self.max_in
        base_out = 2 * self.max_in
        base_green = 2 * self.max_in + self.max_out
        for k, lane in enumerate(self._incoming[inter_id]):
            allc = lane_counts.get(lane, 0)
            queued = waiting_counts.get(lane, 0)
            running = max(0.0, allc - queued)        # moving / approaching demand
            v[k] = queued / self.count_norm
            v[base_run + k] = running / self.count_norm
        for k, lane in enumerate(self._outgoing[inter_id]):
            v[base_out + k] = waiting_counts.get(lane, 0) / self.count_norm
        if 0 <= green_index < self.num_greens(inter_id):
            v[base_green + green_index] = 1.0
        return v

    def action_mask(self, inter_id):
        m = np.zeros(self.max_green, dtype=np.bool_)
        m[: self.num_greens(inter_id)] = True
        return m
