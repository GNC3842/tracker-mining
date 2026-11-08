"""
Usage :
  python -m tm.crawl.prepare_sites crux_vn.csv --max-rank 10000 --pilot 200 --seed 666
Sorties :
  sites_top.txt     origines retenues (1 par domaine enregistrable)
  sites_pilot.txt   échantillon stratifié par palier pour le pilote
  sites_stats.json  statistiques (taille, part .vn, exclusions)
"""

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict


#Suffixes
KNOWN_SUFFIXES = {
  "vn", "com.vn", "edu.vn", "gov.vn", "net.vn", "org.vn", "int.vn", "ac.vn", "biz.vn", "info.vn",
  "co.uk", "org.uk", "gov.uk", "ac.uk", "net.uk",
  "com", "org", "net", "edu", "gov", "mil", "int",
  "co", "io", "me", "ai", "app", "dev", "tech", "info", "biz", "name",
  "fr", "com.fr", "asso.fr", "net.fr", "org.fr",
  "de", "jp", "co.jp", "uk", "ca", "au", "com.au", "net.au"
}

#We blocked adult sites, so we don't need to crawl them.
ADULT = re.compile(r"porn|sex|adult|xxx|erotic|camgirl|camsex|camshow|cam4|camsoda|chaturbate|onlyfans |hentai|jav|nude|18\+|stripchats|xhamster|xhwide|xhsocial", re.IGNORECASE)


#Extract eTLD+1 and suffix 
def registrable(origin):
  host = origin.split("://")[-1].split("/")[0].split(":")[0]
  parts = host.split(".")

  #search for the longest known suffix
  suffix = ""
  for i in range(len(parts)):
    candidate = ".".join(parts[i:])
    if candidate in KNOWN_SUFFIXES:
      suffix = candidate
      break
  #if suffix is not found, we take the 2 last parts as suffix or the last at least
  if not suffix:
    if len(parts) >= 2:
      suffix = ".".join(parts[-2:])
    elif len(parts) == 1:
      suffix = parts[0]
      return host, suffix
  #extract eTLD+1
  suffix_parts_count = len(suffix.split("."))
  domain_parts_count = suffix_parts_count + 1 
  if len(parts) >= domain_parts_count:
    dom = ".".join(parts[-domain_parts_count:])
  else:
    dom = host    
  return dom, suffix


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("crux_csv")  # CSV déjà décompressé
  ap.add_argument("--max-rank", type=int, default=10000)
  ap.add_argument("--pilot", type=int, default=200)
  ap.add_argument("--seed", type=int, default=42)
  a = ap.parse_args()

  rows = []
  with open(a.crux_csv, "rt", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
      if int(r["rank"]) <= a.max_rank:
        rows.append((r["origin"], int(r["rank"])))

  excluded_adult = 0
  seen = {}
  for origin, rank in sorted(rows, key=lambda x: x[1]):
    dom, suffix = registrable(origin)
    if ADULT.search(origin):
      excluded_adult += 1
      continue
    #Keep the first occurrence of a domain, or the one with the preferred origin (https://domain or https://www.domain) if available
    prev = seen.get(dom)
    pref = origin in (f"https://{dom}", f"https://www.{dom}")
    if prev is None or (pref and not prev[2] and prev[1] >= rank):
      seen[dom] = (origin, rank, pref, suffix)

  kept = sorted(seen.items(), key=lambda kv: kv[1][1])
  with open("sites_top.txt", "w") as fh:
    for dom, (origin, rank, _, _) in kept:
      fh.write(f"{origin}\t{rank}\t{dom}\n")

  by_bucket = defaultdict(list)
  for dom, v in kept:
    by_bucket[v[1]].append((v[0], v[1], dom))
  rnd = random.Random(a.seed)
  total = len(kept)
  pilot = []
  for b, items in sorted(by_bucket.items()):
    k = max(1, round(a.pilot * len(items) / total))
    pilot += rnd.sample(items, min(k, len(items)))
  pilot = pilot[: a.pilot]
  with open("sites_pilot.txt", "w") as fh:
    for origin, rank, dom in pilot:
      fh.write(f"{origin}\t{rank}\t{dom}\n")

  suffixes = Counter(v[3] for _, v in kept)
  vn = sum(c for s, c in suffixes.items() if s == "vn" or s.endswith(".vn"))
  stats = {
    "origins_in_rank_window": len(rows),
    "excluded_adult_keyword": excluded_adult,
    "unique_registrable_domains": total,
    "share_vn_suffix": round(vn / total, 4) if total else 0,
    "buckets": {str(b): len(v) for b, v in sorted(by_bucket.items())},
    "pilot_size": len(pilot),
    "top_suffixes": suffixes.most_common(10),
  }
  print(json.dumps(stats, indent=2))
  with open("sites_stats.json", "w") as fh:
    json.dump(stats, fh, indent=2)


if __name__ == "__main__":
    main()