import numpy as np
import pytest

from tm.graph.build import build_bipartite, build_cooccurrence, build_inclusion
from tm.parse.resolve import FP_NODE

# s1:{a,b}  s2:{a,b,c}  s3:{c}   ->  |S_a| = |S_b| = |S_c| = 2
SD = [{"origin": "s1", "domain": "a"}, {"origin": "s1", "domain": "b"},
      {"origin": "s2", "domain": "a"}, {"origin": "s2", "domain": "b"}, {"origin": "s2", "domain": "c"},
      {"origin": "s3", "domain": "c"}, {"origin": "s3", "domain": "c"}]      # doublon ignoré


def test_bipartite():
    B, sites, doms = build_bipartite(SD)
    assert sites == ["s1", "s2", "s3"] and doms == ["a", "b", "c"]
    assert B.toarray().tolist() == [[1, 1, 0], [1, 1, 1], [0, 0, 1]]


def test_jaccard_values_and_thresholds():
    B, _, _ = build_bipartite(SD)
    # J(a,b) = 2/(2+2-2) = 1 ; J(a,c) = J(b,c) = 1/(2+2-1) = 1/3
    G = build_cooccurrence(B, jaccard_min=0.0, co_min=1).toarray()
    assert G[0, 1] == pytest.approx(1.0) and G[0, 2] == pytest.approx(1 / 3)
    assert np.allclose(G, G.T) and np.all(np.diag(G) == 0)
    G2 = build_cooccurrence(B, jaccard_min=0.0, co_min=2).toarray()     # co_min filtre (a,c),(b,c)
    assert G2[0, 1] == pytest.approx(1.0) and G2[0, 2] == 0
    G3 = build_cooccurrence(B, jaccard_min=0.5, co_min=1).toarray()     # J < 0.5 filtré
    assert G3[0, 2] == 0


def test_inclusion_fp_and_dropped():
    doms = ["a", "b", "c"]
    edges = [{"parent": FP_NODE, "child": "a", "n_sites": 5},
             {"parent": "a", "child": "b", "n_sites": 3},
             {"parent": "b", "child": "c", "n_sites": 1},
             {"parent": "zz", "child": "c", "n_sites": 2},
             {"parent": "a", "child": "zz", "n_sites": 2}]
    A, fp_loads, dropped = build_inclusion(edges, doms)
    assert A.toarray().tolist() == [[0, 3, 0], [0, 0, 1], [0, 0, 0]]
    assert fp_loads.tolist() == [5, 0, 0]
    assert dropped == {"parent_not_in_V": 1, "child_not_in_V": 1}


def test_implicit_share():
    from tm.graph.build import implicit_share
    sd = [{"origin": "s1", "domain": "a", "min_depth": 1},
          {"origin": "s2", "domain": "a", "min_depth": 2},
          {"origin": "s3", "domain": "a", "min_depth": 3},
          {"origin": "s1", "domain": "b", "min_depth": 1}]
    assert implicit_share(sd, ["a", "b", "c"]).tolist() == pytest.approx([2 / 3, 0.0, 0.0])
