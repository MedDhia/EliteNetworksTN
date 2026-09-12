# Longitudinal Tunisian elite network, 2008-2012.
# Stages are ordered; each writes its outputs under data/ and can be re-run
# independently once the stages it depends on have completed.

PY := PYTHONPATH=src python3

.PHONY: all seed mirror calendar segment extract resolve spells export codebook validate test clean-derived

all: seed mirror calendar segment extract resolve spells export codebook validate

seed:      ## ingest and clean the curated seed edge list
	$(PY) -m elitenet.seed

mirror:    ## download the French OCR markdown for issues in scope
	$(PY) -m elitenet.mirror

calendar:  ## resolve each issue to a publication date
	$(PY) -m elitenet.calendar

segment:   ## split issues into announcement blocks and state acts
	$(PY) -m elitenet.segment

extract:   ## pull dated relational events out of blocks and acts
	$(PY) -m elitenet.extract

resolve:   ## link mentions to the seed network on the (person, org) dyad
	$(PY) -m elitenet.resolve

spells:    ## build tie spells and panel snapshots
	$(PY) -m elitenet.spells

export:    ## write SQLite, dynamic GEXF, networkDynamic and snapshot files
	$(PY) -m elitenet.export

codebook:  ## regenerate CODEBOOK.md from the data and config
	$(PY) -m elitenet.codebook

validate:  ## consistency checks, coverage and held-out ground truth
	$(PY) -m elitenet.validate

test:      ## parser unit tests on committed fixtures
	$(PY) -m pytest tests/ -q

verify-mirror: ## re-check every mirrored file against the upstream ETag (one HEAD each)
	$(PY) -m elitenet.mirror --verify

clean-derived: ## remove everything derived, keeping the raw mirror
	rm -rf data/interim data/processed
