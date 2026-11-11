"""Sources de vérité terrain et règles d'étiquetage des domaines.

Sources :
- DuckDuckGo Tracker Radar (CC BY-NC-SA 4.0) : catégories + propriétaire par domaine,
  union des 9 régions disponibles (aucune en Asie).
- EasyPrivacy : uniquement les règles de DOMAINE PUR (||domaine^ ou ||domaine^$third-party).
  Les règles à chemin (||x.com/track.js) ciblent une URL, pas un domaine entier.

Règle de label (ordre d'évaluation) :
  1. catégorie de pistage ET catégorie fonctionnelle (ex. cloudflare.com :
     Analytics + CDN)                                      -> ambiguous
  2. catégorie de pistage, ou EasyPrivacy sans catégorie fonctionnelle -> tracking
  3. EasyPrivacy + catégorie fonctionnelle                 -> ambiguous
  4. au moins une catégorie, aucune de pistage             -> non_tracking
  5. présent dans Tracker Radar sans aucune catégorie      -> uncategorized
  6. absent de Tracker Radar et d'EasyPrivacy              -> unknown
Seuls tracking / non_tracking servent à l'apprentissage et à l'évaluation.
`uncategorized` n'est PAS un négatif : 76 % des domaines de Tracker Radar n'ont
aucune catégorie, les traiter comme non-traceurs biaiserait T1.
"""
from __future__ import annotations

import json
import os
import re

from tm.domains import lookup_suffix, reg

TRACKING_CATS = frozenset({
  "Ad Motivated Tracking", "Advertising", "Analytics", "Audience Measurement",
  "Third-Party Analytics Marketing", "Action Pixels", "Session Replay",
  "Ad Fraud", "Unknown High Risk Behavior", "Obscure Ownership",
})

FUNCTIONAL_CATS = frozenset({
  "CDN", "Embedded Content", "Online Payment", "Federated Login", "SSO",
  "Support Chat Widget", "Non-Tracking", "Badge", "Social - Share", "Social - Comment",
  "Fraud Prevention", "Consent Management Platform",
})

LABELS = ("tracking", "non_tracking", "ambiguous", "uncategorized", "unknown")
TRAINABLE = ("tracking", "non_tracking")

_EP_RULE = re.compile(r"^\|\|([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\^(\$third-party)?$")


def load_tracker_radar(path: str) -> dict[str, dict]:
  """domaine -> {"categories": set[str], "owner": str|None}.
  `path` : index compact .json (data/ref/tracker_radar_index.json) ou dépôt cloné."""
  if str(path).endswith(".json"):
    with open(path, encoding="utf-8") as fh:
      raw = json.load(fh)
    return aggregate_to_registrable({d: {"categories": set(v["c"]), "owner": v["o"]} for d, v in raw.items()})
  idx: dict[str, dict] = {}
  droot = os.path.join(path, "domains")
  for region in sorted(os.listdir(droot)):
    for f in os.listdir(os.path.join(droot, region)):
      if not f.endswith(".json"):
        continue
      with open(os.path.join(droot, region, f), encoding="utf-8") as fh:
        d = json.load(fh)
      cur = idx.setdefault(f[:-5], {"categories": set(), "owner": None})
      cur["categories"].update(d.get("categories") or [])
      owner = (d.get("owner") or {}).get("name")
      if owner and not cur["owner"]:
        cur["owner"] = owner
  return idx


def aggregate_to_registrable(idx: dict[str, dict]) -> dict[str, dict]:
  groups: dict[str, list[str]] = {}
  for k in idx:
    r = reg(k)
    if r and r != k and r not in idx:
        groups.setdefault(r, []).append(k)
  out = dict(idx)
  for r, keys in groups.items():
    owners = {idx[k]["owner"] for k in keys if idx[k]["owner"]}
    out[r] = {"categories": set().union(*(idx[k]["categories"] for k in keys)),
                  "owner": owners.pop() if len(owners) == 1 else None,
                  "aggregated_from": len(keys)}
  return out


def load_easyprivacy(path: str | None) -> frozenset[str]:
  if not path:
    return frozenset()
  doms = set()
  with open(path, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
      m = _EP_RULE.match(line.strip().lower())
      if m:
        doms.add(m.group(1))
  return frozenset(doms)


def label_domain(domain: str, tr: dict[str, dict], ep: frozenset[str]) -> dict:
  key = lookup_suffix(domain, tr)
  cats: set[str] = tr[key]["categories"] if key else set()
  owner = tr[key]["owner"] if key else None
  ep_key = lookup_suffix(domain, ep) if ep else None
  trk, fun = bool(cats & TRACKING_CATS), bool(cats & FUNCTIONAL_CATS)
  if trk and fun:
    label = "ambiguous"
  elif trk or (ep_key and not fun):
    label = "tracking"
  elif ep_key:
    label = "ambiguous"
  elif cats:
    label = "non_tracking"
  elif key:
    label = "uncategorized"
  else:
    label = "unknown"
  if key and tr[key].get("aggregated_from"):
    key = key + "*"
  return {"domain": domain, "label": label, "owner": owner,
     "tr_key": key, "tr_categories": sorted(cats), "easyprivacy_key": ep_key}