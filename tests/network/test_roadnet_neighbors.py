import os

from traffic_rl.network.roadnet import RoadNet

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_upstream_neighbors_on_haichau():
    rn = RoadNet.load(
        os.path.join(ROOT, "datasets/haichau_network_v2/roadnet.json")
    )
    sig = set(rn.signalized_ids())
    assert len(sig) == 53                       # sanity: the evaluated network
    with_nbr = 0
    for i in sig:
        nbrs = rn.upstream_neighbors(i)
        for n in nbrs:
            assert n in sig and n != i          # neighbours are signalized, not self
        assert len(nbrs) == len(set(nbrs))      # deduped
        if nbrs:
            with_nbr += 1
    # an arterial network is connected: most signals have >=1 upstream neighbour
    assert with_nbr >= len(sig) // 2
