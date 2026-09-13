"""Canonical filesystem layout and config loading.

Every stage resolves its paths here so the pipeline can be relocated by
setting AALAM_ROOT rather than editing modules. This mirrors
``src/elitenet/paths.py``; the tests rely on the env override to run a stage
against a synthetic tree.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("AALAM_ROOT", Path(__file__).resolve().parents[2]))

CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw" / "aalam"
INTERIM = DATA / "interim" / "aalam"

# Namespaced under data/processed/ like every other build in this repository.
# Three other builds already write events/spells tables; keeping the output
# trees apart lets all four coexist rather than one overwriting another.
BUILD = "aalam-tunisiyun"
PROCESSED = DATA / "processed" / BUILD
GOLD = ROOT / "gold"
DOCS = ROOT / "docs"

# Per-page OCR text and the manifest that makes it verifiable. The page text is
# committed (it is small, ~700 KB gzipped) so that CI can rebuild and byte-diff
# the tables without running an OCR engine.
PAGES = RAW / "pages"
MANIFEST = RAW / "manifest.csv"
PDF = RAW / "book.pdf"


def ensure_dirs() -> None:
    for d in (RAW, PAGES, INTERIM, PROCESSED, GOLD, DOCS):
        d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=None)
def load_config(name: str) -> dict:
    """Load and cache a YAML config by stem, e.g. load_config('aalam_scope')."""
    path = CONFIG / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def page_text_path(pdf_page: int) -> Path:
    """Local path for one page's OCR text. PDF page index is 1-based."""
    return PAGES / f"p{pdf_page:03d}.txt"
