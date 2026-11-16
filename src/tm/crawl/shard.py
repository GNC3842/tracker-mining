"""Découpe la liste de sites en k lots, pour crawler en plusieurs fois ou à deux.

lot(site) = md5(origine) mod k. On utilise md5 et pas hash() parce que hash()
change d'une exécution à l'autre ; les lots sont donc toujours les mêmes, et le
hachage mélange les paliers de rang (pas de lot "que des gros sites").

Usage :
  python -m tm.crawl.shard data/ref/sites_top.txt --k 4 --outdir data/raw/shards
"""
import argparse
import hashlib
from collections import Counter
from pathlib import Path


def shard_of(origin, k):
  return int(hashlib.md5(origin.encode("utf-8")).hexdigest(), 16) % k


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("sites")
  ap.add_argument("--k", type=int, default=4)
  ap.add_argument("--outdir", default="data/raw/shards")
  a = ap.parse_args(argv)

  out = Path(a.outdir)
  out.mkdir(parents=True, exist_ok=True)
  buckets = {i: [] for i in range(a.k)}
  with open(a.sites, encoding="utf-8") as fh:
    for line in fh:
      line = line.rstrip("\n")
      if line.strip():
        buckets[shard_of(line.split("\t")[0], a.k)].append(line)

  for i, lines in buckets.items():
    (out / f"sites_shard_{i}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ranks = Counter(l.split("\t")[1] if "\t" in l else "?" for l in lines)
    print(f"lot {i} : {len(lines)} sites, paliers {dict(sorted(ranks.items()))}")


if __name__ == "__main__":
  main()
