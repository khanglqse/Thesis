"""Parameter-shared DQN training loop over MultiAgentTrafficEnv. 3.6-safe.

Pools every agent's transition into one replay buffer and trains one shared
network (parameter sharing). Engine-agnostic via the env's factory.
"""
import json

import numpy as np

from traffic_rl.agents.dqn import SharedDQN, ReplayBuffer, NStepAccumulator
from traffic_rl.agents.max_pressure import MaxPressureController


def _epsilon(step, cfg):
    frac = min(1.0, float(step) / max(1, cfg["epsilon_decay_steps"]))
    return cfg["epsilon_start"] + frac * (cfg["epsilon_end"] - cfg["epsilon_start"])


def _warmstart(env, net, masks, cfg):
    """Pre-train the net to imitate Max-Pressure for warmstart_steps decisions.

    Behaviour-cloning the heuristic so RL fine-tuning starts AT Max-Pressure's
    level instead of cold (residual/warm-start idea, FitLight/CRL-TSC). Acts with
    Max-Pressure, batches (obs, mp_action) and minimises cross-entropy.
    """
    steps = int(cfg.get("warmstart_steps", 0))
    if steps <= 0:
        return
    mp = MaxPressureController(env.roadnet)
    obs = env.reset()
    done = False
    n = 0
    while n < steps:
        if done:
            obs = env.reset(); done = False
        ctx = {"observations": obs, "waiting_counts": env.current_waiting_counts(),
               "action_masks": masks}
        actions = mp.act(ctx)
        bo = np.stack([obs[a] for a in env.agent_ids])
        bt = np.array([actions[a] for a in env.agent_ids], dtype=np.int64)
        bm = np.stack([masks[a] for a in env.agent_ids])
        net.imitate_step(bo, bt, bm)
        obs, _, done, _ = env.step(actions)
        n += 1
    net.sync_target()


def train(env_factory, cfg, ckpt_path, log_path):
    env = env_factory()
    obs_dim = env.obs_dim
    n_actions = env.encoder.max_green
    rng = np.random.RandomState(cfg["seed"])
    n_step = int(cfg.get("n_step", 1))
    gamma_n = cfg["gamma"] ** n_step   # n-step bootstrap discount

    net = SharedDQN(obs_dim, n_actions, hidden=cfg["hidden"], lr=cfg["lr"], seed=cfg["seed"],
                    grad_clip=cfg.get("grad_clip"), huber_delta=cfg.get("huber_delta", 1.0),
                    dueling=cfg.get("dueling", False))
    buf = ReplayBuffer(cfg["buffer_capacity"], obs_dim, n_actions, seed=cfg["seed"])
    reward_scale = cfg.get("reward_scale", 1.0)
    masks = env.action_masks()

    # Warm-start from Max-Pressure (optional). After cloning, start RL at a low
    # epsilon so it exploits the imitated policy rather than re-exploring blindly.
    warmstart = int(cfg.get("warmstart_steps", 0)) > 0
    if warmstart:
        _warmstart(env, net, masks, cfg)
        cfg = dict(cfg); cfg["epsilon_start"] = cfg.get("warmstart_epsilon", 0.3)

    decisions = 0
    train_steps = 0
    # Record what this run optimised so the comparison/report can label the variant.
    log = {"meta": {"reward_type": getattr(env, "reward_type", "pressure"),
                    "state_mode": getattr(env, "state_mode", "basic"),
                    "dueling": bool(cfg.get("dueling", False)),
                    "n_step": n_step, "warmstart_steps": int(cfg.get("warmstart_steps", 0)),
                    "hidden": cfg["hidden"], "lr": cfg["lr"]},
           "episodes": []}

    for ep in range(cfg["episodes"]):
        obs = env.reset()
        done = False
        ep_rewards, ep_queues, ep_losses = [], [], []
        accs = {a: NStepAccumulator(n_step, cfg["gamma"]) for a in env.agent_ids}
        info = {}
        while not done:
            eps = _epsilon(decisions, cfg)
            actions = {}
            for a in env.agent_ids:
                if rng.rand() < eps:
                    valid = np.where(masks[a])[0]
                    actions[a] = int(rng.choice(valid))
                else:
                    actions[a] = net.greedy_action(obs[a], masks[a])
            next_obs, rewards, done, info = env.step(actions)
            for a in env.agent_ids:
                # Store scaled rewards so TD targets stay O(1) (stability); the log
                # below keeps the raw reward for comparability with the baselines.
                for tr in accs[a].push(obs[a], actions[a], rewards[a] * reward_scale,
                                       next_obs[a], 1.0 if done else 0.0, masks[a]):
                    buf.add(*tr)
            obs = next_obs
            decisions += 1
            ep_rewards.append(sum(rewards.values()) / len(rewards))
            ep_queues.append(info["total_queue"])

            if len(buf) >= cfg["train_start"]:
                b = buf.sample(cfg["batch_size"])
                loss = net.train_step(b["obs"], b["actions"], b["rewards"],
                                      b["next_obs"], b["dones"], b["next_mask"],
                                      gamma=gamma_n)
                ep_losses.append(loss)
                train_steps += 1
                if train_steps % cfg["target_sync"] == 0:
                    net.sync_target()

        log["episodes"].append({
            "episode": ep,
            "mean_reward": float(np.mean(ep_rewards)) if ep_rewards else 0.0,
            "mean_total_queue": float(np.mean(ep_queues)) if ep_queues else 0.0,
            "mean_loss": float(np.mean(ep_losses)) if ep_losses else 0.0,
            "final_average_travel_time": info.get("average_travel_time"),
            "epsilon": _epsilon(decisions, cfg),
        })
        net.save(ckpt_path)
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2)

    return net
