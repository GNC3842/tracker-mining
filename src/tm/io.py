"""Lecture des fichiers JSONL du crawler et écriture des résultats JSON."""
import gzip
import json
from pathlib import Path


def iter_jsonl(path):
  """Itère sur un .jsonl ou .jsonl.gz. Les lignes illisibles (crawl interrompu
  en pleine écriture) sont ignorées."""
  path = Path(path)
  opener = gzip.open if path.suffix == ".gz" else open
  with opener(path, "rt", encoding="utf-8") as fh:
    for line in fh:
      line = line.strip()
      if not line:
        continue
      try:
        yield json.loads(line)
      except json.JSONDecodeError:
        print(f"[iter_jsonl] ligne illisible ignorée dans {path.name}")


def iter_crawl_dir(paths):
  """Itère sur plusieurs fichiers ou dossiers de crawl, un enregistrement par site.
  Un site peut avoir été visité deux fois (2e passe sur les échecs) : on garde la
  visite qui a vu le plus de requêtes."""
  files = []
  for p in map(Path, paths):
    if p.is_dir():
      files += sorted(p.glob("*.jsonl")) + sorted(p.glob("*.jsonl.gz"))
    else:
      files.append(p)
  best = {}
  for f in files:
    for rec in iter_jsonl(f):
      origin = rec.get("origin")
      if not origin:
        continue
      prev = best.get(origin)
      if prev is None or len(rec.get("requests", [])) > len(prev.get("requests", [])):
        best[origin] = rec
  return best.values()


def write_result(path, payload, cfg=None):
  """Écrit un JSON de résultat, avec la config utilisée pour le produire."""
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  doc = {"config": cfg or {}, **payload}
  with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2, ensure_ascii=False, default=str)
  return path
