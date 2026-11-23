# Tracker-mining - IT4868E Web Mining capstone

**Mining the Third-Party Web in Vietnam: Tracker Ecosystem Discovery via Inclusion-Graph Analysis**

We crawl the home page of ~7,600 popular Vietnamese sites, record which domain
loads which other domain, build graphs out of it and rank the nodes with
PageRank and HITS.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install chromium
pytest -q
```

Python 3.10 or newer.

## Run the pipeline

| Step | Command | Output |
|---|---|---|
| E0 pilot | `make pilot` | `results/pilot/report.md` (GO / NO-GO) |
| E2 shards | `make shards` | `data/raw/shards/sites_shard_{0..3}.txt` |
| E2 crawl | `make crawl SHARD=0` (then 1, 2, 3) | `data/raw/full/crawl_shard_i.jsonl` |
| E2 retry | `make retry` | `data/raw/full/crawl_retry.jsonl` |
| E3 tables | `make tables` | `data/interim/*.parquet` |
| E4 labels | `make labels` | `data/interim/labels.parquet` |
| E5 graphs | `make graphs` | `data/interim/g_inc.npz`, `g_co.npz`, `nodes.parquet` |
| E6 ranking | `make rank` | `data/interim/ranks.parquet`, `results/rank_summary.json` |

`make pipeline` runs E3 to E6. Without `make`, every target is a single
`python -m tm.<module>` command, listed in the `Makefile`.

The shards are disjoint, so the crawl can be split between the two of us, and
restarting a crawl with the same `--out` resumes where it stopped. Each step
writes a JSON file in `results/` together with the config used, so every number
in the report can be traced back to one of those files.

## Layout

```
config.yaml        all parameters (thresholds, damping, seed)
src/tm/
  domains.py       registrable domain (eTLD+1) via the Public Suffix List
  io.py            read crawl JSONL, write result JSON
  crawl/           Playwright crawler, site list, shards, retry list
  parse/           request parent, third-party depth, inclusion edges, Parquet tables
  labels/          labelling rules (Tracker Radar + EasyPrivacy)
  graph/           inclusion graph, co-occurrence graph, bipartite matrix
  rank/            PageRank and HITS, written from the course formulas
  feasibility/     pilot report, Cohen's kappa
tests/             pytest
bench/             local test server, used as ground truth by the tests
data/ref/          reference data (site lists, Tracker Radar index, EasyPrivacy)
data/raw/, data/interim/   not versioned (large, regenerable)
```

## Working rules

- One branch per step, reviewed by the other member before merging into `main`.
- `pytest -q` must pass before merging, and any new computation comes with a
  test whose expected value can be computed by hand.
- Only `labels/`, `feasibility/` and `tools/` may read the labels
  (`tests/test_leakage.py` checks it), otherwise labels leak into the features.
- Raw crawl data is never committed.

## Data sources

- Site list: CrUX top lists per country (`github.com/zakird/crux-top-lists`),
  Vietnam snapshot 2026-09.
- DuckDuckGo Tracker Radar, CC BY-NC-SA 4.0, non-commercial academic use
  (`data/ref/TRACKER_RADAR_LICENSE.txt`). The compact index is built with
  `python -m tm.tools.build_tracker_radar_index <tracker-radar> data/ref/tracker_radar_index.json`.
- EasyPrivacy (`github.com/easylist/easylist`): only the plain-domain rules are kept.
