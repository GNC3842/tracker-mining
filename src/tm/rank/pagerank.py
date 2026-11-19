"""PageRank pondéré, écrit à partir de la formule du cours (L03-01) :

    R(A) = (1 - d)/N + d * somme_{B->A} R(B) / do(B)

Deux adaptations :
- poids : do(B) devient le poids sortant total de B, et B donne à A la part
  A[B, A] / poids_sortant(B) ;
- nœuds pendants (aucune arête sortante) : leur masse serait perdue à chaque
  itération (somme R < 1). On la redistribue sur le vecteur de téléportation v
  (uniforme par défaut), comme si un nœud pendant pointait vers tout le monde.
  Dans G_inc les pendants sont les collecteurs, donc ça compte.

L'itération est une contraction de rapport d : elle converge vers un point fixe
unique. On s'arrête quand ||R_k - R_{k-1}||_1 < tol.
"""
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp


@dataclass
class RankResult:
  scores: np.ndarray
  n_iter: int
  converged: bool


def transition_matrix(A):
  """P stochastique en lignes (lignes nulles pour les pendants) + masque des pendants."""
  A = sp.csr_matrix(A, dtype=np.float64)
  if (A.data < 0).any():
    raise ValueError("poids négatifs interdits")
  w_out = np.asarray(A.sum(axis=1)).ravel()
  dangling = w_out == 0
  inv = np.zeros_like(w_out)
  inv[~dangling] = 1.0 / w_out[~dangling]
  return sp.diags(inv) @ A, dangling


def pagerank(A, d=0.85, tol=1e-10, max_iter=1000, personalization=None):
  """A[u, v] = poids de l'arête u -> v. Les scores renvoyés somment à 1."""
  n = A.shape[0]
  if A.shape[0] != A.shape[1]:
    raise ValueError("matrice d'adjacence non carrée")
  if not 0 <= d < 1:
    raise ValueError("d doit être dans [0, 1)")
  if n == 0:
    return RankResult(np.zeros(0), 0, True)

  if personalization is None:
    v = np.full(n, 1.0 / n)
  else:
    v = np.asarray(personalization, dtype=np.float64)
    if v.shape != (n,) or (v < 0).any() or v.sum() == 0:
      raise ValueError("personalization : vecteur positif de taille N, non nul")
    v = v / v.sum()

  P, dangling = transition_matrix(A)
  PT = P.T.tocsr()
  R = v.copy()
  for k in range(1, max_iter + 1):
    R_new = (1 - d) * v + d * (PT @ R + R[dangling].sum() * v)
    err = float(np.abs(R_new - R).sum())
    R = R_new
    if err < tol:
      return RankResult(R / R.sum(), k, True)
  return RankResult(R / R.sum(), max_iter, False)
