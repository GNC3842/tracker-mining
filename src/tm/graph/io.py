"""Chargement des graphes produits par tm.graph.build."""
from pathlib import Path

import pyarrow.parquet as pq
import scipy.sparse as sp


def load_graph(interim, name="g_inc"):
  """(matrice CSR, liste des domaines dans l'ordre des indices)."""
  interim = Path(interim)
  M = sp.load_npz(interim / f"{name}.npz").tocsr()
  doms = pq.read_table(interim / "nodes.parquet", columns=["domain"]).column("domain").to_pylist()
  assert M.shape[0] == len(doms), "nodes.parquet et la matrice ne correspondent pas"
  return M, doms
