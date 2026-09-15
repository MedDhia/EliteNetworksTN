"""Canonical filesystem layout for the rodovid build.

Every stage resolves its paths here rather than off the working directory, so
``python -m rodovid.build`` runs the same from anywhere and the tree can be
relocated by setting RODOVID_ROOT. This mirrors ``src/aalam/paths.py``.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("RODOVID_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
DOCS = ROOT / "docs"
FIGS = ROOT / "figures"

# Namespaced under data/processed/ like every other build in this repository.
BUILD = "rodovid"
PROCESSED = DATA / "processed" / BUILD

# The two workbook sheets, dumped to CSV once and committed, so the build runs
# on the standard library alone with no Excel reader in the dependency list.
SOURCE = PROCESSED / "source"
SRC_INDIVIDUALS = SOURCE / "rodovid_individuals.csv.gz"
SRC_TIES = SOURCE / "rodovid_ties.csv.gz"

# Person level, written by rodovid.build.
INDIVIDUALS = PROCESSED / "tunisian_individuals.csv"
TIES = PROCESSED / "tunisian_ties.csv"
EXCLUDED = PROCESSED / "excluded_individuals.csv"

# Family level, written by rodovid.families.
FAMILY_NODES = PROCESSED / "family_nodes.csv"
FAMILY_ALLIANCES = PROCESSED / "family_alliances.csv"

# Dated, written by rodovid.dynamic. The marriages are undated in the source;
# these carry years derived from birth years, with the provenance of each.
PERSON_YEARS = PROCESSED / "person_years.csv"
MARRIAGES = PROCESSED / "marriages_dated.csv"
ALLIANCE_PANEL = PROCESSED / "alliance_panel.csv"
EVOLUTION = PROCESSED / "network_evolution.csv"

# The three plates, written by rodovid.figures.
FIG_ALLIANCES = "fig01_rodovid_alliances"
FIG_CORE = "fig02_rodovid_alliance_core"
FIG_NULL = "fig03_rodovid_alliance_null"


def ensure_dirs() -> None:
    for d in (PROCESSED, SOURCE, FIGS):
        d.mkdir(parents=True, exist_ok=True)
