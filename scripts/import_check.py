#!/usr/bin/env python3
"""Smoke: confirm every in-container module imports under Python 3.6 (CityFlow image).

  make cf-run CMD="PYTHONPATH=src python3 scripts/import_check.py"
"""
import traffic_rl.sim.multi_agent_env  # noqa: F401
import traffic_rl.sim.encoder          # noqa: F401
import traffic_rl.sim.intersection     # noqa: F401
import traffic_rl.network.roadnet      # noqa: F401
import traffic_rl.agents.dqn           # noqa: F401
import traffic_rl.agents.fixed_time    # noqa: F401
import traffic_rl.agents.max_pressure  # noqa: F401
import traffic_rl.agents.random_agent  # noqa: F401
import traffic_rl.train.trainer        # noqa: F401
import traffic_rl.eval.runner          # noqa: F401
import traffic_rl.eval.compare         # noqa: F401

print("3.6 imports OK")
