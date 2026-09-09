"""Immutable release binding for a selected Hai Chau residual pilot.

This adapter deliberately sits after the preregistered pilot selector.  It
never changes the pilot config: it derives final confirmatory runs from the
selected YAML, an independently revalidated decision, and this fixed policy.
"""
import copy
from pathlib import Path

import yaml

from traffic_rl.research.artifacts import sha256_file
from traffic_rl.research.pilot_residual_selector import validate_selected_outputs


PRIMARY_LEARNED_CONTROLLER = "schedule_residual_ddqn"
FINAL_SEEDS = (12, 13, 14, 15, 16)
FINAL_TIER = {"episodes": 12, "horizon_seconds": 3600, "eval_every": 4}
_SELECTION_TYPE = "haichau_residual_pilot_selection"


def _inside(root, supplied, label):
    root = Path(root).resolve()
    path = Path(supplied)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("%s must remain inside the project" % label)
    return path


def _load_yaml(path, label):
    try:
        value = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("%s is not valid YAML: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a YAML mapping" % label)
    return value


def _record(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def resolve_final_residual_config(root, selector_spec, selected_config, seed,
                                  validation_runner=None):
    """Return a final-only resolved config and compact selection binding.

    Validation recomputes the pilot decision.  The held-out test split is
    forbidden at this stage and the only permitted final run differences are
    confirmatory seed, final tier, and the immutable release binding.
    """
    root = Path(root).resolve()
    if seed not in FINAL_SEEDS:
        raise ValueError("final residual seed must be one of %s" % (FINAL_SEEDS,))
    selected_path = _inside(root, selected_config, "selected residual config")
    if not selected_path.is_file():
        raise ValueError("selected residual config is missing")
    decision = validate_selected_outputs(root, selector_spec, validation_runner)
    if (decision.get("decision_type") != _SELECTION_TYPE
            or decision.get("status") != "selected"
            or not isinstance(decision.get("winner"), dict)):
        raise ValueError("residual pilot selection is not eligible for final release")
    if decision.get("test_split_accessed") is not False:
        raise ValueError("residual pilot selection accessed the test split")
    record = decision.get("selected_config")
    actual = _record(root, selected_path)
    if not isinstance(record, dict) or record != actual:
        raise ValueError("selected config hash or path differs from revalidated decision")
    selected = _load_yaml(selected_path, "selected residual config")
    pilot = selected.get("pilot_selection")
    winner = decision["winner"]
    if (selected.get("controller_family") != PRIMARY_LEARNED_CONTROLLER
            or selected.get("mode") != "pilot"
            or selected.get("learning_seed") != 11
            or not isinstance(pilot, dict)
            or pilot.get("decision_type") != _SELECTION_TYPE
            or pilot.get("selected_checkpoint") != winner.get("checkpoint")
            or pilot.get("training_step") != winner.get("training_step")
            or pilot.get("test_split_accessed") is not False):
        raise ValueError("selected residual config does not bind the selected pilot")
    binding = {
        "schema_version": 1,
        "decision_type": _SELECTION_TYPE,
        "controller_family": PRIMARY_LEARNED_CONTROLLER,
        "selected_config": actual,
        "selected_checkpoint": winner["checkpoint"],
        "training_step": winner["training_step"],
        "checkpoint_artifacts": copy.deepcopy(winner.get("checkpoint_artifacts")),
        "test_split_accessed": False,
    }
    config = copy.deepcopy(selected)
    config.update({"mode": "final", "learning_seed": seed,
                   "run": copy.deepcopy(FINAL_TIER),
                   "final_release": {"selection": copy.deepcopy(binding)}})
    return config, binding
