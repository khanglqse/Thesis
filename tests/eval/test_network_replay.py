from traffic_rl.eval.network_replay import NetworkReplayObserver


def test_replay_observer_records_zero_and_five_second_node_frames():
    observer = NetworkReplayObserver(
        ["A", "B"], {"A": ["a0"], "B": ["b0", "b1"]},
        sample_seconds=5)
    observer.reset({"a0": 1, "b0": 2, "b1": 3}, {"A": 0, "B": 1})
    observer.observe(1, {"a0": 9}, {"A": 0, "B": 1})
    observer.observe(5, {"a0": 4, "b0": 1}, {"A": 1, "B": 2})

    replay = observer.finalize({"arrived": 7, "running": 2})

    assert [frame["t"] for frame in replay["frames"]] == [0, 5]
    assert replay["frames"][0]["nodes"]["B"]["queue"] == 5.0
    assert replay["frames"][1]["nodes"]["A"] == {"queue": 4.0, "phase": 1}
    assert replay["metrics"] == {"arrived": 7, "running": 2}
