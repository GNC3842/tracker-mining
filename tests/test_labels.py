import pytest

from tm.config import repo_path
from tm.labels.labels import build_labels, summarize
from tm.labels.rules import (aggregate_to_registrable, label_domain, load_easyprivacy,
                             load_tracker_radar)

TR = {
    "trk.com": {"categories": {"Analytics"}, "owner": "Trk Inc"},
    "mixed.com": {"categories": {"Analytics", "CDN"}, "owner": "Mixed"},
    "cdn.com": {"categories": {"CDN"}, "owner": "Cdn Co"},
    "bare.com": {"categories": set(), "owner": "Bare"},
}


@pytest.mark.parametrize("domain, ep, expected", [
    ("trk.com", frozenset(), "tracking"),             # règle 2 (catégorie)
    ("mixed.com", frozenset(), "ambiguous"),          # règle 1
    ("eponly.com", frozenset({"eponly.com"}), "tracking"),   # règle 2 (EasyPrivacy seul)
    ("cdn.com", frozenset({"cdn.com"}), "ambiguous"),        # règle 3
    ("cdn.com", frozenset(), "non_tracking"),         # règle 4
    ("bare.com", frozenset(), "uncategorized"),       # règle 5 : PAS un négatif
    ("nowhere.vn", frozenset(), "unknown"),           # règle 6
])
def test_label_rules(domain, ep, expected):
    assert label_domain(domain, TR, ep)["label"] == expected


def test_suffix_lookup_for_subdomain_keys():
    assert label_domain("a.trk.com", TR, frozenset())["tr_key"] == "trk.com"


def test_aggregation_of_subdomain_only_entries():
    idx = {"fonts.big.com": {"categories": {"CDN"}, "owner": "Big"},
           "ads.big.com": {"categories": {"Advertising"}, "owner": "Big"},
           "x.split.com": {"categories": set(), "owner": "A"},
           "y.split.com": {"categories": set(), "owner": "B"}}
    agg = aggregate_to_registrable(idx)
    assert agg["big.com"]["categories"] == {"CDN", "Advertising"}
    assert agg["big.com"]["owner"] == "Big" and agg["big.com"]["aggregated_from"] == 2
    assert agg["split.com"]["owner"] is None            # propriétaires contradictoires
    assert label_domain("big.com", agg, frozenset())["tr_key"] == "big.com*"


def test_easyprivacy_parser_only_pure_domain_rules(tmp_path):
    p = tmp_path / "ep.txt"
    p.write_text("||track.com^\n||tp.com^$third-party\n||path.com/t.js\n||img.com^$image\n! comment\n")
    assert load_easyprivacy(str(p)) == frozenset({"track.com", "tp.com"})


def test_summary_counts():
    rows = build_labels({"trk.com": 3, "cdn.com": 2, "bare.com": 1, "nowhere.vn": 1}, TR, frozenset())
    s = summarize(rows)
    assert s["n_trainable"] == 2 and s["positive_rate_trainable"] == 0.5
    assert s["labels"]["unknown"] == 1 and s["share_unknown"] == 0.25


def test_reference_data_smoke():
    """Données de référence versionnées : quelques domaines connus."""
    tr = load_tracker_radar(str(repo_path("data/ref/tracker_radar_index.json")))
    ep = load_easyprivacy(str(repo_path("data/ref/easyprivacy.txt")))
    assert len(tr) > 20_000 and len(ep) > 40_000
    assert label_domain("google-analytics.com", tr, ep)["label"] == "tracking"
    assert label_domain("google-analytics.com", tr, ep)["owner"] == "Google LLC"
    assert label_domain("cloudflare.com", tr, ep)["label"] == "ambiguous"
    assert label_domain("jsdelivr.net", tr, ep)["label"] == "non_tracking"
