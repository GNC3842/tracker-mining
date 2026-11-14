from collections import Counter

from tm.parse.resolve import FP_NODE, parent_of, resolve_site

# Vérité terrain du banc (bench/bench_server.py)
EXPECTED_DEPTH = {
    "tagmgr-bench.com": 1, "pixel-bench.org": 1, "embed-bench.vn": 1,
    "analytics-bench.net": 2, "deep-bench.net": 2,
    "ads-bench.io": 3, "deep-collect-bench.com": 3, "cdn-bench.co": 4,
}
EXPECTED_EDGES = {
    (FP_NODE, "tagmgr-bench.com"), (FP_NODE, "pixel-bench.org"), (FP_NODE, "embed-bench.vn"),
    ("tagmgr-bench.com", "analytics-bench.net"), ("embed-bench.vn", "deep-bench.net"),
    ("analytics-bench.net", "ads-bench.io"), ("analytics-bench.net", "pixel-bench.org"),
    ("deep-bench.net", "deep-collect-bench.com"), ("ads-bench.io", "cdn-bench.co"),
}


def test_bench_depths(news_record):
    res = resolve_site(news_record)
    assert res.fp == {"news-bench.vn"}
    assert res.pair_depth == EXPECTED_DEPTH


def test_bench_edges(news_record):
    assert resolve_site(news_record).edges == EXPECTED_EDGES


def test_bench_parent_methods(news_record):
    # 4 via le HTML (parser), 5 via une pile JS, 1 via redirection HTTP 302
    assert resolve_site(news_record).methods == Counter({"stack": 5, "init_url": 4, "redirect": 1})


def test_first_party_requests_have_depth_zero(news_record):
    res = resolve_site(news_record)
    fp_rows = [r for r in res.rows if not r["is_third_party"]]
    assert fp_rows and all(r["depth"] == 0 for r in fp_rows)


def test_parent_priority():
    base = {"url": "https://x.com/a", "type": "Script", "doc": "https://site.vn/"}
    assert parent_of({**base, "redirect_from": "https://r.com/", "init_type": "script",
                      "stack": ["https://s.com/s.js"]}) == ("https://r.com/", "redirect")
    assert parent_of({**base, "init_type": "script", "stack": ["https://s.com/s.js"],
                      "init_url": "https://i.com/"}) == ("https://s.com/s.js", "stack")
    assert parent_of({**base, "init_type": "parser", "init_url": "https://i.com/"}) == \
        ("https://i.com/", "init_url")
    assert parent_of({**base, "init_type": "other"}) == ("https://site.vn/", "fallback")
    assert parent_of({"url": "https://site.vn/", "type": "Document"}) == (None, "none")


def test_fallback_parent_creates_no_edge():
    o = "https://site.vn/"
    rec = {"origin": o, "final_url": o, "requests": [
        {"url": o, "type": "Document", "init_type": "other", "doc": o},
        {"url": "https://t.com/p", "type": "Ping", "init_type": "other", "doc": o}]}
    res = resolve_site(rec)
    assert res.edges == set()
    assert res.methods == Counter({"fallback": 1})
    assert res.pair_depth == {"t.com": 1}


def test_cycle_terminates():
    """a.js est (à tort) déclaré initié par b.js et réciproquement : pas de boucle infinie."""
    o = "https://site.vn/"
    a, b = "https://a.com/a.js", "https://b.com/b.js"
    rec = {"origin": o, "final_url": o, "requests": [
        {"url": a, "type": "Script", "init_type": "script", "stack": [b]},
        {"url": b, "type": "Script", "init_type": "script", "stack": [a]}]}
    res = resolve_site(rec)
    assert set(res.pair_depth) == {"a.com", "b.com"}
    assert all(1 <= d <= 2 for d in res.pair_depth.values())


def test_long_chain_of_redirects():
    """Chaîne de 1 000 redirections : la remontée est une boucle, pas une récursion."""
    o = "https://site.vn/"
    urls = [f"https://t{i}.com/x" for i in range(1000)]
    reqs = [{"url": urls[0], "type": "Script", "init_type": "parser", "init_url": o}]
    reqs += [{"url": urls[i], "type": "Other", "redirect_from": urls[i - 1]} for i in range(1, 1000)]
    res = resolve_site({"origin": o, "final_url": o, "requests": reqs})
    assert res.pair_depth["t999.com"] == 1000


def test_synthetic_real_trackers(synth_records):
    res = resolve_site(synth_records[0])
    assert res.pair_depth == {"googletagmanager.com": 1, "google-analytics.com": 2,
                              "doubleclick.net": 3, "facebook.net": 2, "jsdelivr.net": 1}
    assert ("google-analytics.com", "doubleclick.net") in res.edges
    assert (FP_NODE, "jsdelivr.net") in res.edges


# --- Bibliothèques servies par un CDN public (défaut corrigé) ------------------
JQ = "https://code.jquery.com/jquery-3.7.1.min.js"
SITE = "https://tintuc.vn/"


def _jquery_site(stack):
    return {"origin": SITE, "final_url": SITE, "requests": [
        {"url": SITE, "type": "Document", "init_type": "other", "doc": SITE},
        {"url": JQ, "type": "Script", "init_type": "parser", "init_url": SITE, "doc": SITE},
        {"url": "https://px.tracker-vn.com/t.js", "type": "Script", "init_type": "script",
         "stack": stack, "doc": SITE}]}


def test_library_frames_are_skipped():
    """La page appelle $.getScript() : la pile commence dans jQuery (CDN), puis la page.
    Le responsable est la page : arête FP -> traceur, profondeur 1 (et non 2)."""
    res = resolve_site(_jquery_site([JQ, JQ, SITE]))
    assert res.edges == {(FP_NODE, "jquery.com"), (FP_NODE, "tracker-vn.com")}
    assert res.pair_depth["tracker-vn.com"] == 1


def test_without_skip_list_the_old_bias_reappears():
    res = resolve_site(_jquery_site([JQ, SITE]), library_hosts=frozenset())
    assert ("jquery.com", "tracker-vn.com") in res.edges
    assert res.pair_depth["tracker-vn.com"] == 2


def test_only_library_frames_keeps_first_frame():
    res = resolve_site(_jquery_site([JQ]))
    assert ("jquery.com", "tracker-vn.com") in res.edges
