"""Bout en bout : JSONL -> tables -> labels -> graphes -> classement, dans un dossier
temporaire, avec les vraies données de référence (Tracker Radar, EasyPrivacy)."""
import json

import numpy as np
import pyarrow.parquet as pq
import yaml

from tm.config import DEFAULT_CONFIG, repo_path
from tm.graph import build as graph_build
from tm.labels import labels as labels_step
from tm.parse import build_tables
from tm.rank import run as rank_run


def test_end_to_end(tmp_path, synth_records, bench_records):
    raw = tmp_path / "raw"
    raw.mkdir()
    with open(raw / "crawl.jsonl", "w") as fh:
        for r in synth_records + bench_records:
            fh.write(json.dumps(r) + "\n")
    cfg = yaml.safe_load(open(DEFAULT_CONFIG))
    cfg["paths"] = {"ref": str(repo_path("data/ref")), "raw": str(raw),
                    "interim": str(tmp_path / "interim"), "results": str(tmp_path / "results")}
    cfg["ref"] = {k: str(repo_path(v)) for k, v in cfg["ref"].items()}
    cfg["graph"]["co_min"] = 1
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    args = ["--config", str(cfg_path)]

    build_tables.main(args)
    labels_step.main(args)
    graph_build.main(args)
    rank_run.main(args)

    interim, results = tmp_path / "interim", tmp_path / "results"
    for f in ["sites", "requests", "site_domain", "edges_inc", "cookies", "labels", "nodes",
              "sites_index", "ranks"]:
        assert (interim / f"{f}.parquet").exists(), f
    for f in ["tables_summary", "labels_summary", "graph_summary", "rank_summary"]:
        doc = json.load(open(results / f"{f}.json"))
        assert doc["config"]["seed"] == cfg["seed"]

    tables = json.load(open(results / "tables_summary.json"))
    assert tables["n_sites"] == 6 and tables["n_usable"] == 4

    lab = {r["domain"]: r["label"] for r in pq.read_table(interim / "labels.parquet").to_pylist()}
    assert lab["google-analytics.com"] == "tracking"
    assert lab["jsdelivr.net"] == "non_tracking"
    assert lab["adbench-vn-unknown.com"] == "unknown"

    ranks = pq.read_table(interim / "ranks.parquet").to_pandas().set_index("domain")
    assert np.isclose(ranks.pagerank_site.sum(), 1.0) and np.isclose(ranks.pagerank_uniform.sum(), 1.0)
    # PageRank uniforme : doubleclick (collecteur pendant) devance GTM (aucun lien entrant tiers)
    assert ranks.loc["doubleclick.net", "pagerank_uniform"] > ranks.loc["googletagmanager.com", "pagerank_uniform"]
    # PageRank ancré : GTM, chargé directement par 3 sites, devance un tiers vu sur 1 seul site
    assert ranks.loc["googletagmanager.com", "pagerank_site"] > ranks.loc["adbench-vn-unknown.com", "pagerank_site"]
    assert ranks.loc["googletagmanager.com", "hub"] == ranks.hub.max()
    # confiance implicite : doubleclick n'est jamais inclus directement
    assert ranks.loc["doubleclick.net", "implicit_share"] == 1.0
    assert ranks.loc["googletagmanager.com", "implicit_share"] == 0.0
    summ = json.load(open(results / "rank_summary.json"))
    assert summ["pagerank_site"]["teleport"] == "fp_loads"
