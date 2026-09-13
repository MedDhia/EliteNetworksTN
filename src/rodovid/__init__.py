"""Tunisian elite genealogies from a rodovid.org crawl.

A fifth build, independent of the other four and sharing only the ``data/``
root. Where the gazette, bourse and A'lam builds read institutional records and
a printed book, this one reads a user-edited genealogy wiki, and the relation
it carries is kinship: parent, sibling and spouse, collapsed to marriage
alliances between families.

Four stages, in order::

    python -m rodovid.build       # the Tunisian subset of the export
    python -m rodovid.families    # people -> families
    python -m rodovid.audit       # what the figures may be read to say
    python -m rodovid.figures     # the three network plates (needs matplotlib)

The first three are stdlib-only and deterministic; see
``docs/CODEBOOK-rodovid.md`` for what they produce and
``docs/LIMITATIONS-rodovid.md`` for what it cannot support.
"""
