"""Arabic OCR cleaning and the two-key normalisation discipline.

Every rule here was chosen by comparing tesseract's output against pages
transcribed by eye, not by guessing at what an OCR engine might do. The
engine's errors on this volume are systematic: they fall on function words,
on the alif-maqsura/ya and ta-marbuta/ha pairs, and on punctuation (an Arabic
comma is frequently read as a guillemet or a stray hamza). Proper names, which
are what the extractor needs, come through intact.

The central rule, carried over from ``src/elitenet/names.py``, is that there
are **two keys, never one**:

``display``  keeps the text as printed, diacritics and orthography intact. It
             is what an evidence quote is checked against and what a reader
             sees.
``match``    folds the variants an OCR engine and a typesetter move between.
             It is used for comparison and blocking only.

Identifiers hash the identity key, never the match key: folding alif variants
is a judgement the resolver should score, not one an irreversible id should
bake in.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .paths import load_config

# --------------------------------------------------------------------------- #
# character classes
# --------------------------------------------------------------------------- #

TATWEEL = "ـ"                     # ـ  kashida, pure typography
HARAKAT = re.compile(r"[ً-ٰٟۖ-ۭ]")
ALIF_FORMS = "أإآٱ"   # أ إ آ ٱ
ALIF = "ا"                            # ا
ALIF_MAQSURA = "ى"                    # ى
YA = "ي"                              # ي
TA_MARBUTA = "ة"                      # ة
HA = "ه"                              # ه
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_WS = re.compile(r"[ \t ]+")
_BLANK_RUN = re.compile(r"\n{3,}")


@lru_cache(maxsize=1)
def _rules() -> dict:
    cfg = load_config("aalam_ocr_confusions")
    return {
        "words": dict(cfg.get("word_repairs") or {}),
        "clause_enders": tuple(cfg.get("clause_enders") or ()),
    }


# --------------------------------------------------------------------------- #
# display-side cleaning: safe to apply to text we will quote
# --------------------------------------------------------------------------- #

def clean_page(text: str) -> str:
    """Repair OCR damage without changing the words on the page.

    Only reversible typography is touched: Unicode presentation forms are
    folded to their canonical codepoints, the kashida is dropped (it carries
    no meaning, and tesseract emits it inconsistently inside display type),
    and the punctuation the engine reliably misreads is put back. Words are
    left exactly as printed, so the result is still quotable as the source.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(TATWEEL, "")
    text = text.translate(_ARABIC_INDIC)

    # The Arabic comma is read as a guillemet or a stray hamza when it sits at
    # a clause boundary. Both are impossible there in this text: a guillemet
    # only ever opens or closes a quoted title, always in pairs.
    for bad in _rules()["clause_enders"]:
        text = re.sub(rf"(?<=[؀-ۿ]){re.escape(bad)}(?=\s)", "،", text)

    for wrong, right in _rules()["words"].items():
        text = re.sub(rf"(?<![؀-ۿ]){re.escape(wrong)}(?![؀-ۿ])",
                      right, text)

    text = _WS.sub(" ", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# match-side folding: never written back to the display string
# --------------------------------------------------------------------------- #

def strip_harakat(text: str) -> str:
    """Drop vowel marks. They are optional in print and inconsistent in OCR."""
    return HARAKAT.sub("", text)


def fold(text: str) -> str:
    """The match key: fold every distinction OCR and typesetting do not keep.

    Alif hamza forms, alif maqsura vs ya, and ta marbuta vs ha are collapsed.
    In print these are meaningful; in this scan they are not reliably
    distinguished, so treating them as distinct would split one person into
    several. The display string keeps all of them.
    """
    text = strip_harakat(unicodedata.normalize("NFKC", text)).replace(TATWEEL, "")
    for form in ALIF_FORMS:
        text = text.replace(form, ALIF)
    text = text.replace(ALIF_MAQSURA, YA).replace(TA_MARBUTA, HA)
    text = re.sub(r"[^؀-ۿ0-9 ]+", " ", text)
    return _WS.sub(" ", text).strip()


def fold_pattern(pattern: str) -> str:
    """Apply the match-key letter foldings to a regex, leaving its syntax alone.

    Cues are written the way the book prints them (``قرأ\s+على``) but are
    matched against folded text, where hamza forms and alif maqsura have
    already been collapsed. Folding the pattern with :func:`fold` would strip
    the regex metacharacters along with the punctuation, so only the
    character-level substitutions are applied here -- never the class filter.

    Without this the cue table silently under-fires: every pattern containing
    an alif hamza or a final alif maqsura, which is most of them, fails to
    match text that has had exactly those characters normalised away.
    """
    out = strip_harakat(unicodedata.normalize("NFKC", pattern)).replace(TATWEEL, "")
    for form in ALIF_FORMS:
        out = out.replace(form, ALIF)
    return out.replace(ALIF_MAQSURA, YA).replace(TA_MARBUTA, HA)


def arabic_only(text: str) -> str:
    """Drop everything but Arabic letters and spaces, for length heuristics."""
    return _WS.sub(" ", re.sub(r"[^؀-ۿ ]+", " ", text)).strip()
