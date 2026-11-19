import math

import networkx as nx
import numpy as np
import pytest
import scipy.sparse as sp

from tm.rank.pagerank import pagerank


def random_graph(n=1000, p=0.005, seed=0, dangling_frac=0.2):
    """Graphe orienté pondéré aléatoire, avec une part imposée de nœuds pendants."""
    rng = np.random.default_rng(seed)
    M = (rng.random((n, n)) < p).astype(float) * rng.integers(1, 10, size=(n, n))
    np.fill_diagonal(M, 0)
    M[rng.choice(n, int(dangling_frac * n), replace=False)] = 0      # lignes nulles = pendants
    return sp.csr_matrix(M)


def nx_pagerank(A, d, personalization=None):
    G = nx.from_scipy_sparse_array(A, create_using=nx.DiGraph, edge_attribute="weight")
    G.add_nodes_from(range(A.shape[0]))
    pers = None if personalization is None else dict(enumerate(personalization))
    pr = nx.pagerank(G, alpha=d, weight="weight", tol=1e-13, max_iter=10_000, personalization=pers)
    return np.array([pr[i] for i in range(A.shape[0])])


@pytest.mark.parametrize("d", [0.5, 0.85, 0.95])
def test_matches_networkx(d):
    A = random_graph()
    res = pagerank(A, d=d, tol=1e-12)
    assert res.converged
    assert np.abs(res.scores - nx_pagerank(A, d)).max() < 1e-9


def test_personalization_matches_networkx():
    A = random_graph(n=300, p=0.02, seed=1)
    v = np.random.default_rng(2).random(300)
    res = pagerank(A, d=0.85, tol=1e-12, personalization=v)
    assert np.abs(res.scores - nx_pagerank(A, 0.85, v / v.sum())).max() < 1e-9


def test_scores_are_a_distribution():
    res = pagerank(random_graph(seed=3))
    assert res.scores.min() >= 0 and res.scores.sum() == pytest.approx(1.0, abs=1e-12)


def test_naive_course_formula_loses_mass_on_dangling_nodes():
    """Sans redistribution de la masse des pendants, la somme des scores est < 1."""
    A = sp.csr_matrix(np.array([[0, 1, 0], [0, 0, 1], [0, 0, 0]], dtype=float))   # 2 = pendant
    n, d = 3, 0.85
    R = np.full(n, 1 / n)
    out = np.asarray(A.sum(axis=1)).ravel()
    contrib = np.where(out > 0, R / np.where(out > 0, out, 1), 0)
    R_naive = (1 - d) / n + d * (A.T @ contrib)
    assert R_naive.sum() == pytest.approx(1 - d / 3)        # la masse du pendant est perdue
    assert pagerank(A, d=d).scores.sum() == pytest.approx(1.0)


def test_iteration_count_stays_small():
    """Contraction de rapport d : n_iter <= 1 + ln(tol/2)/ln(d)."""
    d, tol = 0.85, 1e-10
    res = pagerank(random_graph(seed=4), d=d, tol=tol)
    assert res.n_iter <= 1 + math.ceil(math.log(tol / 2) / math.log(d))


def test_edge_cases():
    assert pagerank(sp.csr_matrix((0, 0))).scores.shape == (0,)
    assert pagerank(sp.csr_matrix((1, 1))).scores.tolist() == [1.0]
    empty = pagerank(sp.csr_matrix((4, 4)))                 # tous pendants -> uniforme
    assert np.allclose(empty.scores, 0.25)
    assert np.allclose(pagerank(random_graph(n=50, p=0.1), d=0.0).scores, 1 / 50)   # d = 0 -> v


def test_known_small_graph():
    """Cycle 0 -> 1 -> 2 -> 0 : par symétrie, R = (1/3, 1/3, 1/3)."""
    A = sp.csr_matrix(np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float))
    assert np.allclose(pagerank(A).scores, 1 / 3)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        pagerank(sp.csr_matrix(np.array([[0, -1], [0, 0]], dtype=float)))
    with pytest.raises(ValueError):
        pagerank(sp.csr_matrix((2, 3)))
    with pytest.raises(ValueError):
        pagerank(sp.csr_matrix((2, 2)), d=1.0)
