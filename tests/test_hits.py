import networkx as nx
import numpy as np
import pytest
import scipy.sparse as sp

from tm.rank.hits import hits, hits_per_component


def test_matches_networkx():
    rng = np.random.default_rng(0)
    n = 400
    M = (rng.random((n, n)) < 0.03).astype(float) * rng.integers(1, 5, size=(n, n))
    np.fill_diagonal(M, 0)
    A = sp.csr_matrix(M)
    h, a = hits(A, tol=1e-13, max_iter=10_000)
    assert h.converged
    G = nx.from_scipy_sparse_array(A, create_using=nx.DiGraph, edge_attribute="weight")
    nh, na = nx.hits(G, max_iter=10_000, tol=1e-13)
    assert np.abs(h.scores - np.array([nh[i] for i in range(n)])).max() < 1e-8
    assert np.abs(a.scores - np.array([na[i] for i in range(n)])).max() < 1e-8


def test_star_hub_and_authorities():
    """0 -> 1..4 : 0 est le seul hub, 1..4 sont des autorités égales."""
    M = np.zeros((5, 5))
    M[0, 1:] = 1
    h, a = hits(sp.csr_matrix(M))
    assert h.scores == pytest.approx([1, 0, 0, 0, 0])
    assert a.scores == pytest.approx([0, .25, .25, .25, .25])


def test_empty_graph_gives_zero_scores():
    h, a = hits(sp.csr_matrix((3, 3)))
    assert h.scores.tolist() == [0, 0, 0] and a.scores.tolist() == [0, 0, 0]


def test_tkc_effect_and_per_component_fix():
    """Composante dense (K4) + étoile isolée : HITS global écrase l'étoile (effet TKC),
    le calcul par composante lui redonne une masse de 1."""
    M = np.zeros((9, 9))
    for i in range(4):
        for j in range(4):
            if i != j:
                M[i, j] = 1                      # K4 orienté complet (nœuds 0-3)
    M[4, 5:] = 1                                 # étoile 4 -> 5..8
    _, a = hits(sp.csr_matrix(M))
    assert a.scores[5:].sum() < 1e-6             # l'étoile ne reçoit rien
    _, auth, _ = hits_per_component(sp.csr_matrix(M))
    assert auth[5:].sum() == pytest.approx(1.0) and auth[:4].sum() == pytest.approx(1.0)


def test_collector_can_get_zero_authority():
    """gtm -> ga (3), gtm -> fb (2), ga -> dc (2), fb -> dc (1) : l'autorité du
    collecteur dc tombe à 0, alors que c'est lui qui reçoit les données."""
    A = sp.csr_matrix(np.array([[0, 3, 2, 0], [0, 0, 0, 2], [0, 0, 0, 1], [0, 0, 0, 0]],
                               dtype=float))
    h, a = hits(A)
    assert a.scores == pytest.approx([0, 0.6, 0.4, 0], abs=1e-9)
    assert h.scores == pytest.approx([1, 0, 0, 0], abs=1e-9)
