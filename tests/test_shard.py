from tm.crawl.shard import main, shard_of


def test_shard_is_deterministic():
    # md5 : même résultat d'un processus à l'autre (contrairement à hash())
    assert shard_of("https://vnexpress.net", 4) == shard_of("https://vnexpress.net", 4)
    assert 0 <= shard_of("https://vnexpress.net", 4) < 4


def test_shards_partition_the_input(tmp_path):
    lines = [f"https://site{i}.vn\t{1000 if i % 2 else 5000}\tsite{i}.vn" for i in range(400)]
    src = tmp_path / "sites.txt"
    src.write_text("\n".join(lines) + "\n")
    main([str(src), "--k", "4", "--outdir", str(tmp_path / "out")])
    parts = [set((tmp_path / "out" / f"sites_shard_{i}.txt").read_text().split("\n")) - {""}
             for i in range(4)]
    assert set().union(*parts) == set(lines)                       # couverture
    assert sum(len(p) for p in parts) == len(lines)                # disjonction
    assert all(60 <= len(p) <= 140 for p in parts)                 # équilibre grossier (400/4 = 100)


def test_failed_lists_non_usable_except_challenges(tmp_path):
    from pathlib import Path

    from tm.crawl.failed import main as failed_main
    fix = Path(__file__).parent / "fixtures" / "crawl_bench.jsonl"
    out = tmp_path / "retry.txt"
    failed_main([str(fix), "--out", str(out)])
    assert out.read_text().split("\t")[0] == "http://slow-bench.vn:8765/"     # cf-bench = challenge
