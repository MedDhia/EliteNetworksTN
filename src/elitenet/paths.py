"""Canonical filesystem layout and config loading.

Every stage resolves its paths here so the pipeline can be relocated by
setting ELITENET_ROOT rather than editing modules.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

import yaml

ROOT = Path(os.environ.get("ELITENET_ROOT", Path(__file__).resolve().parents[2]))

CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"

# This build is namespaced under data/processed/. The repository already carries
# a separate journal-officiel-only build of bureaucratic elites covering
# 1957-2026; keeping the two output trees apart lets them coexist rather than
# one overwriting the other's tables (both would otherwise write events.csv.gz).
BUILD = "multiplex-2008-2012"
PROCESSED = DATA / "processed" / BUILD
GOLD = ROOT / "gold"
DOCS = ROOT / "docs"

MANIFEST = RAW / "manifest.csv"


def ensure_dirs() -> None:
    for d in (RAW, INTERIM, PROCESSED, GOLD, DOCS):
        d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=None)
def load_config(name: str) -> dict:
    """Load and cache a YAML config by stem, e.g. load_config('scope')."""
    path = CONFIG / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def issue_md_path(collection: str, lang: str, year: int | str, issue: str) -> Path:
    """Local path mirroring the upstream OCR markdown URL structure."""
    return RAW / collection / lang / str(year) / f"{issue}.md"
