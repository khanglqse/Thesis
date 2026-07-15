"""Engine wrapper that perturbs observations (sensor noise) and injects incidents.

Duck-typed over CityFlowEngine / FakeEngine: the env talks to whichever engine it
is given, so wrapping it needs no env changes. OFF by default (exact passthrough),
so it never affects the frozen baselines. 3.6-safe (NumPy only).

Sensor noise is applied to the raw per-lane counts BEFORE any controller reads
them, so it degrades the observation-dependent controllers (DQN, Max-Pressure)
equally, while Fixed-Time / Random -- which ignore the counts -- are immune. That
asymmetry is exactly what the robustness study measures.
"""
import numpy as np


class PerturbedEngine(object):
    def __init__(self, inner, noise_std=0.0, noise_kind="gauss", seed=0, incident=None):
        """incident = (inter_id, t_start, t_end, block_phase) or None.

        During [t_start, t_end) engine-steps, set_tl_phase(inter_id, *) is forced
        to block_phase -- a stuck-signal / blockage that the controllers must
        recover from.
        """
        self._inner = inner
        self.noise_std = float(noise_std)
        self.noise_kind = noise_kind
        self._rng = np.random.RandomState(seed)
        self._incident = incident
        self._step_count = 0

    # --- lifecycle / passthrough ---
    def reset(self):
        self._step_count = 0
        return self._inner.reset()

    def step(self):
        self._step_count += 1
        return self._inner.step()

    def set_tl_phase(self, inter_id, phase):
        if self._incident is not None:
            iid, t0, t1, blk = self._incident
            if inter_id == iid and t0 <= self._step_count < t1:
                phase = blk
        return self._inner.set_tl_phase(inter_id, phase)

    def vehicle_count(self):
        return self._inner.vehicle_count()

    def average_travel_time(self):
        return self._inner.average_travel_time()

    # --- perturbed observations ---
    def _perturb(self, counts):
        if self.noise_std <= 0.0:
            return dict(counts)
        out = {}
        for lane, c in counts.items():
            if self.noise_kind == "dropout":
                out[lane] = 0 if self._rng.random_sample() < self.noise_std else c
            else:  # gaussian, scaled by lane magnitude, clamped to >= 0
                noisy = c + self._rng.normal(0.0, self.noise_std * max(1.0, abs(c)))
                out[lane] = max(0, int(round(noisy)))
        return out

    def lane_vehicle_counts(self):
        return self._perturb(self._inner.lane_vehicle_counts())

    def lane_waiting_counts(self):
        return self._perturb(self._inner.lane_waiting_counts())
