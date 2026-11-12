"""Fixtures partagées.

- bench_records : vraie sortie du crawler sur le banc local (tests/fixtures/crawl_bench.jsonl),
  enregistrée avec Chromium ; vérité terrain dans bench/bench_server.py.
- synth_records : 3 sites synthétiques avec de VRAIS domaines de traceurs, construits
  à la main pour que chaque nombre attendu dans les tests soit calculable de tête.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "bench"))

TS = 1_790_000_000.0          # horodatage fixe de "crawl"
GTM = "https://www.googletagmanager.com/gtm.js"
GA = "https://www.google-analytics.com/analytics.js"
DC = "https://stats.g.doubleclick.net/g/collect"
FB = "https://connect.facebook.net/en_US/fbevents.js"
CDN = "https://cdn.jsdelivr.net/npm/lib.js"
UNK = "https://px.adbench-vn-unknown.com/p"


def req(i, url, typ, init_type, init_url=None, stack=None, redirect_from=None, doc=None):
    return {"id": str(i), "url": url, "type": typ, "init_type": init_type, "init_url": init_url,
            "stack": stack or [], "redirect_from": redirect_from, "doc": doc, "method": "GET"}


def site(origin, extra=(), cookies=(), gtm=True, ga=True, dc=True, fb=True, cdn=True):
    r = [req(0, origin, "Document", "other", doc=origin)]
    if gtm:
        r.append(req(1, GTM, "Script", "parser", init_url=origin, doc=origin))
    if ga:
        r.append(req(2, GA, "Script", "script", stack=[GTM], doc=origin))
    if dc:
        r.append(req(3, DC, "Image", "script", stack=[GA], doc=origin))
    if fb:
        r.append(req(4, FB, "Script", "script", stack=[GTM], doc=origin))
    if cdn:
        r.append(req(5, CDN, "Script", "parser", init_url=origin, doc=origin))
    r += list(extra)
    return {"origin": origin, "rank": "1000", "site": None, "status": "ok", "error": None,
            "final_url": origin, "title": "t", "requests": r, "cookies": list(cookies),
            "duration_s": 10.0, "ts": TS}


def synth():
    s1 = site("https://tinbench.vn/", cookies=[
        {"domain": ".doubleclick.net", "name": "IDE", "expires": TS + 30 * 86400,
         "httpOnly": True, "sameSite": "None"},
        {"domain": "tinbench.vn", "name": "sess", "expires": -1, "httpOnly": False, "sameSite": "Lax"}])
    s2 = site("https://shopbench.com.vn/", extra=[
        req(6, UNK, "Image", "script", stack=[FB], doc="https://shopbench.com.vn/")])
    s3 = site("https://blogbench.vn/", dc=False, fb=False, cdn=False)
    return [s1, s2, s3]


@pytest.fixture
def synth_records():
    return synth()


@pytest.fixture
def bench_records():
    return [json.loads(l) for l in open(FIX / "crawl_bench.jsonl", encoding="utf-8")]


@pytest.fixture
def news_record(bench_records):
    return next(r for r in bench_records if "news-bench" in r["origin"])
