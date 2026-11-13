"""Intégration : vrai Chromium + banc local -> les chaînes reconstruites
correspondent à la vérité terrain. Lent (~30 s) : lancé par `make test-all`
ou `pytest -m browser`."""
import json
import subprocess
import sys
import threading

import pytest

from tm.parse.resolve import resolve_site

from test_resolve import EXPECTED_DEPTH, EXPECTED_EDGES  # noqa: E402


@pytest.mark.browser
def test_crawler_reconstructs_bench_chains(tmp_path):
    pytest.importorskip("playwright")
    from bench_server import make_server

    srv = make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_port
    sites = tmp_path / "sites.txt"
    sites.write_text(f"http://news-bench.vn:{port}/\t1000\tnews-bench.vn\n"
                     f"http://cf-bench.vn:{port}/\t1000\tcf-bench.vn\n")
    out = tmp_path / "crawl.jsonl"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "tm.crawl.crawl", "--sites", str(sites), "--out", str(out),
             "--concurrency", "2", "--timeout", "10", "--wait-after-load", "2",
             "--host-rules", "MAP * 127.0.0.1"], capture_output=True, text=True, timeout=120)
    finally:
        srv.shutdown()
    if "Executable doesn't exist" in proc.stderr:
        pytest.skip("Chromium Playwright non installé (python -m playwright install chromium)")
    assert proc.returncode == 0, proc.stderr[-2000:]
    recs = {json.loads(l)["origin"].split(":")[1].strip("/"): json.loads(l)
            for l in out.read_text().splitlines()}
    assert recs["cf-bench.vn"].get("challenge") is True
    res = resolve_site(recs["news-bench.vn"])
    assert res.pair_depth == EXPECTED_DEPTH
    assert res.edges == EXPECTED_EDGES
