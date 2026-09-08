from scripts import freeze_haichau_protocol as freeze
from scripts import prepare_haichau_release_inputs as prepare
from scripts import verify_haichau_thesis as verifier


def test_release_components_share_the_v3_controller_and_confirmation_seeds():
    expected_controllers = (
        "tuned_fixed", "max_pressure", "hysteretic_mp",
        "neighbor_phase_ddqn")
    expected_seeds = (12, 13, 14, 15, 16)

    assert prepare.LEARNING_CONTROLLERS == ("neighbor_phase_ddqn",)
    assert freeze.LEARNING_CONTROLLERS == ("neighbor_phase_ddqn",)
    assert verifier.LEARNING_CONTROLLERS == ("neighbor_phase_ddqn",)
    assert prepare.CONTROLLERS == expected_controllers
    assert freeze.CONTROLLERS == expected_controllers
    assert verifier.REQUIRED_CONTROLLERS == expected_controllers
    assert prepare.SEEDS == expected_seeds
    assert freeze.LEARNING_SEEDS == expected_seeds
    assert verifier.REQUIRED_SEEDS == expected_seeds


def test_pilot_seed_is_excluded_from_every_release_seed_constant():
    assert 11 not in prepare.SEEDS
    assert 11 not in freeze.LEARNING_SEEDS
    assert 11 not in verifier.REQUIRED_SEEDS
