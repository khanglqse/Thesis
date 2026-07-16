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


def test_intersection_block_lane_ordering_and_phases():
    rn, enc, net, weights = export.load_bundle(AREA, CKPT, count_norm=5.0, state_mode="basic")
    inter_id = export.pick_intersection(rn)
    blk = export.intersection_block(rn, enc, inter_id)
    # lane order must match the encoder's, so obs slots line up with training
    assert blk["incoming_lanes"] == rn.incoming_lanes(inter_id)
    assert blk["outgoing_lanes"] == rn.outgoing_lanes(inter_id)
    assert blk["num_greens"] == len(rn.green_phases(inter_id))
    assert blk["num_greens"] >= 3
    inset = set(blk["incoming_lanes"])
    outset = set(blk["outgoing_lanes"])
    for ph in blk["green_phases"]:
        assert ph["movements"], "green phase with no movements"
        for mv in ph["movements"]:
            assert set(mv["in_lanes"]) <= inset
            assert set(mv["out_lanes"]) <= outset
            assert mv["turn"] in ("go_straight", "turn_left", "turn_right", "turn_u")
    # geometry: one approach entry per road touching the intersection
    assert len(blk["geometry"]["approaches"]) == len(rn._by_id[inter_id]["roads"])
    for ap in blk["geometry"]["approaches"]:
        assert ap["role"] in ("in", "out")
        assert 0.0 <= ap["angle_deg"] < 360.0


def test_encoder_parity_samples_are_self_consistent():
    """Guards the JS Encoder + count_norm seam: rebuilds each sample's combined
    lane_counts dict and asserts the real ObservationEncoder reproduces the
    stored obs vector exactly (these are the samples the JS parity test also
    consumes, so this pins the Python side of that contract)."""
    rn, enc, net, weights = export.load_bundle(AREA, CKPT, count_norm=5.0, state_mode="basic")
    inter_id = export.pick_intersection(rn)
    samples = export.encoder_parity_samples(rn, enc, inter_id, n=16, seed=2)
    assert len(samples) == 16
    for s in samples:
        lane_counts = dict(s["inCounts"])
        lane_counts.update(s["outCounts"])
        obs = enc.encode(inter_id, lane_counts, s["greenIdx"])
        assert len(obs) == enc.obs_dim
        assert np.allclose(obs, s["obs"], atol=1e-6)


def test_compass_buckets():
    assert export.compass_vi(0.0) == "Đông"
    assert export.compass_vi(90.0) == "Bắc"
    assert export.compass_vi(180.0) == "Tây"
    assert export.compass_vi(270.0) == "Nam"
