"""Modèle de téléportation de PageRank (uniforme vs ancré sur les sites)."""
import numpy as np
import pytest
import scipy.sparse as sp

from tm.rank.pagerank import pagerank
from tm.rank.run import rho, site_teleport

# 0 = X (chargé directement par 1 000 sites) -> 2 = C, sur 1 000 sites
# 1 = Y (chargé directement par 1 site)      -> 3 = D, sur 1 site
A = sp.csr_matrix(np.array([[0, 0, 1000, 0], [0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
                           dtype=float))
FP_LOADS = np.array([1000, 1, 0, 0])


def test_uniform_teleport_ignores_site_counts():
    """Défaut du PageRank uniforme : chaque ligne est normalisée, donc un nœud avec
    une seule arête sortante transmet tout, que l'arête vienne de 1 ou 1 000 sites."""
    r = pagerank(A).scores
    assert r[2] == pytest.approx(r[3])          # C (1 000 sites) == D (1 site) !
    assert r[0] == pytest.approx(r[1])


def test_site_anchored_teleport_restores_site_counts():
    r = pagerank(A, personalization=site_teleport(FP_LOADS)).scores
    assert r[2] > 100 * r[3] and r[0] > 100 * r[1]
    assert r.sum() == pytest.approx(1.0)


def test_site_teleport_falls_back_when_no_direct_loads():
    assert site_teleport(np.zeros(4)) is None


def test_rho_is_none_when_a_series_is_constant():
    assert rho(np.arange(5.0), 2 * np.arange(5.0)) == 1.0
    assert rho(np.ones(5), np.arange(5.0)) is None
