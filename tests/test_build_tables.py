import gzip
import json

import pyarrow.parquet as pq

from tm.io import iter_crawl_dir
from tm.parse.build_tables import SCHEMAS, build, summarize, write_tables
from tm.parse.resolve import FP_NODE


def edges_dict(t):
    return {(e["parent"], e["child"]): e["n_sites"] for e in t["edges_inc"]}


def test_usable_filter_on_bench(bench_records):
    t = build(bench_records, min_requests=2)
    by = {s["origin"]: s for s in t["sites"]}
    assert len(t["sites"]) == 3
    assert by["http://cf-bench.vn:8765/"]["usable"] is False        # challenge anti-bot
    assert by["http://slow-bench.vn:8765/"]["usable"] is False      # 1 seule requête
    assert by["http://news-bench.vn:8765/"]["usable"] is True
    assert by["http://news-bench.vn:8765/"]["n_tp_domains"] == 8
    assert summarize(t)["success_rate"] == round(1 / 3, 4)


def test_requests_only_for_usable_sites(bench_records):
    t = build(bench_records)
    assert {r["origin"] for r in t["requests"]} == {"http://news-bench.vn:8765/"}
    assert len(t["requests"]) == 12


def test_edges_aggregated_across_sites(synth_records):
    e = edges_dict(build(synth_records))
    assert e[("googletagmanager.com", "google-analytics.com")] == 3     # 3 sites
    assert e[("google-analytics.com", "doubleclick.net")] == 2          # s3 sans doubleclick
    assert e[(FP_NODE, "googletagmanager.com")] == 3
    assert e[("facebook.net", "adbench-vn-unknown.com")] == 1


def test_site_domain_and_cookies(synth_records):
    t = build(synth_records)
    sd = {(r["origin"], r["domain"]): r for r in t["site_domain"]}
    dc = sd[("https://tinbench.vn/", "doubleclick.net")]
    assert dc["min_depth"] == 3 and dc["sets_cookie"] is True and dc["types"] == ["Image"]
    assert sd[("https://shopbench.com.vn/", "doubleclick.net")]["sets_cookie"] is False
    ck = {c["name"]: c for c in t["cookies"]}
    assert abs(ck["IDE"]["ttl_days"] - 30.0) < 1e-9 and ck["IDE"]["is_third_party"] is True
    assert ck["sess"]["ttl_days"] is None and ck["sess"]["is_third_party"] is False


def test_parquet_roundtrip_respects_schemas(tmp_path, synth_records):
    t = build(synth_records)
    write_tables(t, tmp_path)
    for name, schema in SCHEMAS.items():
        tbl = pq.read_table(tmp_path / f"{name}.parquet")
        assert tbl.schema.equals(schema), name
        assert tbl.num_rows == len(t[name])


def test_empty_input_writes_empty_typed_tables(tmp_path):
    t = build([])
    write_tables(t, tmp_path)
    assert pq.read_table(tmp_path / "edges_inc.parquet").schema.equals(SCHEMAS["edges_inc"])


def test_iter_crawl_dir_dedup_keeps_last_usable(tmp_path, synth_records):
    good = synth_records[0]
    bad = {**good, "status": "error", "requests": []}
    (tmp_path / "a.jsonl").write_text(json.dumps(good) + "\n" + "{tronqué\n")
    with gzip.open(tmp_path / "b.jsonl.gz", "wt") as fh:      # 2e passe ratée : ne doit pas écraser
        fh.write(json.dumps(bad) + "\n")
    recs = list(iter_crawl_dir([tmp_path]))
    assert len(recs) == 1 and recs[0]["status"] == "ok"
