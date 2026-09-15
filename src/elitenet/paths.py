"""Canonical filesystem layout and config loading.

Every stage resolves its paths here so the pipeline can be relocated by
setting ELITENET_ROOT rather than editing modules.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from functools import lru_cache

import yaml

ROOT = Path(os.environ.get("ELITENET_ROOT", Path(__file__).resolve().parents[2]))

CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"

# This build is namespaced under data/processed/ so it can coexist with the
# others rather than overwriting their tables; several would otherwise write
# events.csv.gz to the same place. The name carries no window: it used to be
# "multiplex-2008-2012", which stopped being true the moment the window was
# widened, and the window now lives in config/scope.yaml where it belongs.
#
# What distinguishes the builds is *what* they extract, not when. This one is
# relational and multiplex: it resolves gazette mentions onto the curated seed
# network dyad by dyad. src/eltn reads the journal officiel alone for
# bureaucratic office-holding, the bourse component reads CMF filings for
# listed-company boards and ownership, src/aalam reads the A'lam Tunisiyun
# biographical dictionary, and src/rodovid reads the Rodovid genealogies.
BUILD = "multiplex"
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


def window() -> tuple[date, date]:
    """The dataset's temporal window, from config/scope.yaml.

    Every stage that needs the window reads it here. It used to be a literal in
    four modules, which meant "the window is a config value" was not true: the
    panel periods, the networkDynamic time origin and the validator's range all
    had to be edited by hand to agree with the config, and nothing checked that
    they did.
    """
    w = load_config("scope")["window"]
    return (date.fromisoformat(w["start"]), date.fromisoformat(w["end"]))


def window_years() -> list[int]:
    """Years in the window, derived rather than listed.

    scope.yaml may still carry an explicit `years` list; if present it must
    agree with the window, because a disagreement silently mirrors one range
    and analyses another.
    """
    start, end = window()
    derived = list(range(start.year, end.year + 1))
    listed = load_config("scope")["window"].get("years")
    if listed and [int(y) for y in listed] != derived:
        raise ValueError(
            f"scope.yaml window {start.year}-{end.year} implies "
            f"{len(derived)} years but `years` lists {len(listed)}"
        )
    return derived


def issue_md_path(collection: str, lang: str, year: int | str, issue: str) -> Path:
    """Local path mirroring the upstream OCR markdown URL structure."""
    return RAW / collection / lang / str(year) / f"{issue}.md"
