"""HITS (Kleinberg 1998, cours L03-01), pondéré :

    a <- Aᵀ h ,  h <- A a ,  avec normalisation à chaque pas.

Le HITS du cours part d'une requête (ensemble racine puis ensemble de base) ;
ici on l'applique au graphe d'inclusion entier : les hubs attendus sont les
chargeurs (tag managers, SDK), les autorités les collecteurs.

Limite connue (effet TKC) : une communauté très dense capte toute la masse et
les autres composantes tombent à ~0, d'où la variante `hits_per_component`.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from tm.rank.pagerank import RankResult


def hits(A, tol=1e-10, max_iter=1000):
  """(hubs, autorités), scores normalisés en somme = 1 (comme networkx)."""
  A = sp.csr_matrix(A, dtype=np.float64)
  n = A.shape[0]
  if n == 0:
    return RankResult(np.zeros(0), 0, True), RankResult(np.zeros(0), 0, True)
  if A.nnz == 0:                        # aucun lien : scores nuls par convention
    return RankResult(np.zeros(n), 0, True), RankResult(np.zeros(n), 0, True)

  AT = A.T.tocsr()
  h = np.full(n, 1.0 / np.sqrt(n))
  a = np.zeros(n)
  converged = False
  for k in range(1, max_iter + 1):
    a_new = AT @ h
    a_new /= np.linalg.norm(a_new)
    h_new = A @ a_new
    h_new /= np.linalg.norm(h_new)
    err = float(np.abs(a_new - a).sum() + np.abs(h_new - h).sum())
    a, h = a_new, h_new
    if err < tol:
      converged = True
      break
  return RankResult(h / h.sum(), k, converged), RankResult(a / a.sum(), k, converged)


def hits_per_component(A, **kw):
  """HITS calculé dans chaque composante faiblement connexe séparément
  (scores normalisés à l'intérieur de la composante). Corrige l'effet TKC."""
  A = sp.csr_matrix(A, dtype=np.float64)
  _, labels = connected_components(A, directed=True, connection="weak")
  hub = np.zeros(A.shape[0])
  auth = np.zeros(A.shape[0])
  for c in np.unique(labels):
    idx = np.flatnonzero(labels == c)
    if len(idx) < 2:
      continue
    h, a = hits(A[idx][:, idx], **kw)
    hub[idx], auth[idx] = h.scores, a.scores
  return hub, auth, labels
