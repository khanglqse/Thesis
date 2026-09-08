from traffic_rl.train.case_sampler import BalancedCaseSampler


def _cases():
    return [
        {"case_id": "normal-1", "scenario": "normal"},
        {"case_id": "normal-2", "scenario": "normal"},
        {"case_id": "am-1", "scenario": "am_peak"},
        {"case_id": "am-2", "scenario": "am_peak"},
        {"case_id": "pm-1", "scenario": "pm_peak"},
        {"case_id": "pm-2", "scenario": "pm_peak"},
    ]


def test_sampler_balances_regimes_before_repeating():
    sampler = BalancedCaseSampler(_cases(), seed=7)
    seen = [sampler.next_case()["scenario"] for _ in range(3)]

    assert set(seen) == {"normal", "am_peak", "pm_peak"}


def test_sampler_is_deterministic_and_exhausts_regime_cases():
    first = BalancedCaseSampler(_cases(), seed=11)
    second = BalancedCaseSampler(_cases(), seed=11)
    ids_a = [first.next_case()["case_id"] for _ in range(6)]
    ids_b = [second.next_case()["case_id"] for _ in range(6)]

    assert ids_a == ids_b
    assert set(ids_a) == {case["case_id"] for case in _cases()}

