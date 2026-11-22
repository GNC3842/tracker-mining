"""E0 — Analyse du crawl pilote et verdict GO / NO-GO sur chaque critère.

Usage :
  python -m tm.feasibility.analyze data/raw/pilot/crawl_pilot.jsonl \
      --tracker-radar data/ref/tracker_radar_index.json \
      --easyprivacy data/ref/easyprivacy.txt --outdir results/pilot

Sorties : report.md, metrics.json, inclusion_edges.csv, annotation_sample.csv
(ce dernier est la liste des domaines inconnus de Tracker Radar, à annoter à
deux puis à passer à tm.feasibility.kappa).
"""
import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict

import networkx as nx
from scipy.stats import spearmanr

from tm.domains import reg
from tm.io import iter_crawl_dir
from tm.labels.rules import label_domain, load_easyprivacy, load_tracker_radar
from tm.parse.resolve import FP_NODE, resolve_site

# Plateformes de gestion du consentement (bandeaux cookies) les plus courantes.
CMP_DOMAINS = {
  "cookielaw.org", "onetrust.com", "cookiebot.com", "consensu.org", "didomi.io",
  "privacy-mgmt.com", "trustarc.com", "usercentrics.eu", "osano.com", "iubenda.com",
  "termly.io", "cookieyes.com", "cookie-script.com", "transcend-cdn.com",
  "consentmanager.net", "quantcast.com", "sourcepoint.com", "cookiefirst.com",
}

