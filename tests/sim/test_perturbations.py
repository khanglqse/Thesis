from tests.conftest import FakeEngine
from traffic_rl.sim.perturbations import PerturbedEngine


def test_passthrough_when_off():
    inner = FakeEngine(vehicle_counts={"l": 10}, waiting_counts={"l": 4})
    pe = PerturbedEngine(inner, noise_std=0.0)
    assert pe.lane_vehicle_counts() == {"l": 10}
    assert pe.lane_waiting_counts() == {"l": 4}


def test_noise_is_seeded_and_reproducible():
    a = PerturbedEngine(FakeEngine(waiting_counts={"l": 20}), noise_std=0.3, seed=1)
    b = PerturbedEngine(FakeEngine(waiting_counts={"l": 20}), noise_std=0.3, seed=1)
    assert a.lane_waiting_counts() == b.lane_waiting_counts()


def test_noise_perturbs_and_stays_nonnegative():
    pe = PerturbedEngine(FakeEngine(waiting_counts={"l": 20}), noise_std=0.8, seed=2)
    vals = [pe.lane_waiting_counts()["l"] for _ in range(6)]
    assert any(v != 20 for v in vals)          # noise actually changes the count
    assert all(v >= 0 for v in vals)           # never negative


def test_dropout_zeros_some_lanes():
    pe = PerturbedEngine(FakeEngine(waiting_counts={"a": 5, "b": 5, "c": 5, "d": 5}),
                         noise_std=1.0, noise_kind="dropout", seed=0)
    assert pe.lane_waiting_counts() == {"a": 0, "b": 0, "c": 0, "d": 0}   # p=1 -> all dropped


def test_delegates_lifecycle():
    inner = FakeEngine(waiting_counts={"l": 1})
    pe = PerturbedEngine(inner, noise_std=0.0)
    pe.reset(); pe.step(); pe.set_tl_phase("A", 2)
    assert ("reset",) in inner.calls and ("step",) in inner.calls
    assert inner.phase["A"] == 2


def test_incident_forces_block_phase_in_window():
    inner = FakeEngine()
    pe = PerturbedEngine(inner, incident=("X", 2, 5, 0))
    pe.set_tl_phase("X", 3); assert inner.phase["X"] == 3      # before window: unaffected
    pe.step(); pe.step()                                        # step_count -> 2 (in [2,5))
    pe.set_tl_phase("X", 3); assert inner.phase["X"] == 0      # forced to block phase 0
    pe.set_tl_phase("Y", 3); assert inner.phase["Y"] == 3      # other intersection unaffected
