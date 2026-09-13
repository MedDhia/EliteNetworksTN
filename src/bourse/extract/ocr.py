"""Read scanned filings by OCR, presenting them as pdfplumber pages.

A third of the CMF's archive is paper that was scanned, not filed digitally:
every annual report for financial years 2004-2011 is a page image carrying no
text layer at all, so the ordinary extraction path gets literally nothing from
them. They are also the only filings that cover those years, which makes them
worth the trouble.

The table extractor already knows how to rebuild a borderless table from word
coordinates, which is exactly what OCR produces. So rather than writing a
second extraction path, this module wraps Tesseract's word boxes in the small
part of the pdfplumber page interface that `extract.tables` actually uses -
``extract_words``, ``extract_text``, ``find_tables`` and ``height``. Every
classification, heading-binding and row-parsing rule then applies unchanged,
and an OCR'd table is held to the same standard as a digital one.

Two things are deliberately not done. Ruling lines are not recovered from the
image, so ``find_tables`` returns nothing and every OCR'd table goes through
the borderless reconstruction path. And no attempt is made to correct OCR
spellings: a misread name should surface as an unmatched entity that a human
can see, not be silently merged into a real one.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from ..common import log

# Tesseract 5 is built with OpenMP and, on page images of this size, its
# multi-threaded path collapses: a page that takes 2 seconds single-threaded
# takes 78 with OpenMP left to its own devices - a 39x difference, measured on
# a scanned 2005 annual report. Extraction is parallelised across documents
# anyway, which uses the cores properly, so each OCR process is pinned to one
# thread. This must be set before the tesseract binary is invoked.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

# 300 dpi is where Tesseract's accuracy on small table figures stops improving
# enough to pay for the rendering time. Below ~250 the thousands separators in
# share counts start dropping out, which is the one thing we cannot detect.
DPI = 300

# Tesseract's own confidence, 0-100. Below this a "word" is usually scanner
# speckle. Table rules and page borders come through as punctuation strings,
# which is why they are dropped separately.
MIN_CONF = 40

# Page images are rendered one at a time and thrown away; a scanned annual
# report can be 200 pages and the tables we want are in the front matter.
DEFAULT_MAX_PAGES = 40

_JUNK = re.compile(r"^[^\w%]+$")


@dataclass
class OcrPage:
    """One OCR'd page, quacking like a pdfplumber page.

    Coordinates are in image pixels rather than PDF points. Nothing downstream
    compares them against anything but each other - gaps, line buckets and
    heading positions are all relative - so they are left unscaled.
    """

    words: list[dict]
    height: float
    width: float
    page_number: int
    _text: str = ""

    def extract_words(self, **_kw) -> list[dict]:
        return self.words

    def extract_text(self, **_kw) -> str:
        return self._text

    def find_tables(self, *_a, **_kw) -> list:
        # Ruling lines are not recovered from the image. Returning nothing
        # sends every table through the borderless reconstruction path, which
        # is what a page of OCR'd words is anyway.
        return []


@dataclass
class OcrDocument:
    """A stand-in for a pdfplumber PDF holding OCR'd pages."""

    pages: list[OcrPage] = field(default_factory=list)


def _words_from_tsv(data: dict, page_number: int, scale: float) -> list[dict]:
    """Turn Tesseract's image_to_data output into pdfplumber-shaped words.

    Coordinates are divided back down to PDF points. This matters: every
    threshold in `extract.tables` - the line-bucket height, the minimum column
    gap - is calibrated in points, and at 300 dpi a pixel-coordinate page would
    bucket each printed line into four separate "lines", tearing every row away
    from its own figures.
    """
    rows: list[dict] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text or _JUNK.match(text):
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < MIN_CONF:
            continue
        left, top = float(data["left"][i]) / scale, float(data["top"][i]) / scale
        rows.append({
            "text": text,
            "x0": left,
            "x1": left + float(data["width"][i]) / scale,
            "top": top,
            "bottom": top + float(data["height"][i]) / scale,
            "upright": True,
            "page_number": page_number,
            "_line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
        })

    # Snap every word on one printed line to a common vertical position.
    # Tesseract reports each word's own glyph box, so a word without ascenders
    # or descenders ("M.", "au", "par") sits a point or two off its neighbours.
    # Downstream that is fatal: lines are bucketed in 3-point bands, so the
    # honorific separates from the name it belongs to and the row falls apart.
    # Tesseract already knows which words share a line; this uses that rather
    # than guessing from geometry.
    by_line: dict[tuple, list[dict]] = {}
    for w in rows:
        by_line.setdefault(w.pop("_line"), []).append(w)
    for ws in by_line.values():
        top = min(w["top"] for w in ws)
        bottom = max(w["bottom"] for w in ws)
        for w in ws:
            w["top"], w["bottom"] = top, bottom
    return rows


def _text_from_words(words: list[dict]) -> str:
    """Flatten words back to lines, so the page's text tests still work.

    The 3-point bucket is the same one `extract.tables` uses, so the text a
    page reports and the rows the extractor rebuilds agree about where the
    lines are.
    """
    buckets: dict[int, list[dict]] = {}
    for w in words:
        buckets.setdefault(round(w["top"] / 3.0), []).append(w)
    lines = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w["x0"])
        lines.append(" ".join(w["text"] for w in ws))
    return "\n".join(lines)


def has_text_layer(pdf, sample_pages: int = 6, min_chars: int = 200) -> bool:
    """Whether a PDF carries enough of a text layer to be read without OCR.

    Judged over several pages rather than the first: a scanned report often
    opens with a digitally generated cover sheet, and a born-digital one can
    open with a full-page image.
    """
    total = 0
    for page in pdf.pages[:sample_pages]:
        try:
            total += len(page.extract_text() or "")
        except Exception:
            continue
    return total >= min_chars


def ocr_document(path, max_pages: int | None = None, dpi: int = DPI,
                 lang: str = "fra") -> OcrDocument:
    """Render a PDF's pages and OCR them into page objects.

    Raises ImportError if the OCR stack is missing, so a caller can fall back
    rather than silently producing an empty document.
    """
    import pypdfium2 as pdfium
    import pytesseract

    limit = DEFAULT_MAX_PAGES if max_pages is None else max_pages
    doc = pdfium.PdfDocument(str(path))
    pages: list[OcrPage] = []
    try:
        n = min(len(doc), limit)
        scale = dpi / 72.0
        for i in range(n):
            page = doc[i]
            try:
                image = page.render(scale=scale).to_pil()
                data = pytesseract.image_to_data(
                    image, lang=lang, output_type=pytesseract.Output.DICT,
                    # 1 = automatic page segmentation with orientation and
                    # script detection: scanned filings are not always square
                    # on the platen, and a rotated page OCRs to nothing.
                    config="--psm 1",
                )
            except Exception as exc:
                log.debug("OCR failed on page %d of %s: %s", i + 1, path, exc)
                continue
            finally:
                page.close()
            words = _words_from_tsv(data, i + 1, scale)
            if not words:
                continue
            pages.append(OcrPage(
                words=words,
                height=float(image.height) / scale,
                width=float(image.width) / scale,
                page_number=i + 1,
                _text=_text_from_words(words),
            ))
    finally:
        doc.close()
    return OcrDocument(pages=pages)
