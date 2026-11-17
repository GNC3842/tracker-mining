"""E4 — Étiquette chaque domaine tiers observé (règles : tm/labels/rules.py).

Entrée : interim/site_domain.parquet
Sortie : interim/labels.parquet + results/labels_summary.json

labels.parquet est le seul fichier qui contient des informations venant de
Tracker Radar ou d'EasyPrivacy : aucun module de features ne doit le lire,
sinon les labels fuiteraient dans le modèle (tests/test_leakage.py).

Usage : python -m tm.labels.labels [--config config.yaml]
"""
import argparse
from collections import Counter

import pyarrow as pa
import pyarrow.parquet as pq

from tm.config import ensure_dir, load_config, repo_path
from tm.io import write_result
from tm.labels.rules import TRAINABLE, label_domain, load_easyprivacy, load_tracker_radar

SCHEMA = pa.schema([("domain", pa.string()), ("label", pa.string()), ("owner", pa.string()),
                    ("tr_key", pa.string()), ("tr_categories", pa.list_(pa.string())),
                    ("easyprivacy_key", pa.string()), ("n_sites", pa.int64())])


def build_labels(domain_counts, tr, ep):
  return [{**label_domain(d, tr, ep), "n_sites": int(domain_counts[d])}
          for d in sorted(domain_counts)]


def summarize(rows):
  labels = Counter(r["label"] for r in rows)
  owners = Counter(r["owner"] for r in rows if r["owner"])
  n_pos = labels["tracking"]
  n_neg = labels["non_tracking"]
  return {
    "n_domains": len(rows), "labels": dict(labels),
    "n_trainable": sum(labels[l] for l in TRAINABLE),
    "positive_rate_trainable": round(n_pos / max(1, n_pos + n_neg), 4),
    "n_owners": len(owners), "owners_ge2_domains": sum(1 for c in owners.values() if c >= 2),
    "share_unknown": round(labels["unknown"] / max(1, len(rows)), 4),
    "top_owners": owners.most_common(15),
  }


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("--config", default=None)
  ap.add_argument("--interim", default=None)
  ap.add_argument("--results", default=None)
  a = ap.parse_args(argv)
  cfg = load_config(a.config)
  interim = ensure_dir(a.interim or cfg["paths"]["interim"])

  sd = pq.read_table(interim / "site_domain.parquet", columns=["domain"]).to_pylist()
  counts = Counter(r["domain"] for r in sd)
  tr = load_tracker_radar(str(repo_path(cfg["ref"]["tracker_radar_index"])))
  ep = load_easyprivacy(str(repo_path(cfg["ref"]["easyprivacy"])))
  rows = build_labels(counts, tr, ep)
  pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), interim / "labels.parquet")
  summary = summarize(rows)
  write_result(repo_path(a.results or cfg["paths"]["results"]) / "labels_summary.json", summary, cfg)
  for k, v in summary.items():
    print(f"{k:24s} {v}")


if __name__ == "__main__":
  main()
