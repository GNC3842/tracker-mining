"""E3 — Transforme les JSONL du crawler en tables Parquet.

Entrée  : fichiers ou dossiers de crawl (défaut : paths.raw de config.yaml)
Sorties (paths.interim) :
  sites.parquet        1 ligne par site visité
  requests.parquet     1 ligne par requête HTTP(S) d'un site exploitable
  site_domain.parquet  1 ligne par couple (site, domaine tiers)
  edges_inc.parquet    1 ligne par arête d'inclusion (parent, enfant, n_sites)
  cookies.parquet      1 ligne par cookie (sans sa valeur)
  + results/tables_summary.json

SCHEMAS est le contrat entre les étapes : pour changer une table, on modifie
SCHEMAS et tests/test_build_tables.py.

Usage : python -m tm.parse.build_tables [--config config.yaml] [--crawl data/raw/...]
"""
import argparse
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tm.config import ensure_dir, load_config, repo_path
from tm.domains import reg
from tm.io import iter_crawl_dir, write_result
from tm.parse.resolve import DEFAULT_LIBRARY_HOSTS, FP_NODE, resolve_site

S, I, F, B = pa.string(), pa.int64(), pa.float64(), pa.bool_()
SCHEMAS = {
  "sites": pa.schema([("origin", S), ("rank", I), ("site", S), ("status", S), ("challenge", B),
                      ("usable", B), ("n_requests", I), ("n_tp_domains", I), ("duration_s", F),
                      ("final_url", S), ("error", S), ("crawl_ts", F)]),
  "requests": pa.schema([("origin", S), ("url", S), ("domain", S), ("type", S),
                         ("is_third_party", B), ("parent_url", S), ("parent_domain", S),
                         ("parent_method", S), ("depth", I)]),
  "site_domain": pa.schema([("origin", S), ("domain", S), ("min_depth", I), ("n_req", I),
                            ("types", pa.list_(S)), ("sets_cookie", B)]),
  "edges_inc": pa.schema([("parent", S), ("child", S), ("n_sites", I)]),
  "cookies": pa.schema([("origin", S), ("domain", S), ("is_third_party", B), ("name", S),
                        ("ttl_days", F), ("same_site", S), ("http_only", B)]),
}


def is_usable(rec, min_requests):
  """Page servie (même si "load" a expiré), sans challenge anti-bot, avec au
  moins une sous-ressource en plus du document."""
  return (rec.get("status") in ("ok", "timeout") and not rec.get("challenge")
          and len(rec.get("requests") or []) >= min_requests)


def to_int(x):
  try:
    return int(x)
  except (TypeError, ValueError):
    return None


def build(records, min_requests=2, library_hosts=DEFAULT_LIBRARY_HOSTS):
  out = {k: [] for k in SCHEMAS}
  edge_sites = Counter()
  for rec in records:
    usable = is_usable(rec, min_requests)
    row_site = {
      "origin": rec["origin"], "rank": to_int(rec.get("rank")), "site": rec.get("site"),
      "status": rec.get("status"), "challenge": bool(rec.get("challenge")), "usable": usable,
      "n_requests": len(rec.get("requests") or []), "n_tp_domains": 0,
      "duration_s": rec.get("duration_s"), "final_url": rec.get("final_url"),
      "error": rec.get("error"), "crawl_ts": rec.get("ts"),
    }
    out["sites"].append(row_site)
    if not usable:
      continue

    res = resolve_site(rec, library_hosts)
    for r in res.rows:
      out["requests"].append({"origin": rec["origin"], **r})

    cookie_doms = set()
    ts = rec.get("ts")
    for c in rec.get("cookies") or []:
      d = reg((c.get("domain") or "").lstrip("."))
      if not d:
        continue
      is_tp = d not in res.fp
      if is_tp:
        cookie_doms.add(d)
      exp = c.get("expires")
      ttl = (exp - ts) / 86400 if (exp and exp > 0 and ts) else None   # None = cookie de session
      out["cookies"].append({"origin": rec["origin"], "domain": d, "is_third_party": is_tp,
                             "name": c.get("name"), "ttl_days": ttl,
                             "same_site": c.get("sameSite"), "http_only": c.get("httpOnly")})

    for d, n in res.pair_nreq.items():
      out["site_domain"].append({
        "origin": rec["origin"], "domain": d, "min_depth": res.pair_depth.get(d),
        "n_req": n, "types": sorted(res.pair_types.get(d, ())), "sets_cookie": d in cookie_doms,
      })
    row_site["n_tp_domains"] = len(res.pair_nreq)
    edge_sites.update(res.edges)       # res.edges est un ensemble : +1 par site

  out["edges_inc"] = [{"parent": p, "child": c, "n_sites": n}
                      for (p, c), n in sorted(edge_sites.items(), key=lambda kv: (-kv[1], kv[0]))]
  return out


def write_tables(tables, outdir):
  for name, rows in tables.items():
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMAS[name]), Path(outdir) / f"{name}.parquet")


def summarize(t):
  sites = t["sites"]
  usable = [s for s in sites if s["usable"]]
  tp_req = [r for r in t["requests"] if r["is_third_party"]]
  methods = Counter(r["parent_method"] for r in tp_req)
  reliable = sum(methods[m] for m in ("redirect", "stack", "init_url"))
  domains = {sd["domain"] for sd in t["site_domain"]}
  return {
    "n_sites": len(sites), "n_usable": len(usable),
    "success_rate": round(len(usable) / len(sites), 4) if sites else None,
    "status": dict(Counter(s["status"] for s in sites)),
    "challenges": sum(s["challenge"] for s in sites),
    "n_requests": len(t["requests"]), "n_tp_requests": len(tp_req),
    "parent_method_tp": dict(methods),
    "reliable_parent_rate": round(reliable / len(tp_req), 4) if tp_req else None,
    "n_tp_domains": len(domains), "n_site_domain_pairs": len(t["site_domain"]),
    "n_edges_inc": len(t["edges_inc"]),
    "n_edges_inc_tp_tp": sum(1 for e in t["edges_inc"] if e["parent"] != FP_NODE),
    "n_cookies": len(t["cookies"]),
  }


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("--config", default=None)
  ap.add_argument("--crawl", nargs="*", default=None, help="fichiers ou dossiers JSONL")
  ap.add_argument("--outdir", default=None)
  ap.add_argument("--results", default=None)
  a = ap.parse_args(argv)
  cfg = load_config(a.config)
  crawl = [repo_path(p) for p in (a.crawl or [cfg["paths"]["raw"]])]
  outdir = ensure_dir(a.outdir or cfg["paths"]["interim"])

  lib = (cfg.get("resolve") or {}).get("library_hosts")
  tables = build(iter_crawl_dir(crawl), cfg["tables"]["min_requests_usable"],
                 frozenset(lib) if lib is not None else DEFAULT_LIBRARY_HOSTS)
  write_tables(tables, outdir)
  summary = summarize(tables)
  res_dir = repo_path(a.results or cfg["paths"]["results"])
  write_result(res_dir / "tables_summary.json", {"inputs": [str(p) for p in crawl], **summary}, cfg)
  for k, v in summary.items():
    print(f"{k:28s} {v}")
  print(f"-> {outdir}")


if __name__ == "__main__":
  main()
