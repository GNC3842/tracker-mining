"""Liste les sites non exploitables d'un crawl, pour une seconde passe
(timeout plus long, moins de sites en parallèle).

Les sites bloqués par un anti-bot sont ignorés : relancer depuis la même IP
donnerait le même résultat (--include-challenges pour quand même les reprendre).

Usage :
  python -m tm.crawl.failed data/raw/full --out data/raw/retry_sites.txt
  python -m tm.crawl.crawl --sites data/raw/retry_sites.txt \
      --out data/raw/full/crawl_retry.jsonl --timeout 45 --concurrency 2
"""
import argparse
from collections import Counter

from tm.io import iter_crawl_dir
from tm.parse.build_tables import is_usable


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("crawl", nargs="+")
  ap.add_argument("--out", required=True)
  ap.add_argument("--min-requests", type=int, default=2)
  ap.add_argument("--include-challenges", action="store_true")
  a = ap.parse_args(argv)

  todo, reasons = [], Counter()
  for r in iter_crawl_dir(a.crawl):
    if is_usable(r, a.min_requests):
      continue
    if r.get("challenge") and not a.include_challenges:
      reasons["challenge (ignoré)"] += 1
      continue
    reasons[r.get("status") or "?"] += 1
    todo.append(f"{r['origin']}\t{r.get('rank') or ''}\t{r.get('site') or ''}")

  with open(a.out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(todo) + ("\n" if todo else ""))
  print(f"{len(todo)} sites à relancer -> {a.out} ; motifs : {dict(reasons)}")


if __name__ == "__main__":
  main()
