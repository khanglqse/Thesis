from traffic_rl.eval.agreement import AgreementLogger


def test_agreement_counts():
    lg = AgreementLogger()
    lg.record({"A": 0, "B": 1}, {"A": 0, "B": 0})   # A agrees, B differs
    lg.record({"A": 1, "B": 1}, {"A": 1, "B": 1})   # both agree
    s = lg.summary()
    assert s["n_decisions"] == 2
    assert s["n_pairs"] == 4 and s["agree"] == 3
    assert abs(s["agree_rate"] - 0.75) < 1e-9
    assert s["per_agent"]["B"] == 0.5
    assert s["per_agent"]["A"] == 1.0


def test_empty_summary_safe():
    s = AgreementLogger().summary()
    assert s["n_pairs"] == 0 and s["agree_rate"] == 0.0


def test_missing_agent_in_mp_is_skipped():
    lg = AgreementLogger()
    lg.record({"A": 0, "B": 0}, {"A": 0})           # B has no MP action -> skipped
    s = lg.summary()
    assert s["n_pairs"] == 1 and "B" not in s["per_agent"]
