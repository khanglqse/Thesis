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


def pick_incident(rn, agent_ids, horizon, block_phase=None):
    """Construct a deterministic incident for a robustness run.

    Blocks the busiest signalized intersection (most incoming lanes; ties broken by
    the smallest id, so the choice is reproducible) at a fixed green for the middle
    third of the horizon -- a stuck-signal / local blockage the rest of the network
    must absorb and recover from. Returns the (inter_id, t_start, t_end, block_phase)
    tuple expected by ``PerturbedEngine(incident=...)``.

    block_phase defaults to the target's first *green* lightphase (holding one green
    while every conflicting movement stays red is the stuck-signal failure); the value
    is a real lightphase index because the env drives the engine with lightphase
    indices, not green-action indices.
    """
    target = max(sorted(agent_ids), key=lambda a: len(rn.incoming_lanes(a)))
    if block_phase is None:
        greens = rn.green_phases(target)
        block_phase = greens[0] if greens else 0
    t0 = horizon // 3
    t1 = 2 * horizon // 3
    return (target, t0, t1, block_phase)


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

    def vehicle_ids(self):
        return self._inner.vehicle_ids()

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

    def true_lane_waiting_counts(self):
        # Ground-truth (unperturbed) queue for the METRIC. The controller reads the
        # perturbed lane_waiting_counts()/lane_vehicle_counts() above; performance is
        # measured on the real queue so sensor noise degrades only what a policy actually
        # consumes, not the reported metric (Fixed-Time/Random stay flat by construction).
        return self._inner.lane_waiting_counts()
