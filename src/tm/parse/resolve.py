"""Reconstruit les chaînes d'inclusion d'un site à partir des requêtes du crawler.

Parent d'une requête, par ordre de priorité :
  1. "redirect" : l'URL qui a redirigé vers elle ;
  2. "stack"    : le script qui l'a émise (1er cadre de la pile d'appels JS), en
                  sautant les CDN de bibliothèques (jQuery, jsDelivr...) qui ne
                  font qu'exécuter le code de leur appelant ;
  3. "init_url" : initiator.url (document HTML pour le type "parser") ;
  4. "fallback" : le document du cadre (peu fiable : pas d'arête) ;
  5. "none"     : pas de parent (document principal).

Profondeur d'une requête = nombre de changements de domaine tiers en remontant
ses parents. 1 = chargé directement par le site, 2 = chargé par un tiers, etc.
Arête (parent -> enfant) au niveau domaine si le parent est fiable (1-3) et que
les deux domaines diffèrent ; le parent vaut "__FP__" s'il est premier parti.
"""
from collections import Counter
from dataclasses import dataclass, field

from tm.domains import host_of, is_http, reg

FP_NODE = "__FP__"
RELIABLE = ("redirect", "stack", "init_url")

# CDN publics qui servent des bibliothèques open source (liste volontairement courte).
DEFAULT_LIBRARY_HOSTS = frozenset({
  "code.jquery.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "fastly.jsdelivr.net",
  "unpkg.com", "ajax.googleapis.com", "ajax.aspnetcdn.com",
  "stackpath.bootstrapcdn.com", "maxcdn.bootstrapcdn.com",
})


def parent_of(r, library_hosts=DEFAULT_LIBRARY_HOSTS):
  """(url du parent, méthode utilisée)."""
  if r.get("redirect_from"):
    return r["redirect_from"], "redirect"
  if r.get("init_type") == "script" and r.get("stack"):
    for frame in r["stack"]:
      if host_of(frame) not in library_hosts:
        return frame, "stack"
    return r["stack"][0], "stack"      # que des bibliothèques : pas mieux
  if r.get("init_url"):
    return r["init_url"], "init_url"
  if r.get("doc") and r.get("type") != "Document":
    return r["doc"], "fallback"
  return None, "none"


@dataclass
class SiteResolution:
  origin: str
  fp: set                                      # domaines premier-parti du site
  rows: list = field(default_factory=list)     # 1 ligne par requête HTTP(S)
  pair_depth: dict = field(default_factory=dict)      # domaine tiers -> profondeur min
  pair_nreq: Counter = field(default_factory=Counter)  # domaine tiers -> nb requêtes
  pair_types: dict = field(default_factory=dict)       # domaine tiers -> types de requêtes
  edges: set = field(default_factory=set)              # arêtes domaine -> domaine
  methods: Counter = field(default_factory=Counter)    # méthodes de parent (requêtes tierces)


def resolve_site(rec, library_hosts=DEFAULT_LIBRARY_HOSTS):
  origin = rec["origin"]
  fp = {reg(origin)}
  if rec.get("final_url") and is_http(rec["final_url"]):
    fp.add(reg(rec["final_url"]))
  fp.discard("")
  reqs = [r for r in rec.get("requests", []) if is_http(r.get("url", ""))]
  first_by_url = {}
  for r in reqs:
    first_by_url.setdefault(r["url"], r)

  def depth(url):
    """Remonte la chaîne des parents en comptant les changements de domaine tiers.
    `seen` coupe les cycles (un script peut être déclaré initiateur de son initiateur)."""
    d = 0
    seen = set()
    cur = url
    while cur and cur not in seen:
      seen.add(cur)
      r = first_by_url.get(cur)
      parent = parent_of(r, library_hosts)[0] if r else None
      dom = reg(cur)
      pdom = reg(parent) if parent else None
      if dom not in fp and dom != pdom:
        d += 1
      cur = parent
    return d

  res = SiteResolution(origin=origin, fp=fp)
  for r in reqs:
    d = reg(r["url"])
    pu, how = parent_of(r, library_hosts)
    pdom = reg(pu) if pu and is_http(pu) else None
    dep = depth(r["url"])
    is_tp = bool(d) and d not in fp
    res.rows.append({
      "url": r["url"], "domain": d, "type": r.get("type"), "is_third_party": is_tp,
      "parent_url": pu, "parent_domain": pdom, "parent_method": how, "depth": dep,
    })
    if not is_tp:
      continue
    res.methods[how] += 1
    res.pair_nreq[d] += 1
    res.pair_types.setdefault(d, set()).add(r.get("type") or "Other")
    if dep >= 1:
      res.pair_depth[d] = min(res.pair_depth.get(d, dep), dep)
    if how in RELIABLE and pdom and pdom != d:
      res.edges.add((FP_NODE if pdom in fp else pdom, d))
  return res
