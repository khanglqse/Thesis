"""Drive controllers through episodes and validate reproducible run manifests.
3.6-safe (used in-container with CityFlow)."""


def validate_experiment_manifest(manifest):
    """Validate the split/provenance contract used by final experiments."""
    if manifest.get("protocol_version") != 1:
        raise ValueError("protocol_version must be 1")

    valid_splits = ("train", "validation", "test")
    case_ids = set()
    demand_splits = {}
    case_counts = dict((split, 0) for split in valid_splits)
    for case in manifest.get("cases", []):
        case_id = case.get("case_id")
        split = case.get("split")
        demand_hash = case.get("demand_sha256")
        if not case_id or case_id in case_ids:
            raise ValueError("case_id must be present and unique")
        if split not in valid_splits:
            raise ValueError("split must be train, validation, or test")
        if not demand_hash:
            raise ValueError("demand_sha256 is required")
        prior = demand_splits.setdefault(demand_hash, split)
        if prior != split:
            raise ValueError("demand artifact appears in multiple splits")
        label = case.get("data_source_label", "")
        if label.startswith("observed") and not case.get("source_id"):
            raise ValueError("observed cases require source_id")
        case_ids.add(case_id)
        case_counts[split] += 1

    for run in manifest.get("runs", []):
        if run.get("case_id") not in case_ids:
            raise ValueError("run case_id is not declared")
        for field in ("run_id", "controller_id", "train_seed",
                      "demand_seed", "sim_seed"):
            if field not in run or run[field] is None:
                raise ValueError("run requires %s" % field)

    return {"case_counts": case_counts,
            "run_count": len(manifest.get("runs", []))}


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
    result = {
        "controller": getattr(controller, "name", controller.__class__.__name__),
        "agents": len(env.agent_ids),
        "steps": info.get("step"),
        "final_average_travel_time": info.get("average_travel_time"),
        "final_vehicle_count": info.get("vehicle_count"),
        "mean_total_queue": sum(queues) / n,
        "mean_reward": (sum(rewards) / len(rewards)) if rewards else 0.0,
        "queue_integral_vehicle_seconds": info.get(
            "queue_integral_vehicle_seconds", 0.0),
        "queue_integral_vehicle_hours": info.get(
            "queue_integral_vehicle_seconds", 0.0) / 3600.0,
        # Per-decision total-queue trace, so peak-window congestion can be
        # analysed/plotted (one value per action_interval).
        "queue_series": [float(q) for q in queues],
    }
    for field in ("scheduled", "due", "unreleased", "inserted", "arrived", "running", "pending",
                  "network_queue", "collisions", "emergency_braking",
                  "phase_switches"):
        result[field] = info.get(field)
    network_metrics = info.get("network_metrics")
    if network_metrics:
        result.update(network_metrics)
    else:
        scheduled = info.get("scheduled")
        result["completion_rate"] = (float(info.get("arrived", 0)) / scheduled
                                     if scheduled else None)
    return result
