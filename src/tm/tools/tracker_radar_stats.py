"""Statistiques de faisabilité sur DuckDuckGo Tracker Radar (points 4 et 5).

Usage : python tracker_radar_stats.py <chemin/tracker-radar> [region]
Sortie : tableau texte + tracker_radar_stats.json
"""
import json
import os
import sys
from collections import Counter

TRACKING_CATS = {
    "Ad Motivated Tracking", "Advertising", "Analytics", "Audience Measurement",
    "Third-Party Analytics Marketing", "Action Pixels", "Session Replay",
    "Ad Fraud", "Unknown High Risk Behavior", "Obscure Ownership",
}


def load_region(root, region):
    d = os.path.join(root, "domains", region)
    for f in os.listdir(d):
        if f.endswith(".json"):
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                yield json.load(fh)


def main():
    root = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "US"
    recs = list(load_region(root, region))
    n = len(recs)
    cats = Counter(c for r in recs for c in r.get("categories", []))
    tracking = [r for r in recs if TRACKING_CATS & set(r.get("categories", []))]
    no_cat = sum(1 for r in recs if not r.get("categories"))

    # Profondeur d'inclusion : part des chargements initiés par un tiers.
    third_init_share = []
    top_is_third = 0
    for r in recs:
        ti = r.get("topInitiators") or []
        if not ti:
            continue
        fp = sum(x["prevalence"] for x in ti if x["domain"] == "first party")
        tp = sum(x["prevalence"] for x in ti if x["domain"] != "first party")
        tot = fp + tp
        if tot > 0:
            third_init_share.append(tp / tot)
        if ti[0]["domain"] != "first party":
            top_is_third += 1
    with_init = len(third_init_share)
    mean_third = sum(third_init_share) / with_init if with_init else 0.0
    ge_half = sum(1 for s in third_init_share if s >= 0.5)

    owners = Counter((r.get("owner") or {}).get("name") for r in recs)
    owners.pop(None, None)
    owners.pop("", None)
    ent_ge2 = sum(1 for _, c in owners.items() if c >= 2)
    dom_with_owner = sum(owners.values())

    # Union des régions
    union = set()
    for reg in os.listdir(os.path.join(root, "domains")):
        union.update(f[:-5] for f in os.listdir(os.path.join(root, "domains", reg)) if f.endswith(".json"))

    out = {
        "region": region,
        "n_domains": n,
        "n_tracking_category": len(tracking),
        "n_without_category": no_cat,
        "n_domains_union_all_regions": len(union),
        "regions": sorted(os.listdir(os.path.join(root, "domains"))),
        "domains_with_initiator_data": with_init,
        "mean_share_loads_initiated_by_third_party": round(mean_third, 4),
        "domains_majority_third_party_initiated": ge_half,
        "domains_top_initiator_is_third_party": top_is_third,
        "domains_with_owner": dom_with_owner,
        "entities_in_region": len(owners),
        "entities_with_ge2_domains": ent_ge2,
        "top_categories": cats.most_common(15),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    with open("tracker_radar_stats.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
