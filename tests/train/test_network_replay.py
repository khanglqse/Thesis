import numpy as np

from traffic_rl.train.network_replay import NetworkReplayBuffer


def _features(value=0.0):
    return np.full((3, 4), value, np.float32)


def test_replay_reports_regime_coverage():
    replay = NetworkReplayBuffer(10, max_green=3, feature_dim=4, seed=1)
    mask = np.array([True, True, False])
    replay.add(_features(), 0, -1, _features(1), False, mask, "normal")
    replay.add(_features(), 1, -2, _features(2), False, mask, "pm_peak")

    assert replay.coverage() == {"normal": 1, "pm_peak": 1}


def test_replay_overwrite_updates_coverage_and_sample_shapes():
    replay = NetworkReplayBuffer(2, max_green=3, feature_dim=4, seed=1)
    mask = np.array([True, True, False])
    replay.add(_features(), 0, -1, _features(1), False, mask, "normal")
    replay.add(_features(), 1, -2, _features(2), False, mask, "am_peak")
    replay.add(_features(), 1, -3, _features(3), True, mask, "pm_peak")
    batch = replay.sample(2)

    assert replay.coverage() == {"am_peak": 1, "pm_peak": 1}
    assert batch["features"].shape == (2, 3, 4)
    assert batch["next_masks"].shape == (2, 3)
    assert batch["case_regimes"].shape == (2,)
    assert len(replay) == 2

