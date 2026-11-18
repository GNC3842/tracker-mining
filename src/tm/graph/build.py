"""E5 — Construit les graphes au niveau domaine.

Nœuds : les domaines tiers vus sur au moins un site exploitable, triés par ordre
alphabétique (l'indice d'un domaine est sa position dans cette liste).

G_inc (orienté)    A[u, v] = nb de sites où le domaine u a chargé le domaine v.
                   Les chargements par le site lui-même ne sont pas des arêtes
                   (le premier parti n'est pas un nœud) : on les garde dans la
                   colonne fp_loads de nodes.parquet.
B (biparti)        B[s, v] = 1 si le domaine v apparaît sur le site s.
G_co (non orienté) C = Bᵀ B donne |S_u ∩ S_v| ; arête si Jaccard >= jaccard_min
                   et |S_u ∩ S_v| >= co_min ; poids = Jaccard.

Sorties (paths.interim) : nodes.parquet, sites_index.parquet, g_inc.npz,
g_co.npz, b_site_domain.npz ; results/graph_summary.json.

Usage : python -m tm.graph.build [--config config.yaml]
"""
import argparse

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from tm.config import ensure_dir, load_config, repo_path
from tm.io import write_result
from tm.parse.resolve import FP_NODE


def build_bipartite(site_domain):
  """Matrice sites x domaines, + les deux listes d'étiquettes."""
  sites = sorted({r["origin"] for r in site_domain})
  doms = sorted({r["domain"] for r in site_domain})
  si = {s: i for i, s in enumerate(sites)}
  di = {d: i for i, d in enumerate(doms)}
  pairs = {(si[r["origin"]], di[r["domain"]]) for r in site_domain}
  rows, cols = zip(*pairs) if pairs else ((), ())
  B = sp.csr_matrix((np.ones(len(rows), dtype=np.int64), (rows, cols)),
                    shape=(len(sites), len(doms)))
  return B, sites, doms


def implicit_share(site_domain, doms):
  """Part des sites où le domaine n'est présent qu'indirectement (profondeur >= 2).
  0 = toujours chargé par le site, 1 = toujours via un autre tiers. C'est la
  mesure simple à laquelle on compare PageRank."""
  di = {d: i for i, d in enumerate(doms)}
  total = np.zeros(len(doms))
  deep = np.zeros(len(doms))
  for r in site_domain:
    i = di[r["domain"]]
    total[i] += 1
    deep[i] += (r.get("min_depth") or 0) >= 2
  out = np.zeros(len(doms))
  np.divide(deep, total, out=out, where=total > 0)
  return out


def build_inclusion(edges, doms):
  """Matrice d'adjacence tiers -> tiers, + les chargements par le premier parti."""
  di = {d: i for i, d in enumerate(doms)}
  fp_loads = np.zeros(len(doms), dtype=np.int64)
  rows, cols, weights = [], [], []
  dropped = {"parent_not_in_V": 0, "child_not_in_V": 0}
  for e in edges:
    p, c, n = e["parent"], e["child"], e["n_sites"]
    if c not in di:
      dropped["child_not_in_V"] += 1
    elif p == FP_NODE:
      fp_loads[di[c]] += n
    elif p not in di:
      dropped["parent_not_in_V"] += 1
    else:
      rows.append(di[p])
      cols.append(di[c])
      weights.append(n)
  A = sp.csr_matrix((np.array(weights, dtype=np.float64), (rows, cols)),
                    shape=(len(doms), len(doms)))
  A.sum_duplicates()
  A.setdiag(0)              # pas de boucle sur soi-même
  A.eliminate_zeros()
  return A, fp_loads, dropped


def build_cooccurrence(B, jaccard_min, co_min):
  C = (B.T @ B).tocoo()
  size = np.asarray(B.sum(axis=0)).ravel().astype(np.float64)   # nb de sites par domaine
  off = C.row != C.col                                          # on jette la diagonale
  r, c, inter = C.row[off], C.col[off], C.data[off].astype(np.float64)
  jaccard = inter / (size[r] + size[c] - inter)
  keep = (jaccard >= jaccard_min) & (inter >= co_min)
  n = B.shape[1]
  return sp.csr_matrix((jaccard[keep], (r[keep], c[keep])), shape=(n, n))


def graph_stats(A, G):
  n = A.shape[0]
  out_deg = np.diff(A.indptr)
  in_deg = np.diff(A.tocsc().indptr)
  n_cc, labels = connected_components(G, directed=False)
  return {
    "n_nodes": n,
    "g_inc": {"n_edges": int(A.nnz),
              "nodes_with_tp_edge": int(((out_deg + in_deg) > 0).sum()),
              "max_in_degree": int(in_deg.max()) if n else 0,
              "max_out_degree": int(out_deg.max()) if n else 0,
              "n_collectors": int(((out_deg == 0) & (in_deg > 0)).sum())},
    "g_co": {"n_edges": int(G.nnz // 2),
             "mean_degree": float(np.diff(G.indptr).mean()) if n else 0,
             "n_cc": int(n_cc),
             "largest_cc": int(np.bincount(labels).max()) if n else 0},
  }


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("--config", default=None)
  ap.add_argument("--interim", default=None)
  ap.add_argument("--results", default=None)
  a = ap.parse_args(argv)
  cfg = load_config(a.config)
  interim = ensure_dir(a.interim or cfg["paths"]["interim"])
  gcfg = cfg["graph"]

  sd = pq.read_table(interim / "site_domain.parquet",
                     columns=["origin", "domain", "min_depth"]).to_pylist()
  edges = pq.read_table(interim / "edges_inc.parquet").to_pylist()
  B, sites, doms = build_bipartite(sd)
  A, fp_loads, dropped = build_inclusion(edges, doms)
  G = build_cooccurrence(B, gcfg["jaccard_min"], gcfg["co_min"])

  prevalence = np.asarray(B.sum(axis=0)).ravel()
  implicit = implicit_share(sd, doms)
  pq.write_table(pa.table({"idx": np.arange(len(doms)), "domain": doms,
                           "n_sites": prevalence.astype(np.int64), "fp_loads": fp_loads,
                           "implicit_share": implicit}),
                 interim / "nodes.parquet")
  pq.write_table(pa.table({"row": np.arange(len(sites)), "origin": sites}),
                 interim / "sites_index.parquet")
  sp.save_npz(interim / "g_inc.npz", A)
  sp.save_npz(interim / "g_co.npz", G)
  sp.save_npz(interim / "b_site_domain.npz", B)

  summary = {"n_sites": len(sites), **graph_stats(A, G), "dropped_edges": dropped,
             "single_site_domains": int((prevalence == 1).sum()),
             "mean_implicit_share": float(implicit.mean()) if len(doms) else None}
  write_result(repo_path(a.results or cfg["paths"]["results"]) / "graph_summary.json", summary, cfg)
  for k, v in summary.items():
    print(f"{k:16s} {v}")


if __name__ == "__main__":
  main()
