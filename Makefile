# Raccourcis du pipeline. Sans make (Windows), lancer la commande python indiquée.
PY     ?= python
CFG    ?= config.yaml
K      ?= 4
SHARD  ?= 0
CONC   ?= 4

.PHONY: help install test test-all pilot shards crawl retry tables labels graphs rank pipeline clean

help:
	@echo "install | test | test-all | pilot | shards | crawl SHARD=i | retry | pipeline | clean"

install:
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m playwright install chromium

test:                    # tests rapides
	$(PY) -m pytest -q

test-all:                # + le test qui lance Chromium
	$(PY) -m pytest -q -m "browser or not browser"

# E0 : pilote
pilot:
	$(PY) -m tm.crawl.crawl --sites data/ref/sites_pilot.txt --out data/raw/pilot/crawl_pilot.jsonl --concurrency $(CONC)
	$(PY) -m tm.feasibility.analyze data/raw/pilot/crawl_pilot.jsonl \
	  --tracker-radar data/ref/tracker_radar_index.json --easyprivacy data/ref/easyprivacy.txt \
	  --concurrency $(CONC) --outdir results/pilot

# E2 : crawl complet, en 4 lots
shards:
	$(PY) -m tm.crawl.shard data/ref/sites_top.txt --k $(K) --outdir data/raw/shards

crawl:                   # make crawl SHARD=0
	$(PY) -m tm.crawl.crawl --sites data/raw/shards/sites_shard_$(SHARD).txt \
	  --out data/raw/full/crawl_shard_$(SHARD).jsonl --concurrency $(CONC)

retry:                   # 2e passe sur les échecs
	$(PY) -m tm.crawl.failed data/raw/full --out data/raw/retry_sites.txt
	$(PY) -m tm.crawl.crawl --sites data/raw/retry_sites.txt --out data/raw/full/crawl_retry.jsonl \
	  --timeout 45 --concurrency 2

# E3 -> E6
tables:
	$(PY) -m tm.parse.build_tables --config $(CFG) --crawl data/raw/full
labels:
	$(PY) -m tm.labels.labels --config $(CFG)
graphs:
	$(PY) -m tm.graph.build --config $(CFG)
rank:
	$(PY) -m tm.rank.run --config $(CFG)

pipeline: tables labels graphs rank

clean:
	rm -rf data/interim/*
