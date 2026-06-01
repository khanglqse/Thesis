"""Drive any controller through one episode and collect comparison metrics.
3.6-safe (used in-container with CityFlow)."""


def run_episode(env, controller, max_decisions=None):
    obs = env.reset()
    if hasattr(controller, "reset"):
        controller.reset()
    masks = env.action_masks()
    queues, rewards, info = [], [], {}
    done = False
    decisions = 0
    while not done:
        ctx = {"observations": obs,
               "waiting_counts": env.current_waiting_counts(),
               "action_masks": masks}
        actions = controller.act(ctx)
        obs, r, done, info = env.step(actions)
        masks = env.action_masks()
        queues.append(info["total_queue"])
        if r:
            rewards.append(sum(r.values()) / len(r))
        decisions += 1
        if max_decisions is not None and decisions >= max_decisions:
            break
    n = max(len(queues), 1)
    return {
        "controller": getattr(controller, "name", controller.__class__.__name__),
        "agents": len(env.agent_ids),
        "steps": info.get("step"),
        "final_average_travel_time": info.get("average_travel_time"),
        "final_vehicle_count": info.get("vehicle_count"),
        "mean_total_queue": sum(queues) / n,
        "mean_reward": (sum(rewards) / len(rewards)) if rewards else 0.0,
    }
