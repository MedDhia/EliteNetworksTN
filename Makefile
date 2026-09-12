# Longitudinal Tunisian elite network, 2008-2012.
# Stages are ordered; each writes its outputs under data/ and can be re-run
# independently once the stages it depends on have completed.

PY := PYTHONPATH=src python3

.PHONY: all seed mirror calendar segment extract resolve spells orgties orgattrs export tergm codebook validate test clean-derived

all: seed mirror calendar segment extract resolve spells orgties orgattrs export tergm codebook validate

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

orgties:   ## build the organisation-to-organisation tie layer
	$(PY) -m elitenet.orgties

orgattrs:  ## organisation identifiers (tax ID, RC number) and addresses
	$(PY) -m elitenet.orgattrs

tergm:     ## re-index the yearly panel into TERGM-estimable inputs
	$(PY) -m elitenet.tergm

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

# ---------------------------------------------------------------------------
# bourse: listed companies, shareholders and boards from BVMT + CMF filings.
# Independent of the JORT stages above; shares only the data/ root.
# ---------------------------------------------------------------------------

BPY := PYTHONPATH=src python3

.PHONY: bourse bourse-spine bourse-crawl bourse-resolve bourse-fetch \
        bourse-extract bourse-build bourse-export bourse-validate bourse-test

bourse: bourse-spine bourse-crawl bourse-resolve bourse-fetch bourse-extract \
        bourse-build bourse-export bourse-validate

bourse-spine:    ## BVMT listed-securities roster (firm identity spine)
	$(BPY) -m bourse.bvmt

bourse-crawl:    ## list CMF filings into the document registry
	$(BPY) -m bourse.cmf_crawl --max-pages 60

bourse-resolve:  ## resolve each filing's PDF link (slow; resumable)
	$(BPY) -m bourse.cmf_crawl --resolve

bourse-fetch:    ## download registration-document PDFs (~2 GB)
	$(BPY) -m bourse.fetch_docs --doc-types document_de_reference

bourse-extract:  ## parse tables into typed records (slow; parallel)
	$(BPY) -m bourse.pipeline --doc-types document_de_reference

bourse-build:    ## assemble entities and multiplex edge lists
	$(BPY) -m bourse.build_dataset

bourse-export:   ## write muxViz edge lists and yearly GraphML
	$(BPY) -m bourse.export_networks
	$(BPY) -m bourse.export_networks --panel

bourse-validate: ## integrity checks -> validation_report.md
	$(BPY) -m bourse.validate

bourse-test:     ## parser and entity-resolution unit tests
	$(BPY) tests/test_bourse_extract.py
