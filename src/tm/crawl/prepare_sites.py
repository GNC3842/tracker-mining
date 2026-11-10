import argparse
import csv
import gzip
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from tm.domains import reg

ADULT = re.compile(r"porn|xxx|sex|jav|hentai|stripchat|xvideo|xnxx|xhamster|onlyfans|camsoda|chaturbate|bongacams|livejasmin|nude|nsfw|erotic|18\+|phim\s*sex|clip\s*nong|spankbang|redtube|youporn|brazzers|jizz|milf|fap|cum|cock|pussy|dildo|anal|blowjob|cumshot|fetish|bdsm|shemale|transgender|transsexual|gay\s*porn|lesbian\s*porn",re.I,)


def public_suffix(dom):
  return dom.split(".", 1)[1] if "." in dom and not dom.replace(".", "").isdigit() else dom


def read_crux(path: str, max_rank: int) -> list[tuple[str, int]]:
  opener = gzip.open if path.endswith(".gz") else open
  rows = []
  with opener(path, "rt", encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
      rank = int(r["rank"])
      if rank <= max_rank:
        rows.append((r["origin"].strip(), rank))
  return rows


def dedup(rows):
  excluded_adult = 0
  seen: dict[str, tuple] = {}
  for origin, rank in sorted(rows, key=lambda x: (x[1], x[0])):
    if ADULT.search(origin):
      excluded_adult += 1
      continue
    dom = reg(origin)
    if not dom:
      continue
    pref = origin.rstrip("/") in (f"https://{dom}", f"https://www.{dom}")
    prev = seen.get(dom)
    if prev is None or (pref and not prev[2] and prev[1] == rank):
      seen[dom] = (origin, rank, pref)
  return seen, excluded_adult


def stratified_pilot(kept, n, seed):
  by_bucket: dict[int, list] = defaultdict(list)
  for item in kept:
      by_bucket[item[1]].append(item)
  rnd = random.Random(seed)
  total = len(kept)
  pilot = []
  for b, items in sorted(by_bucket.items()):
    k = max(1, round(n * len(items) / total))
    pilot += rnd.sample(items, min(k, len(items)))
  return pilot[:n]


def write_list(path: Path, items) -> None:
  with open(path, "w", encoding="utf-8") as fh:
    for origin, rank, dom in items:
      fh.write(f"{origin}\t{rank}\t{dom}\n")


def main(argv: list[str] | None = None) -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("crux_csv", help="fichier CrUX .csv ou .csv.gz")
  ap.add_argument("--max-rank", type=int, default=10000)
  ap.add_argument("--pilot", type=int, default=200)
  ap.add_argument("--seed", type=int, default=42)
  ap.add_argument("--outdir", default=".")
  a = ap.parse_args(argv)
  out = Path(a.outdir)
  out.mkdir(parents=True, exist_ok=True)

  rows = read_crux(a.crux_csv, a.max_rank)
  seen, excluded_adult = dedup(rows)
  kept = sorted(((o, r, d) for d, (o, r, _) in seen.items()), key=lambda x: (x[1], x[2]))
  pilot = stratified_pilot(kept, a.pilot, a.seed)
  write_list(out / "sites_top.txt", kept)
  write_list(out / "sites_pilot.txt", pilot)

  suffixes = Counter(public_suffix(d) for _, _, d in kept)
  vn = sum(c for s, c in suffixes.items() if s == "vn" or s.endswith(".vn"))
  buckets = Counter(r for _, r, _ in kept)
  stats = {
    "source": a.crux_csv, "max_rank": a.max_rank, "seed": a.seed,
    "domain_definition": "tm.domains.reg (PSL embarquée, section privée incluse)",
    "origins_in_rank_window": len(rows),
    "excluded_adult_keyword": excluded_adult,
    "unique_registrable_domains": len(kept),
    "share_vn_suffix": round(vn / len(kept), 4) if kept else 0,
    "buckets": {str(b): n for b, n in sorted(buckets.items())},
    "pilot_size": len(pilot),
    "pilot_buckets": {str(b): n for b, n in sorted(Counter(r for _, r, _ in pilot).items())},
    "top_suffixes": suffixes.most_common(10),
}
  with open(out / "sites_stats.json", "w", encoding="utf-8") as fh:
    json.dump(stats, fh, indent=2, ensure_ascii=False)
  print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
  main()