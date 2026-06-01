from traffic_rl.agents.random_agent import RandomController

def test_actions_are_valid_green_indices_and_seeded():
    c1 = RandomController(num_actions={"A": 2, "B": 3}, seed=42)
    c2 = RandomController(num_actions={"A": 2, "B": 3}, seed=42)
    ctx = {"observations": {}, "waiting_counts": {}, "action_masks": {}}
    seq1 = [c1.act(ctx) for _ in range(5)]
    seq2 = [c2.act(ctx) for _ in range(5)]
    assert seq1 == seq2                         # deterministic given seed
    for step in seq1:
        assert 0 <= step["A"] < 2 and 0 <= step["B"] < 3
