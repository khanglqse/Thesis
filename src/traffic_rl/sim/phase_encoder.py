"""Movement-aligned phase observations for the shared Hai Chau policy.

This module stays compatible with Python 3.6 for the CityFlow runtime.
"""
import math

import numpy as np


FEATURES = (
    "incoming_queue_mean", "incoming_queue_max", "incoming_running_mean",
    "outgoing_queue_mean", "outgoing_remaining_capacity_mean", "pressure",
    "is_current_phase", "elapsed_green", "upstream_queue_mean",
    "downstream_queue_mean", "time_since_service", "movement_count",
)

SCHEDULE_FEATURES = (
    "phase_row_cycle_fraction", "fixed_schedule_cycle_sin",
    "fixed_schedule_cycle_cos",
)
SCHEDULE_CONTEXT_FEATURES = FEATURES + SCHEDULE_FEATURES


def _mean(values):
    return float(sum(values)) / len(values) if values else 0.0


class PhaseFeatureEncoder:
    """Encode candidate greens by the movements each green serves."""

    def __init__(self, roadnet, count_norm, capacity_norm, max_green=None,
                 schedule_green_duration=None):
        self.roadnet = roadnet
        self.count_norm = float(count_norm)
        self.capacity_norm = float(capacity_norm)
        if self.count_norm <= 0 or self.capacity_norm <= 0:
            raise ValueError("normalization constants must be positive")
        self._ids = roadnet.signalized_ids()
        errors = []
        for inter_id in self._ids:
            errors.extend(roadnet.phase_contract(inter_id)["errors"])
        if errors:
            raise ValueError("invalid phase-role contract: %s" % "; ".join(errors))
        self._greens = {inter_id: roadnet.green_phases(inter_id)
                        for inter_id in self._ids}
        inferred = max(len(greens) for greens in self._greens.values())
        self.max_green = int(max_green) if max_green is not None else inferred
        if self.max_green < inferred:
            raise ValueError("max_green cannot be smaller than the network maximum")
        self.schedule_green_duration = (
            None if schedule_green_duration is None
            else float(schedule_green_duration))
        if (self.schedule_green_duration is not None
                and self.schedule_green_duration <= 0):
            raise ValueError("schedule_green_duration must be positive")
        self.feature_order = list(
            SCHEDULE_CONTEXT_FEATURES if self.schedule_green_duration is not None
            else FEATURES)

    def _neighbor_queue_mean(self, inter_ids, waiting_counts):
        lanes = []
        for inter_id in inter_ids:
            lanes.extend(self.roadnet.incoming_lanes(inter_id))
        return _mean([waiting_counts.get(lane, 0.0) for lane in lanes])

    def encode_all(self, inter_id, vehicle_counts, waiting_counts, green_index,
                   elapsed_green, time_since_service, elapsed_seconds=0.0):
        greens = self._greens[inter_id]
        features = np.zeros(
            (self.max_green, len(self.feature_order)), dtype=np.float32)
        mask = np.zeros(self.max_green, dtype=np.bool_)
        upstream_queue = self._neighbor_queue_mean(
            self.roadnet.upstream_neighbors(inter_id), waiting_counts)
        downstream_queue = self._neighbor_queue_mean(
            self.roadnet.downstream_neighbors(inter_id), waiting_counts)

        for phase_row, phase_idx in enumerate(greens):
            incoming, outgoing = self.roadnet.phase_movements(inter_id, phase_idx)
            movement_pairs = self.roadnet.phase_movement_pairs(inter_id, phase_idx)
            incoming_queue = [float(waiting_counts.get(lane, 0.0))
                              for lane in incoming]
            incoming_running = [max(0.0, float(vehicle_counts.get(lane, 0.0))
                                    - float(waiting_counts.get(lane, 0.0)))
                                for lane in incoming]
            outgoing_queue = [float(waiting_counts.get(lane, 0.0))
                              for lane in outgoing]
            outgoing_remaining = [max(0.0, self.capacity_norm
                                      - float(vehicle_counts.get(lane, 0.0)))
                                  for lane in outgoing]
            in_mean = _mean(incoming_queue)
            out_mean = _mean(outgoing_queue)
            since_service = (time_since_service[phase_row]
                             if phase_row < len(time_since_service) else 0.0)
            row = [
                in_mean / self.count_norm,
                (max(incoming_queue) if incoming_queue else 0.0) / self.count_norm,
                _mean(incoming_running) / self.count_norm,
                out_mean / self.count_norm,
                _mean(outgoing_remaining) / self.capacity_norm,
                (in_mean - out_mean) / self.count_norm,
                1.0 if phase_row == green_index else 0.0,
                float(elapsed_green) / self.count_norm,
                upstream_queue / self.count_norm,
                downstream_queue / self.count_norm,
                float(since_service) / self.count_norm,
                float(len(movement_pairs)) / self.count_norm,
            ]
            if self.schedule_green_duration is not None:
                period = self.schedule_green_duration * len(greens)
                angle = 2.0 * math.pi * (float(elapsed_seconds) % period) / period
                row.extend([
                    float(phase_row) / len(greens),
                    math.sin(angle),
                    math.cos(angle),
                ])
            features[phase_row] = np.asarray(row, dtype=np.float32)
            mask[phase_row] = True
        return features, mask
