import numpy as np
import pytest

export = pytest.importorskip("scripts.export_sandbox_model", reason="host-only export tool")


AREA = "haichau_rush"
CKPT = "results/haichau_rush/dqn_haichau_rush.npz"


def test_forward_mirror_matches_shareddqn():
    rn, enc, net, weights = export.load_bundle(AREA, CKPT, count_norm=5.0, state_mode="basic")
    rng = np.random.RandomState(0)
    for _ in range(16):
        obs = (rng.rand(enc.obs_dim) * 3.0).astype(np.float32)
        ref = net.q_values(obs)[0]
        got = export.forward_mirror(weights, obs.tolist())
        assert np.allclose(got, ref, atol=1e-5), (got[:4], ref[:4])


def test_parity_samples_are_self_consistent():
    rn, enc, net, weights = export.load_bundle(AREA, CKPT, count_norm=5.0, state_mode="basic")
    samples = export.parity_samples(net, enc.obs_dim, enc.max_green, n=8, seed=1)
    assert len(samples) == 8
    for s in samples:
        assert len(s["obs"]) == enc.obs_dim
        assert len(s["q"]) == enc.max_green
        got = export.forward_mirror(weights, s["obs"])
        assert np.allclose(got, s["q"], atol=1e-5)
        assert int(np.argmax(s["q"])) == s["greedy"]
