"""Stage 4 -- split issues into announcement blocks and state acts.

Two things make this stage more than a text split.

**Folio pages are preserved.** The running headers carry the printed page
number ("Page 2522 Journal Officiel ..."), which is what a reader cites; the
OCR page index is not the same thing. Chrome is therefore *recorded* before it
is removed, and every block keeps both numbers.

**Blocks are found in concatenated text.** An announcement frequently runs
across a page break, so segmentation operates on the chrome-stripped
concatenation of all pages, with an offset map back to the printed page.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

from .paths import INTERIM, MANIFEST, PROCESSED, RAW, ensure_dirs, load_config

RE_PAGE = re.compile(r"<!--\s*page:(?P<n>\d+)\s*-->")

# Chrome: running headers and footers. Recorded (for the folio) then removed.
RE_CHROME_HDR = re.compile(
    r"^(?:Page\s+(?P<folio_a>\d{1,5})\s+)?Journal\s+Officiel\s+de\s+la\s+"
    r"R[ée]publique\s+Tunisienne\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
RE_CHROME_FOLIO = re.compile(r"^\s*Page\s+(?P<folio>\d{1,5})\s*$",
                             re.IGNORECASE | re.MULTILINE)
RE_CHROME_ISSUE = re.compile(r"^\s*N[°ºo]\s*\d{1,3}\s*$", re.MULTILINE)

# Announcement reference code: terminates its block, and its 5-char rubric
# suffix types the announcement almost for free.
# The code normally sits alone on its line, but in 925 issues it trails the
# last sentence of the announcement. Requiring a whole line missed 1,559 codes,
# merging those announcements into their neighbour and so attributing them to
# the wrong company.
RE_REF = re.compile(
    r"(?:^[ \t]*|(?<=[.\s]))(?P<ref>(?P<year>\d{4})(?P<series>[A-Z0-9]{1,6}?)"
    r"(?P<seq>\d{3,6})(?P<rubric>[A-Z]{3,4}\d))[ \t]*$",
    re.MULTILINE,
)

# Marks the end of the page-1 front matter (masthead + Sommaire) that precedes
# the first announcement of an issue. Only the FIRST block needs trimming: the
# text between two reference codes is a single announcement in its entirety.
RE_FRONT_MATTER_END = re.compile(
    r"^(?:#{1,6}\s*CONSTITUTION\s+DE\s+SOCIETES|#{1,6}\s*ANNONCES|---)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Journal officiel: section headings give each act its organisational anchor.
RE_JO_SECTION = re.compile(
    r"^#{0,6}\s*(?P<sec>(?:PRESIDENCE|PR[ÉE]SIDENCE|MINIST[ÈE]RE|ASSEMBL[ÉE]E|"
    r"CONSEIL|HAUTE\s+INSTANCE|BANQUE\s+CENTRALE)[^\n]*)$",
    re.MULTILINE,
)
# An act opener must be the noun followed by "du"/"n°" -- not the verb
# "Arrête :" that introduces a dispositif, which occurs ~6,300 times.
RE_JO_ACT = re.compile(
    r"^#{0,6}\s*(?P<opener>(?:Par\s+)?"
    r"(?P<kind>d[ée]cret(?:-loi)?(?:\s+Pr[ée]sidentiel|\s+gouvernemental)?|"
    r"arr[êe]t[ée]s?|loi(?:\s+organique)?|d[ée]cision|circulaire)"
    r"[^\n]{0,160}?(?:n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4})|du\s+\d{1,2}))",
    re.IGNORECASE | re.MULTILINE,
)

BLOCK_FIELDS = [
    "block_uid", "issue_uid", "collection", "year", "issue", "pub_date",
    "block_type", "ref", "ref_series", "ref_seq", "rubric_raw", "rubric",
    "rubric_repaired", "legal_form", "section", "domain",
    "ministry", "act_kind", "act_number", "heading",
    "ocr_page_start", "ocr_page_end", "folio_page_start", "folio_page_end",
    "spans_page_break", "n_chars", "text_sha1", "needs_review", "review_note",
]


# --------------------------------------------------------------------------- #
# page mapping
# --------------------------------------------------------------------------- #

@dataclass
class PageMap:
    """Chrome-stripped text plus a map from offset back to the printed page."""

    text: str = ""
    starts: list[int] = field(default_factory=list)
    ocr_pages: list[int] = field(default_factory=list)
    folios: list[int | None] = field(default_factory=list)

    def page_at(self, offset: int) -> tuple[int | None, int | None]:
        if not self.starts:
            return None, None
        i = max(0, bisect_right(self.starts, offset) - 1)
        return self.ocr_pages[i], self.folios[i]

    def span_pages(self, start: int, end: int) -> tuple:
        o1, f1 = self.page_at(start)
        o2, f2 = self.page_at(max(start, end - 1))
        return o1, o2, f1, f2


def strip_chrome(raw: str) -> PageMap:
    """Remove page markers and running chrome, keeping the folio numbers.

    Chrome is read before deletion because the folio page is the citable one.
    """
    pm = PageMap()
    parts = RE_PAGE.split(raw)
    # parts = [pre, n1, body1, n2, body2, ...]
    chunks: list[tuple[int, str]] = []
    if parts[0].strip():
        chunks.append((0, parts[0]))
    for i in range(1, len(parts) - 1, 2):
        chunks.append((int(parts[i]), parts[i + 1]))

    buf: list[str] = []
    cursor = 0
    for ocr_page, body in chunks:
        folio: int | None = None
        for m in RE_CHROME_HDR.finditer(body):
            if m.group("folio_a"):
                folio = int(m.group("folio_a"))
                break
        if folio is None:
            m = RE_CHROME_FOLIO.search(body)
            if m:
                folio = int(m.group("folio"))

        cleaned = RE_CHROME_HDR.sub("", body)
        cleaned = RE_CHROME_FOLIO.sub("", cleaned)
        cleaned = RE_CHROME_ISSUE.sub("", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        pm.starts.append(cursor)
        pm.ocr_pages.append(ocr_page)
        pm.folios.append(folio)
        buf.append(cleaned)
        cursor += len(cleaned)

    pm.text = "".join(buf)
    _fill_folios(pm)
    return pm


def _fill_folios(pm: PageMap) -> None:
    """Fill folio gaps from neighbouring pages.

    Only some pages print the "Page NNNN" header, but folios advance by one per
    page, so a gap can be filled exactly from the nearest anchor in either
    direction. This is arithmetic on a known sequence, not interpolation of an
    unknown, and it lets every block carry a citable page number.
    """
    n = len(pm.folios)
    known = [i for i, f in enumerate(pm.folios) if f is not None]
    if not known:
        return
    # Trust the sequence only where it is internally consistent: consecutive
    # anchors should differ by exactly their page distance.
    for idx in range(n):
        if pm.folios[idx] is not None:
            continue
        before = [i for i in known if i < idx]
        after = [i for i in known if i > idx]
        cand = None
        if before:
            j = before[-1]
            cand = pm.folios[j] + (idx - j)
        if after:
            k = after[0]
            alt = pm.folios[k] - (k - idx)
            if cand is None or cand == alt:
                cand = alt
            else:
                cand = None  # anchors disagree; leave unknown rather than guess
        pm.folios[idx] = cand


# --------------------------------------------------------------------------- #
# rubric handling
# --------------------------------------------------------------------------- #

def _rubric_table() -> dict:
    return load_config("vocab_events")["rubrics"]


def repair_rubric(raw: str, table: dict) -> tuple[str, bool]:
    """Map an OCR-damaged rubric suffix onto the nearest known code.

    Roughly 0.02% of codes are corrupted (RUB1 for SRUB1, VEA2 for VEPA2).
    A single-edit neighbour is accepted and flagged; anything further is left
    unmapped so it shows up in review rather than being guessed at.
    """
    if raw in table:
        return raw, False
    best, best_d = None, 99
    for cand in table:
        d = _edit_distance(raw, cand, cap=2)
        if d < best_d:
            best, best_d = cand, d
    if best is not None and best_d <= 1:
        return best, True
    return "", False


def _edit_distance(a: str, b: str, cap: int = 2) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# --------------------------------------------------------------------------- #
# segmentation
# --------------------------------------------------------------------------- #

def segment_annonces(pm: PageMap, meta: dict, table: dict) -> tuple[list[dict], list[dict]]:
    """Split an annonces issue on its trailing reference codes."""
    blocks: list[dict] = []
    orphans: list[dict] = []
    seen_refs: dict[str, int] = {}
    prev_end = 0
    for m in RE_REF.finditer(pm.text):
        body_start, body_end = prev_end, m.start()
        prev_end = m.end()
        body = pm.text[body_start:body_end]
        if not body.strip():
            continue

        # Only the first block carries front matter (masthead and Sommaire);
        # every later body is one complete announcement, so trimming it would
        # discard the company name, capital and address that open the notice.
        offset = 0
        if body_start == 0:
            fm = list(RE_FRONT_MATTER_END.finditer(body))
            if fm:
                offset = fm[-1].end()
                discarded = body[:offset].strip()
                if len(discarded) > 120:
                    orphans.append({
                        "issue_uid": meta["issue_uid"],
                        "ref": m.group("ref"),
                        "n_chars": len(discarded),
                        "text": discarded[:600],
                    })
        raw_tail = body[offset:]
        text = raw_tail.strip().lstrip("-").strip()
        if not text:
            continue

        # Cite from where the announcement actually begins, not from the end of
        # the previous block: a block whose body starts at a page boundary would
        # otherwise be attributed to the preceding folio.
        lead = len(raw_tail) - len(raw_tail.lstrip())
        first_char = raw_tail.find(text[:20].strip()[:10], lead) if text else lead
        abs_start = body_start + offset + (first_char if first_char >= 0 else lead)
        o1, o2, f1, f2 = pm.span_pages(abs_start, body_end)
        rubric_raw = m.group("rubric")
        rubric, repaired = repair_rubric(rubric_raw, table)
        info = table.get(rubric, {}) if rubric else {}
        heading = _first_heading(text)

        # An announcement reference is not unique within an issue: 151 issues
        # between 2004 and 2017 print the same reference twice, as a reprint or
        # a correction, with slightly different OCR each time. Both texts are
        # kept -- there is no way to tell which is authoritative -- but the uid
        # has to distinguish them, or provenance points at two different texts
        # and the verbatim-quote guard fails against whichever copy a reader's
        # lookup happens to hold.
        ref = m.group("ref")
        n_seen = seen_refs[ref] = seen_refs.get(ref, 0) + 1
        uid = f"{meta['issue_uid']}:{ref}" + (f"#{n_seen}" if n_seen > 1 else "")

        blocks.append({
            **meta,
            "block_uid": uid,
            "block_type": "annonce",
            "ref": m.group("ref"),
            "ref_series": m.group("series"),
            "ref_seq": m.group("seq"),
            "rubric_raw": rubric_raw,
            "rubric": rubric,
            "rubric_repaired": repaired,
            "legal_form": info.get("legal_form") or "",
            "section": info.get("section") or "",
            "domain": info.get("domain") or "",
            "ministry": "", "act_kind": "", "act_number": "",
            "heading": heading,
            "ocr_page_start": o1, "ocr_page_end": o2,
            "folio_page_start": f1, "folio_page_end": f2,
            "spans_page_break": bool(o1 is not None and o2 is not None and o2 > o1),
            "n_chars": len(text),
            "text_sha1": hashlib.sha1(text.encode()).hexdigest(),
            "needs_review": not rubric,
            "review_note": "" if rubric else f"unmapped rubric {rubric_raw!r}",
            "text": text,
        })
    return blocks, orphans


def segment_jo(pm: PageMap, meta: dict) -> tuple[list[dict], list[dict]]:
    """Split a journal-officiel issue into acts under their ministry section."""
    text = pm.text
    # Drop the page-1 Sommaire, whose entries mimic act titles.
    body_start = 0
    som = re.search(r"^#{0,6}\s*Sommaire\s*$", text, re.IGNORECASE | re.MULTILINE)
    if som:
        after = re.search(r"^\s*(?:---|#\s*\w)", text[som.end():], re.MULTILINE)
        body_start = som.end() + (after.start() if after else 0)

    sections = [(m.start(), re.sub(r"\s+", " ", m.group("sec")).strip())
                for m in RE_JO_SECTION.finditer(text) if m.start() >= body_start]

    def section_at(pos: int) -> str:
        name = ""
        for start, sec in sections:
            if start <= pos:
                name = sec
            else:
                break
        return name

    opens = [m for m in RE_JO_ACT.finditer(text) if m.start() >= body_start]
    blocks: list[dict] = []
    for i, m in enumerate(opens):
        start = m.start()
        end = opens[i + 1].start() if i + 1 < len(opens) else len(text)
        act_text = text[start:end].strip()
        if not act_text:
            continue
        o1, o2, f1, f2 = pm.span_pages(start, end)
        kind = re.sub(r"\s+", " ", m.group("kind")).strip().lower()
        blocks.append({
            **meta,
            "block_uid": f"{meta['issue_uid']}:act{i + 1:04d}",
            "block_type": "act",
            "ref": "", "ref_series": "", "ref_seq": "",
            "rubric_raw": "", "rubric": "", "rubric_repaired": False,
            "legal_form": "", "section": "state", "domain": "state",
            "ministry": section_at(start),
            "act_kind": kind,
            "act_number": (m.group("num") or "").replace(" ", ""),
            "heading": re.sub(r"\s+", " ", act_text.split("\n")[0])[:300],
            "ocr_page_start": o1, "ocr_page_end": o2,
            "folio_page_start": f1, "folio_page_end": f2,
            "spans_page_break": bool(o1 is not None and o2 is not None and o2 > o1),
            "n_chars": len(act_text),
            "text_sha1": hashlib.sha1(act_text.encode()).hexdigest(),
            "needs_review": False, "review_note": "",
            "text": act_text,
        })
    return blocks, []


def _first_heading(text: str) -> str:
    for line in text.split("\n"):
        s = line.strip().lstrip("#").strip()
        if s and len(s) > 2:
            return re.sub(r"\s+", " ", s)[:300]
    return ""


def run() -> dict:
    ensure_dirs()
    table = _rubric_table()
    with (PROCESSED / "issue_calendar.csv").open(encoding="utf-8", newline="") as fh:
        cal = {r["issue_uid"]: r for r in csv.DictReader(fh)}
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        manifest = [r for r in csv.DictReader(fh)]

    out_path = INTERIM / "blocks.jsonl"
    index: list[dict] = []
    orphans: list[dict] = []
    stats = {"issues": 0, "annonce_blocks": 0, "acts": 0, "skipped_not_fr": 0,
             "skipped_undated": 0, "rubric_repaired": 0, "rubric_unmapped": 0}

    with out_path.open("w", encoding="utf-8") as out:
        for rec in manifest:
            if rec["status"] != "ok":
                stats["skipped_not_fr"] += 1
                continue
            uid = rec["issue_uid"]
            cal_row = cal.get(uid, {})
            pub_date = cal_row.get("pub_date", "")
            if not pub_date:
                stats["skipped_undated"] += 1
                continue
            path = RAW / rec["collection"] / rec["language"] / rec["year"] / f"{rec['issue']}.md"
            if not path.exists():
                continue
            pm = strip_chrome(path.read_text(encoding="utf-8", errors="replace"))
            meta = {
                "issue_uid": uid, "collection": rec["collection"],
                "year": int(rec["year"]), "issue": rec["issue"], "pub_date": pub_date,
            }
            if rec["collection"] == "annonces-legales":
                blocks, orph = segment_annonces(pm, meta, table)
                stats["annonce_blocks"] += len(blocks)
            else:
                blocks, orph = segment_jo(pm, meta)
                stats["acts"] += len(blocks)
            orphans.extend(orph)
            stats["issues"] += 1
            for b in blocks:
                stats["rubric_repaired"] += bool(b["rubric_repaired"])
                stats["rubric_unmapped"] += bool(b["block_type"] == "annonce" and not b["rubric"])
                out.write(json.dumps(b, ensure_ascii=False) + "\n")
                index.append({k: b.get(k, "") for k in BLOCK_FIELDS})

    _write(PROCESSED / "blocks_index.csv", index, BLOCK_FIELDS)
    _write(INTERIM / "segment_orphans.csv", orphans,
           ["issue_uid", "ref", "n_chars", "text"])
    stats["orphan_fragments"] = len(orphans)
    return stats


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Segment issues into blocks and acts.").parse_args(argv)
    for k, v in run().items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