THRESHOLDS = {
  "success_rate": 0.80,
  "initiator_resolution_rate": 0.80,
  "share_domains_majority_depth_ge2": 0.20,
  "labeled_domains_full_crawl": 500,
  "share_domains_absent_from_tr": 0.10,
  "entities_ge2_domains": 30,
}


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("crawl_jsonl")
  ap.add_argument("--tracker-radar", required=True)
  ap.add_argument("--easyprivacy", default=None)
  ap.add_argument("--n-target", type=int, default=7665, help="nb de sites du crawl complet")
  ap.add_argument("--concurrency", type=int, default=4)
  ap.add_argument("--outdir", default=".")
  a = ap.parse_args()

  recs = list(iter_crawl_dir([a.crawl_jsonl]))
  n = len(recs)
  status = Counter(r["status"] for r in recs)
  challenge = sum(1 for r in recs if r.get("challenge"))
  usable = [r for r in recs if r["status"] in ("ok", "timeout") and not r.get("challenge")
            and len(r["requests"]) >= 2]

  tr = load_tracker_radar(a.tracker_radar)
  ep = load_easyprivacy(a.easyprivacy)

  dom_sites = defaultdict(set)        # domaine -> sites où il apparaît
  dom_depths = defaultdict(list)      # domaine -> profondeurs observées
  dom_parents = defaultdict(Counter)  # domaine -> parents observés
  dom_example = {}                    # domaine -> une URL d'exemple
  methods = Counter()
  edge_sites = Counter()              # (parent, enfant) -> nb de sites
  cmp_sites = 0
  tp_cookie_sites = 0
  for r in usable:
    res = resolve_site(r)
    methods.update(res.methods)
    for d, depth in res.pair_depth.items():
      dom_sites[d].add(r["origin"])
      dom_depths[d].append(depth)
    for p, c in res.edges:
      edge_sites[(p, c)] += 1
      dom_parents[c][p] += 1
    for q in r["requests"]:
      d = reg(q["url"])
      if d and d not in res.fp:
        dom_example.setdefault(d, q["url"][:200])
    if any(reg(q["url"]) in CMP_DOMAINS for q in r["requests"]):
      cmp_sites += 1
    if any(c.get("domain") and reg(c["domain"].lstrip(".")) not in res.fp for c in r["cookies"]):
      tp_cookie_sites += 1

  # Chaînes d'inclusion : part des requêtes tierces dont on connaît l'initiateur,
  # et profondeur des domaines (médiane sur les sites où ils apparaissent).
  tp_req = sum(methods.values())
  resolved = methods["redirect"] + methods["stack"] + methods["init_url"]
  doms = sorted(dom_sites)
  maj_ge2 = sum(1 for d in doms if statistics.median(dom_depths[d]) >= 2)
  any_ge2 = sum(1 for d in doms if max(dom_depths[d]) >= 2)
  depths = [x for d in doms for x in dom_depths[d]]
  depth_hist = Counter(min(x, 4) for x in depths)

  # PageRank sur le graphe tiers -> tiers (networkx suffit pour le pilote).
  G = nx.DiGraph()
  for (p, c), w in edge_sites.items():
    if p != FP_NODE:
      G.add_edge(p, c, weight=w)
  rho_prev = None
  if G.number_of_edges() >= 5:
    pr = nx.pagerank(G, alpha=0.85, weight="weight")
    nodes = [v for v in G.nodes if v in dom_sites]
    prevalence = [len(dom_sites[v]) for v in nodes]
    if len(nodes) >= 5 and len(set(prevalence)) > 1:
      rho_prev = round(float(spearmanr([pr[v] for v in nodes], prevalence).statistic), 3)

  # Labels et entités propriétaires.
  labels = Counter()
  dom_label = {}
  owners = Counter()
  for d in doms:
    info = label_domain(d, tr, ep)
    dom_label[d] = info["label"]
    labels[info["label"]] += 1
    if info["owner"]:
      owners[info["owner"]] += 1
  labeled = labels["tracking"] + labels["non_tracking"]
  ent_ge2 = sum(1 for c in owners.values() if c >= 2)

  # Coût du crawl complet, estimé à partir de la durée médiane d'une visite.
  durations = sorted(r["duration_s"] for r in recs if r.get("duration_s"))
  med = statistics.median(durations) if durations else None
  p90 = durations[int(0.9 * (len(durations) - 1))] if durations else None
  hours_full = round(a.n_target * med / a.concurrency / 3600, 1) if med else None
  # Le nombre de domaines distincts croît moins vite que le nombre de sites :
  # on extrapole en racine carrée plutôt que linéairement.
  scale = (a.n_target / max(1, len(usable))) ** 0.5

  m = {
    "n_sites": n, "status": dict(status), "challenge": challenge, "usable": len(usable),
    "success_rate": round(len(usable) / n, 3) if n else 0,
    "tp_requests": tp_req, "parent_method": dict(methods),
    "initiator_resolution_rate": round(resolved / tp_req, 3) if tp_req else 0,
    "tp_domains": len(doms), "tp_site_pairs": len(depths),
    "depth_hist_pairs": {str(k): v for k, v in sorted(depth_hist.items())},
    "share_pairs_depth_ge2": round(sum(1 for x in depths if x >= 2) / len(depths), 3) if depths else 0,
    "share_domains_any_depth_ge2": round(any_ge2 / len(doms), 3) if doms else 0,
    "share_domains_majority_depth_ge2": round(maj_ge2 / len(doms), 3) if doms else 0,
    "graph_tp_nodes": G.number_of_nodes(), "graph_tp_edges": G.number_of_edges(),
    "spearman_pagerank_vs_prevalence": rho_prev,
    "labels": dict(labels), "labeled": labeled,
    "labeled_full_crawl_estimate": round(labeled * scale),
    "share_domains_absent_from_tr": round(labels["unknown"] / len(doms), 3) if doms else 0,
    "entities_observed": len(owners), "entities_ge2_domains": ent_ge2,
    "cmp_site_rate": round(cmp_sites / len(usable), 3) if usable else 0,
    "tp_cookie_site_rate": round(tp_cookie_sites / len(usable), 3) if usable else 0,
    "duration_median_s": med, "duration_p90_s": p90,
    "jsonl_kb_per_site": round(os.path.getsize(a.crawl_jsonl) / 1024 / n, 1) if n else 0,
    "estimated_hours_full_crawl": hours_full,
    "easyprivacy_rules_loaded": len(ep),
  }

  criteria = [
    ("2. Taux de succès du crawl", m["success_rate"], THRESHOLDS["success_rate"]),
    ("3a. Requêtes tierces à parent résolu", m["initiator_resolution_rate"],
     THRESHOLDS["initiator_resolution_rate"]),
    ("3b. Domaines majoritairement à profondeur >= 2", m["share_domains_majority_depth_ge2"],
     THRESHOLDS["share_domains_majority_depth_ge2"]),
    ("4a. Domaines étiquetés (estimation crawl complet)", m["labeled_full_crawl_estimate"],
     THRESHOLDS["labeled_domains_full_crawl"]),
    ("4b. Part de domaines absents de Tracker Radar", m["share_domains_absent_from_tr"],
     THRESHOLDS["share_domains_absent_from_tr"]),
    ("5. Entités avec >= 2 domaines observés", m["entities_ge2_domains"],
     THRESHOLDS["entities_ge2_domains"]),
  ]

  os.makedirs(a.outdir, exist_ok=True)
  with open(os.path.join(a.outdir, "metrics.json"), "w", encoding="utf-8") as fh:
    json.dump(m, fh, indent=2, ensure_ascii=False)
  with open(os.path.join(a.outdir, "inclusion_edges.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["parent", "child", "n_sites"])
    for (p, c), k in edge_sites.most_common():
      w.writerow([p, c, k])
  unknown = sorted((d for d in doms if dom_label[d] == "unknown"),
                   key=lambda d: -len(dom_sites[d]))[:200]
  with open(os.path.join(a.outdir, "annotation_sample.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["domain", "n_sites", "example_url", "top_parents", "label_A", "label_B", "notes"])
    for d in unknown:
      w.writerow([d, len(dom_sites[d]), dom_example.get(d, ""),
                  "; ".join(p for p, _ in dom_parents[d].most_common(3)), "", "", ""])

  lines = ["# Rapport de faisabilité — crawl pilote", "",
           f"Sites visités : {n} · exploitables : {len(usable)} · statuts : {dict(status)} "
           f"· challenges anti-bot : {challenge}", "",
           "| Critère | Valeur | Seuil | Verdict |", "|---|---|---|---|"]
  for name, value, threshold in criteria:
    lines.append(f"| {name} | {value} | {threshold} | {'GO' if value >= threshold else 'NO-GO'} |")
  lines += ["", "## Indicateurs complémentaires", "",
            f"- Méthodes de résolution du parent : {dict(methods)}",
            f"- Profondeurs des couples site x domaine (4 = >= 4) : {m['depth_hist_pairs']}",
            f"- Couples à profondeur >= 2 : {m['share_pairs_depth_ge2']} · domaines vus au moins "
            f"une fois à >= 2 : {m['share_domains_any_depth_ge2']}",
            f"- Graphe tiers -> tiers : {m['graph_tp_nodes']} nœuds, {m['graph_tp_edges']} arêtes",
            f"- Spearman(PageRank, prévalence) = {rho_prev} (proche de 1 = la structure "
            f"n'apporte presque rien de plus que le comptage)",
            f"- Labels : {dict(labels)} · entités observées : {len(owners)}",
            f"- Sites avec bandeau de consentement : {m['cmp_site_rate']} · sites déposant "
            f"des cookies tiers : {m['tp_cookie_site_rate']}",
            f"- Durée par site : médiane {med} s, p90 {p90} s · {m['jsonl_kb_per_site']} Ko/site",
            f"- Crawl complet estimé ({a.n_target} sites, {a.concurrency} en parallèle) : "
            f"{hours_full} h",
            f"- Règles EasyPrivacy chargées : {len(ep)}", "",
            "Fichiers produits : metrics.json, inclusion_edges.csv, annotation_sample.csv."]
  with open(os.path.join(a.outdir, "report.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
  print("\n".join(lines))


if __name__ == "__main__":
  main()
