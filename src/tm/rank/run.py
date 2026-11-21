"""E6 — Classement des domaines du graphe d'inclusion G_inc.

Sorties : interim/ranks.parquet (un score par domaine) et results/rank_summary.json
(convergence, top 20, corrélations de Spearman).

Deux PageRank sont calculés :
- "uniforme" (formule du cours, téléportation 1/N) : un nœud qui n'a qu'une
  arête sortante transmet toute sa masse, que l'arête vienne de 1 site ou de
  1 000 (voir tests/test_rank_run.py) ;
- "ancré sur les sites" (mesure principale) : téléportation proportionnelle à
  fp_loads, c.-à-d. aux tiers chargés directement par les sites.

Question du projet : PageRank apporte-t-il plus que le simple comptage de sites ?
-> corrélation de Spearman entre PageRank et prévalence.

Usage : python -m tm.rank.run [--config config.yaml]
"""
import argparse

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.stats import spearmanr

from tm.config import ensure_dir, load_config, repo_path
from tm.graph.io import load_graph
from tm.io import write_result
from tm.rank.hits import hits
from tm.rank.pagerank import pagerank


def rho(x, y):
  """Spearman, ou None si une des deux séries est constante (corrélation indéfinie)."""
  if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
    return None
  return round(float(spearmanr(x, y).statistic), 4)


def site_teleport(fp_loads):
  """Vecteur de téléportation proportionnel au nombre de sites qui chargent
  directement chaque domaine (None si aucun chargement direct)."""
  v = np.asarray(fp_loads, dtype=np.float64)
  return v if v.sum() > 0 else None


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("--config", default=None)
  ap.add_argument("--interim", default=None)
  ap.add_argument("--results", default=None)
  ap.add_argument("--top", type=int, default=20)
  a = ap.parse_args(argv)
  cfg = load_config(a.config)
  interim = ensure_dir(a.interim or cfg["paths"]["interim"])
  rc = cfg["rank"]

  A, doms = load_graph(interim, "g_inc")
  nodes = pq.read_table(interim / "nodes.parquet").to_pandas()
  pr_u = pagerank(A, d=rc["damping"], tol=rc["tol"], max_iter=rc["max_iter"])
  v = site_teleport(nodes["fp_loads"].values)
  pr_s = pagerank(A, d=rc["damping"], tol=rc["tol"], max_iter=rc["max_iter"], personalization=v)
  hub, auth = hits(A, tol=rc["tol"], max_iter=rc["max_iter"])

  in_w = np.asarray(A.sum(axis=0)).ravel()
  out_w = np.asarray(A.sum(axis=1)).ravel()
  in_deg = np.diff(A.tocsc().indptr)
  out_deg = np.diff(A.indptr)
  df = nodes.assign(pagerank_site=pr_s.scores, pagerank_uniform=pr_u.scores,
                    hub=hub.scores, authority=auth.scores,
                    in_w=in_w, out_w=out_w, in_deg=in_deg, out_deg=out_deg)
  pq.write_table(pa.Table.from_pandas(df, preserve_index=False), interim / "ranks.parquet")

  # Corrélations et top-N sur les nœuds qui ont au moins une arête tiers -> tiers.
  linked = df[(in_deg + out_deg) > 0]

  def top(col):
    return linked.nlargest(a.top, col)[["domain", col, "n_sites"]].to_dict("records")

  summary = {
    "n_nodes": len(df), "n_nodes_with_tp_edge": len(linked),
    "pagerank_site": {"iterations": pr_s.n_iter, "converged": pr_s.converged,
                      "teleport": "fp_loads" if v is not None else "uniform"},
    "pagerank_uniform": {"iterations": pr_u.n_iter, "converged": pr_u.converged},
    "hits": {"iterations": hub.n_iter, "converged": hub.converged},
    "spearman": {
      "pagerank_site_vs_prevalence": rho(linked.pagerank_site.values, linked.n_sites.values),
      "pagerank_uniform_vs_prevalence": rho(linked.pagerank_uniform.values, linked.n_sites.values),
      "authority_vs_in_weight": rho(linked.authority.values, linked.in_w.values),
      "hub_vs_out_weight": rho(linked.hub.values, linked.out_w.values),
    },
    "top_pagerank_site": top("pagerank_site"), "top_pagerank_uniform": top("pagerank_uniform"),
    "top_authority": top("authority"), "top_hub": top("hub"),
  }
  write_result(repo_path(a.results or cfg["paths"]["results"]) / "rank_summary.json", summary, cfg)
  print(f"PageRank sites : {pr_s.n_iter} it. · uniforme : {pr_u.n_iter} it. · HITS : {hub.n_iter} it.")
  print("Spearman :", summary["spearman"])
  print(linked.nlargest(min(10, len(linked)), "pagerank_site")
        [["domain", "pagerank_site", "authority", "hub", "n_sites"]].to_string(index=False))


if __name__ == "__main__":
  main()
