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

# ---------------------------------------------------------------------------
# bourse: listed companies, shareholders and boards from BVMT + CMF filings.
# Independent of the JORT stages above; shares only the data/ root.
# ---------------------------------------------------------------------------

BPY := PYTHONPATH=src python3

.PHONY: bourse bourse-spine bourse-crawl bourse-resolve bourse-fetch \
        bourse-extract bourse-ocr bourse-movements bourse-resolutions \
        bourse-build bourse-export bourse-validate bourse-verify bourse-test

# bourse-ocr is deliberately out of the default chain: it needs tesseract-ocr
# with the French model installed, and it takes hours. Run it explicitly.
bourse: bourse-spine bourse-crawl bourse-resolve bourse-fetch bourse-extract \
        bourse-movements bourse-resolutions bourse-build bourse-export \
        bourse-validate

bourse-spine:    ## BVMT listed-securities roster (firm identity spine)
	$(BPY) -m bourse.bvmt

bourse-crawl:    ## list CMF filings into the document registry
	$(BPY) -m bourse.cmf_crawl --max-pages 60

bourse-resolve:  ## resolve each filing's PDF link (slow; resumable)
	$(BPY) -m bourse.cmf_crawl --resolve

bourse-fetch:    ## download registration documents and movement notices
	$(BPY) -m bourse.fetch_docs --doc-types document_de_reference
	$(BPY) -m bourse.fetch_docs --doc-types offre_publique \
	        operation_sur_capital augmentation_de_capital
	$(BPY) -m bourse.fetch_docs --doc-types resolutions_ag
	$(BPY) -m bourse.fetch_docs --doc-types rapport_annuel
	$(BPY) -m bourse.fetch_docs --doc-types prospectus

bourse-extract:  ## parse tables into typed records (slow; parallel)
	$(BPY) -m bourse.pipeline --doc-types document_de_reference
	$(BPY) -m bourse.pipeline --doc-types rapport_annuel --skip-processed
	$(BPY) -m bourse.pipeline --doc-types prospectus --skip-processed

bourse-ocr:      ## read the scanned filings by OCR (very slow; needs tesseract)
	$(BPY) -m bourse.pipeline --ocr --only-scanned --skip-processed \
	        --doc-types document_de_reference rapport_annuel prospectus

bourse-movements: ## parse dated operations out of CMF notices
	$(BPY) -m bourse.movements_pipeline

bourse-resolutions: ## parse dated board decisions out of AGM resolutions
	$(BPY) -m bourse.resolutions_pipeline

bourse-build:    ## assemble entities and multiplex edge lists
	$(BPY) -m bourse.build_dataset

bourse-export:   ## write muxViz edge lists and yearly GraphML
	$(BPY) -m bourse.export_networks
	$(BPY) -m bourse.export_networks --panel

bourse-validate: ## integrity checks -> validation_report.md
	$(BPY) -m bourse.validate

bourse-verify:   ## re-read the filings and check every record against the page it cites
	$(BPY) -m bourse.verify_source

bourse-test:     ## parser and entity-resolution unit tests
	$(BPY) tests/test_bourse_extract.py

# --- aalam-tunisiyun --------------------------------------------------------
# A fourth build, independent of the three above and sharing only the data/
# root. Source: Sadok Zmerli, *A'lam Tunisiyun* (Dar al-Gharb al-Islami, 2000),
# 38 biographical essays on the Tunisian elite of roughly 1606-1973.
#
# Unlike the other three this one reads a printed book, so the first stage is
# an OCR pass rather than an HTTP mirror. The scan is not redistributed:
# `aalam-fetch` pulls it from the Internet Archive and checks it against a
# pinned sha256 before anything downstream runs.
APY := PYTHONPATH=src python3

.PHONY: aalam aalam-fetch aalam-ingest aalam-segment aalam-extract aalam-model \
        aalam-relations aalam-codebook aalam-validate aalam-test

aalam: aalam-segment aalam-extract aalam-model aalam-relations aalam-codebook aalam-validate

aalam-fetch:      ## download the scan and verify it against the pinned digest
	$(APY) -m aalam.ingest --fetch --limit 0
aalam-ingest:     ## OCR every page at native resolution, write the page manifest
	$(APY) -m aalam.ingest
aalam-segment:    ## cut the volume into its 38 entries using the printed contents
	$(APY) -m aalam.segment
aalam-extract:    ## rule pass: cue table over clause-sized spans
	$(APY) -m aalam.extract
aalam-model:      ## model pass: verify committed assertions quote their entry
	$(APY) -m aalam.llm --strict
aalam-relations:  ## registers and the layered edge list
	$(APY) -m aalam.relations
aalam-codebook:   ## regenerate the codebook from the data and config
	$(APY) -m aalam.codebook
aalam-validate:   ## consistency, coverage and the verbatim-quote guard
	$(APY) -m aalam.validate --strict
aalam-test:       ## parser and normalisation tests
	$(APY) -m pytest tests/test_names_aalam.py tests/test_extract_aalam.py -q
