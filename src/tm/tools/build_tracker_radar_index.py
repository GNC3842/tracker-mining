  """Usage : python -m tm.tools.build_tr_index <chemin/tracker-radar> data/ref/tracker_radar_index.json
  """


import json
import sys

from tm.labels.rules import load_tracker_radar

def main():
  root, out = sys.argv[1], sys.argv[2]
  idx = load_tracker_radar(root)
  with open(out, "w", encoding="utf-8") as fh:
    json.dump({d: {"c": sorted(v["categories"]), "o": v["owner"]} for d, v in sorted(idx.items())},fh, ensure_ascii=False, separators=(",", ":"))
  print(f"Saved {len(idx)} domains to {out}")

if __name__ == "__main__":
  main()