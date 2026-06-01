from traffic_rl.report import replay


def test_truncate_keeps_first_n_lines(tmp_path):
    src = tmp_path / "big.txt"
    src.write_text("".join("step %d\n" % i for i in range(1000)))
    dst = tmp_path / "demo.txt"
    n = replay.truncate_replay(str(src), str(dst), 120)
    assert n == 120
    lines = dst.read_text().splitlines()
    assert len(lines) == 120
    assert lines[0] == "step 0"
    assert lines[-1] == "step 119"


def test_truncate_zero_steps(tmp_path):
    src = tmp_path / "big.txt"
    src.write_text("step 0\nstep 1\n")
    dst = tmp_path / "empty.txt"
    assert replay.truncate_replay(str(src), str(dst), 0) == 0
    assert dst.read_text() == ""


def test_truncate_shorter_than_n(tmp_path):
    src = tmp_path / "small.txt"
    src.write_text("a\nb\nc\n")
    dst = tmp_path / "demo.txt"
    n = replay.truncate_replay(str(src), str(dst), 120)
    assert n == 3
    assert dst.read_text() == "a\nb\nc\n"
