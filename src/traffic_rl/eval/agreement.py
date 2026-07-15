"""Per-decision agreement between the learned DQN and the Max-Pressure heuristic.

Quantifies the thesis's central claim -- that the DQN rediscovers Max-Pressure-like
control from raw local counts -- by, at every decision, also computing the phase
Max-Pressure WOULD choose from the same state (without applying it) and recording
whether the two agree, per intersection. 3.6-safe.
"""


class AgreementLogger(object):
    def __init__(self):
        self._n_decisions = 0
        self._agree = 0
        self._pairs = 0
        self._per_agent = {}          # id -> [agree_count, total]

    def record(self, dqn_actions, mp_actions):
        self._n_decisions += 1
        for a, da in dqn_actions.items():
            if a not in mp_actions:
                continue
            self._pairs += 1
            ok = 1 if int(da) == int(mp_actions[a]) else 0
            self._agree += ok
            slot = self._per_agent.setdefault(a, [0, 0])
            slot[0] += ok
            slot[1] += 1

    def summary(self):
        per = dict((a, (g / float(t) if t else 0.0))
                   for a, (g, t) in self._per_agent.items())
        return {
            "n_decisions": self._n_decisions,
            "n_pairs": self._pairs,
            "agree": self._agree,
            "agree_rate": (self._agree / float(self._pairs) if self._pairs else 0.0),
            "per_agent": per,
        }


def run_agreement(env, dqn_controller, mp_controller, max_decisions=None):
    """Drive the DQN through an episode; at each step also query Max-Pressure on the
    same context (not applied) and log agreement. Returns AgreementLogger.summary()."""
    obs = env.reset()
    if hasattr(dqn_controller, "reset"):
        dqn_controller.reset()
    masks = env.action_masks()
    lg = AgreementLogger()
    done = False
    decisions = 0
    while not done:
        ctx = {"observations": obs,
               "waiting_counts": env.current_waiting_counts(),
               "action_masks": masks}
        dqn_actions = dqn_controller.act(ctx)
        mp_actions = mp_controller.act(ctx)        # computed for comparison, NOT applied
        lg.record(dqn_actions, mp_actions)
        obs, _, done, _ = env.step(dqn_actions)    # the DQN drives the sim
        masks = env.action_masks()
        decisions += 1
        if max_decisions is not None and decisions >= max_decisions:
            break
    return lg.summary()
