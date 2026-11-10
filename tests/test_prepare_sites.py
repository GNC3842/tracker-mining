import gzip
import json

from tm.crawl.prepare_sites import ADULT, dedup, main, public_suffix, stratified_pilot

CSV = """origin,rank
https://www.animevietsub.mom,1000
https://animevietsub.mom,1000
https://m.f8bet195.cc,1000
https://www.f8bet195.cc,5000
https://vnexpress.net,1000
https://m.vnexpress.net,1000
https://shop.com.vn,5000
https://onlyfans.com,1000
https://vi.stripchat.com,1000
https://user.github.io,5000
https://far.vn,50000
"""


def test_adult_filter_has_no_trailing_space_bug():
    assert ADULT.search("https://onlyfans.com")
    assert ADULT.search("https://vi.stripchat.com")
    assert not ADULT.search("https://vnexpress.net")


def test_dedup_merges_www_and_bare_on_unlisted_suffixes():
    rows = [(l.split(",")[0], int(l.split(",")[1])) for l in CSV.strip().splitlines()[1:]]
    seen, excluded = dedup(rows)
    assert excluded == 2
    assert set(seen) == {"animevietsub.mom", "f8bet195.cc", "vnexpress.net", "shop.com.vn",
                         "user.github.io", "far.vn"}
    assert seen["f8bet195.cc"][0] == "https://m.f8bet195.cc"        # meilleur palier gagne (1000 < 5000)
    assert seen["vnexpress.net"][0] == "https://vnexpress.net"      # à palier égal, origine « propre »


def test_public_suffix():
    assert public_suffix("shop.com.vn") == "com.vn"
    assert public_suffix("doubleclick.net") == "net"
    assert public_suffix("127.0.0.1") == "127.0.0.1"


def test_stratified_allocation_by_hand():
    kept = [(f"https://a{i}.vn", 1000, f"a{i}.vn") for i in range(770)] + \
           [(f"https://b{i}.vn", 5000, f"b{i}.vn") for i in range(3128)] + \
           [(f"https://c{i}.vn", 10000, f"c{i}.vn") for i in range(3767)]
    pilot = stratified_pilot(kept, 200, 42)
    counts = {b: sum(1 for _, r, _ in pilot if r == b) for b in (1000, 5000, 10000)}
    assert counts == {1000: 20, 5000: 82, 10000: 98}                # 20,1 / 81,6 / 98,3 arrondis
    assert pilot == stratified_pilot(kept, 200, 42)                 # reproductible


def test_main_accepts_csv_and_gz(tmp_path):
    (tmp_path / "c.csv").write_text(CSV)
    with gzip.open(tmp_path / "c.csv.gz", "wt") as fh:
        fh.write(CSV)
    for name in ("c.csv", "c.csv.gz"):
        out = tmp_path / name.replace(".", "_")
        main([str(tmp_path / name), "--max-rank", "10000", "--pilot", "3", "--outdir", str(out)])
        stats = json.loads((out / "sites_stats.json").read_text())
        assert stats["unique_registrable_domains"] == 5               # far.vn hors fenêtre
        assert stats["excluded_adult_keyword"] == 2
        lines = (out / "sites_top.txt").read_text().splitlines()
        assert len(lines) == 5 and all(len(l.split("\t")) == 3 for l in lines)
