"""Code each firm-year as politically connected, or not, and say why.

The concept comes from a literature that does not agree on one definition, so
this codes the *channels* separately and leaves the aggregation to the analyst.
Four of them are observable in CMF filings:

``state_ownership``
    A state body holds equity in the firm. Boubakri, Cosset and Saffar (2008)
    treat government ownership as a connection in its own right; Faccio (2006)
    counts a shareholder only above a threshold, which is why the stake is
    carried alongside the flag and ``pc_narrow`` applies her 10%.

``state_board``
    A state body - a ministry, the central bank, a public agency - holds a
    board seat. This is the organ sitting on the board, not a person.

``officeholder``
    A director or officer whose printed title names a political or senior
    bureaucratic office. This is closest to Faccio's own rule, which asks
    whether a top officer *is* a minister, an MP or a head of state. Current
    and former office are flagged separately, after Hillman (2005).

``public_bank``
    A board or equity tie to a majority state-owned bank. Khwaja and Mian
    (2005) identify connection through state-bank lending; Diwan, Keefer and
    Schiffbauer (2020) apply it across MENA. The filings do not show loans, so
    this is the governance tie, which is weaker - it is kept out of
    ``pc_narrow`` for that reason.

A fifth, ``political_figure``, matches directors against a named roster of
political figures - the design Rijkers, Freund and Nucifora (2017) use for
Tunisia with the post-revolution confiscation lists. The matching is
implemented and tested; the roster ships empty, because putting a name in it
is an assertion about a real person that needs a citable primary source. See
the notes in ``config/bourse_political_connections.csv``.

Every rule lives in that file, not here, so that a reader can see what was
counted and rebuild after disagreeing with a line.

Run with::

    PYTHONPATH=src python -m bourse.political_connections

Writes a firm-year panel, a long evidence file in which every flag points at
the page it came from, and a short report.
"""

from __future__ import annotations

import csv
import gzip
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from .common import PROCESSED, ROOT, log, read_jsonl
from .entities import Resolver, person_key

RECORDS = PROCESSED / "records"
RULES = ROOT / "config" / "bourse_political_connections.csv"
EDGES = PROCESSED / "multiplex_edges_observed.csv.gz"
PANEL_OUT = PROCESSED / "political_connections.csv"
EVIDENCE_OUT = PROCESSED / "political_connection_evidence.csv"
REPORT_OUT = PROCESSED / "political_connections.md"

# Faccio (2006) counts a shareholder as connected at 10% of voting shares.
FACCIO_THRESHOLD = 10.0

# Layers in which a state body's presence is an ownership stake, and those in
# which it is a seat. `ownership_director` is a director's personal holding,
# not the state's, so it is excluded from both.
OWNERSHIP_LAYERS = {"ownership", "group_participation"}
BOARD_LAYERS = {"board_seat_corporate", "board_seat", "board_interlock"}

FIRMISH = {"firm", "fund", "state"}

CHANNELS = ["state_ownership", "state_board", "officeholder", "public_bank",
            "political_figure"]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


# Filings set compound titles with whatever dash the typesetter had, and OCR
# adds more variety. "Ex - vice-Gouverneur" with an en dash read as a *serving*
# governor until these were folded, because the `former` pattern's separator
# class did not contain the character actually on the page.
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


def norm(s: str) -> str:
    """Lower-case, accent-free, dash- and whitespace-folded: what patterns match."""
    return re.sub(r"\s+", " ", strip_accents(s or "").translate(_DASHES).lower()).strip()


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------


class Rules:
    """The coding rules, compiled once.

    Kept as an object rather than module globals so a test can build a rule set
    without a config file on disk.
    """

    def __init__(self, rows: list[dict]) -> None:
        self.office: list[tuple[re.Pattern, str, str]] = []
        self.state_firm: list[tuple[re.Pattern, str]] = []
        self.figures: dict[str, dict] = {}
        for row in rows:
            kind = (row.get("rule_kind") or "").strip()
            pat = (row.get("pattern") or "").strip()
            cat = (row.get("category") or "").strip()
            if not kind or not pat:
                continue
            if kind == "office_title":
                self.office.append(
                    (re.compile(pat, re.I), cat, (row.get("tenure") or "current").strip()))
            elif kind == "state_owned_firm":
                self.state_firm.append((re.compile(pat, re.I), cat))
            elif kind == "political_figure":
                # Matched on the resolver's own order-insensitive person key,
                # so "BEN ALI Leila" and "Leila Ben Ali" are one person.
                self.figures[person_key(pat)] = {
                    "name": pat, "category": cat or "political_figure",
                    "source": (row.get("source") or "").strip()}

    def office_match(self, text: str) -> tuple[str, str] | None:
        """Return (category, tenure) for the first matching office rule.

        A title can name more than one office - "ex-vice-Gouverneur de la BCT
        et ex-ministre du commerce" - so a *former* match is preferred over a
        current one. Reading that title as a sitting minister would be the
        more consequential error.
        """
        n = norm(text)
        if not n:
            return None
        hit = None
        for pat, cat, tenure in self.office:
            if pat.search(n):
                if tenure == "former":
                    return cat, tenure
                hit = hit or (cat, tenure)
        return hit

    def is_state_owned(self, name: str) -> str | None:
        n = norm(name)
        for pat, cat in self.state_firm:
            if pat.search(n):
                return cat
        return None

    def figure_match(self, name: str) -> dict | None:
        return self.figures.get(person_key(name))


def load_rules(path: Path = RULES) -> Rules:
    if not path.exists():
        log.warning("no coding rules at %s; nothing will be flagged", path)
        return Rules([])
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("rule_kind") and not r["rule_kind"].lstrip().startswith("#")]
    return Rules(rows)


# --------------------------------------------------------------------------
# evidence
# --------------------------------------------------------------------------


def _year(rec: dict) -> int | None:
    for key in ("as_of", "issuer_ref_year", "filing_date"):
        v = rec.get(key)
        if not v:
            continue
        m = re.search(r"(19|20)\d{2}", str(v))
        if m:
            return int(m.group(0))
    return None


def read_edges() -> list[dict]:
    with gzip.open(EDGES, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def from_edges(edges: list[dict], rules: Rules) -> list[dict]:
    """State ownership, state board seats and public-bank ties.

    All three are relational, so the edge list already holds them with both
    ends resolved; nothing needs re-reading here.
    """
    out = []
    for e in edges:
        layer, year = e["layer"], e.get("year")
        if not year:
            continue
        for near, far in (("source", "target"), ("target", "source")):
            if e[f"{far}_type"] != "firm":
                continue
            counter_type, counter_name = e[f"{near}_type"], e[f"{near}_name"]
            firm_id, firm_name = e[f"{far}_id"], e[f"{far}_name"]
            if not firm_id or firm_id == e[f"{near}_id"]:
                continue
            base = {
                "entity_id": firm_id, "canonical_name": firm_name, "year": year,
                "counterpart": counter_name, "counterpart_id": e[f"{near}_id"],
                "layer": layer, "detail": "",
                "doc_url": e.get("doc_url", ""), "page": e.get("page", ""),
                "doc_type": e.get("doc_type", ""), "from_ocr": e.get("from_ocr", "0"),
            }
            if counter_type == "state" and layer in OWNERSHIP_LAYERS:
                out.append({**base, "channel": "state_ownership",
                            "category": "state_shareholder", "tenure": "",
                            "stake_pct": e.get("pct_stated", "")})
            elif counter_type == "state" and layer in BOARD_LAYERS:
                out.append({**base, "channel": "state_board",
                            "category": "state_organ_seat", "tenure": "",
                            "stake_pct": ""})
            cat = rules.is_state_owned(counter_name)
            if cat and counter_type in FIRMISH and layer in (OWNERSHIP_LAYERS | BOARD_LAYERS):
                # Strength is recorded in the category, because these are not
                # one relationship. A public bank holding equity is close to
                # the lending channel the literature identifies; sharing a
                # director with one is a much weaker claim, and pooling them
                # would let the weakest evidence carry the channel.
                strength = ("equity" if layer in OWNERSHIP_LAYERS
                            else "interlock" if layer == "board_interlock"
                            else "seat")
                out.append({**base, "channel": "public_bank",
                            "category": f"{cat}_{strength}",
                            "tenure": "", "stake_pct": e.get("pct_stated", "")})
    return out


# Where a political office can be printed. `represented_by_raw` matters as much
# as the role column: a ministry's seat names the official who fills it.
# `section_heading` is included because the state's seats are usually marked
# once over a block of directors - "ADMINISTRATEURS REPRESENTANT L'ETAT
# TUNISIEN" - rather than against each name. That makes the heading apply to
# every row beneath it, which is the intended reading, but it also means one
# misread heading flags a whole table: `detail` carries the text so the call
# can be checked.
TITLE_FIELDS = ("role_raw", "member_title", "represented_by_raw", "relation",
                "section_heading")
NAME_FIELDS = ("member_name_raw", "represented_by_raw")


def from_records(rules: Rules, res: Resolver) -> list[dict]:
    """Officeholders and roster figures, read from the records themselves.

    The edge list carries role text for only about 60% of board seats, so the
    office signal is taken from the records, where every title field survives.
    The issuer is resolved with the same resolver the build uses, so the
    entity_ids line up with every other file.
    """
    out = []
    for fname in ("board.jsonl.gz", "executives.jsonl.gz", "interlocks.jsonl.gz"):
        path = RECORDS / fname
        if not path.exists():
            continue
        for rec in read_jsonl(path):
            issuer = rec.get("issuer_name_raw")
            if not issuer:
                continue
            firm_id, ftype = res.resolve(issuer, hint="firm")
            if not firm_id or ftype not in FIRMISH:
                continue
            year = _year(rec)
            if year is None:
                continue
            base = {
                "entity_id": firm_id, "canonical_name": res.canonical_name(firm_id),
                "year": str(year), "layer": rec.get("record_kind", fname.split(".")[0]),
                "doc_url": rec.get("doc_url", ""), "page": rec.get("page", ""),
                "doc_type": rec.get("doc_type", ""),
                "from_ocr": "1" if rec.get("from_ocr") else "0", "stake_pct": "",
            }
            who = next((rec.get(f) for f in NAME_FIELDS if rec.get(f)), "") or ""
            title = " ".join(str(rec.get(f) or "") for f in TITLE_FIELDS).strip()
            hit = rules.office_match(title)
            if hit:
                cat, tenure = hit
                out.append({**base, "channel": "officeholder", "category": cat,
                            "tenure": tenure, "counterpart": who or title[:60],
                            "counterpart_id": "", "detail": title[:160]})
            fig = rules.figure_match(who)
            if fig:
                out.append({**base, "channel": "political_figure",
                            "category": fig["category"], "tenure": "",
                            "counterpart": who, "counterpart_id": "",
                            "detail": fig["source"][:160]})
    return out


# --------------------------------------------------------------------------
# panel
# --------------------------------------------------------------------------


def to_panel(evidence: list[dict]) -> list[dict]:
    """Collapse evidence to one row per firm-year.

    ``pc_narrow`` follows Faccio (2006) as closely as this source allows: a
    named officeholder, or a state stake at or above her 10% threshold. It
    deliberately excludes the public-bank tie, which is a governance link
    rather than the lending relationship that literature identifies, and
    excludes state stakes whose size the filing did not state.

    ``pc_broad`` is any channel at all.
    """
    cells: dict[tuple[str, str], dict] = {}
    for ev in evidence:
        key = (ev["entity_id"], ev["year"])
        row = cells.setdefault(key, {
            "entity_id": ev["entity_id"], "canonical_name": ev["canonical_name"],
            "year": ev["year"], "max_state_stake_pct": "",
            **{f"pc_{c}": 0 for c in CHANNELS},
            "pc_officeholder_former": 0, "pc_public_bank_equity": 0,
            "n_evidence": 0, "n_evidence_ocr": 0,
            "categories": set(),
        })
        row[f"pc_{ev['channel']}"] = 1
        if ev["channel"] == "officeholder" and ev.get("tenure") == "former":
            row["pc_officeholder_former"] = 1
        if ev["channel"] == "public_bank" and ev["category"].endswith("_equity"):
            row["pc_public_bank_equity"] = 1
        row["n_evidence"] += 1
        row["n_evidence_ocr"] += 1 if ev.get("from_ocr") == "1" else 0
        row["categories"].add(ev["category"])
        if ev["channel"] == "state_ownership":
            try:
                pct = float(str(ev.get("stake_pct") or "").replace(",", "."))
            except ValueError:
                pct = None
            if pct is not None:
                cur = row["max_state_stake_pct"]
                if cur == "" or pct > float(cur):
                    row["max_state_stake_pct"] = f"{pct:g}"

    rows = []
    for row in cells.values():
        stake = row["max_state_stake_pct"]
        big_stake = stake != "" and float(stake) >= FACCIO_THRESHOLD
        # A current officeholder only: a former minister is a weaker claim and
        # is carried in its own column for whoever wants it.
        current_office = row["pc_officeholder"] and not row["pc_officeholder_former"]
        row["pc_narrow"] = int(bool(current_office or row["pc_political_figure"]
                                    or big_stake))
        row["pc_broad"] = int(any(row[f"pc_{c}"] for c in CHANNELS))
        row["categories"] = "|".join(sorted(row["categories"]))
        rows.append(row)
    rows.sort(key=lambda r: (r["canonical_name"], r["year"]))
    return rows


PANEL_FIELDS = (["entity_id", "canonical_name", "year"]
                + [f"pc_{c}" for c in CHANNELS]
                + ["pc_officeholder_former", "pc_public_bank_equity",
                   "max_state_stake_pct",
                   "pc_narrow", "pc_broad", "n_evidence", "n_evidence_ocr",
                   "categories"])
EVIDENCE_FIELDS = ["entity_id", "canonical_name", "year", "channel", "category",
                   "tenure", "counterpart", "counterpart_id", "stake_pct",
                   "layer", "detail", "doc_type", "doc_url", "page", "from_ocr"]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("%-38s %6d rows", path.name, len(rows))


# Names that cannot be a company, however generously read: a prospectus title
# fragment, a parenthetical date, a committee. Used only to *report* how much
# entity-resolution debris reached the coding - the rows are left in the files,
# because silently dropping them would hide the defect rather than measure it.
_NOT_A_COMPANY = re.compile(r"^d.?admission$|^prospectus|^note d|^/|^\(cr.{1,3} lors|"
                            r"comit.{1,3} de nomination|^membre\b|^conseil\b", re.I)


def report(panel: list[dict], evidence: list[dict], rules: Rules) -> str:
    firms = {r["entity_id"] for r in panel}
    by_channel = {c: len({r["entity_id"] for r in panel if r[f"pc_{c}"]}) for c in CHANNELS}
    years = sorted({int(r["year"]) for r in panel}) or [0]
    narrow = {r["entity_id"] for r in panel if r["pc_narrow"]}
    ocr = sum(1 for e in evidence if e.get("from_ocr") == "1")
    office_firms = sorted({r["canonical_name"] for r in panel if r["pc_officeholder"]})
    debris = sorted({r["canonical_name"] for r in panel
                     if _NOT_A_COMPANY.search(r["canonical_name"])})
    debris_ids = {r["entity_id"] for r in panel
                  if _NOT_A_COMPANY.search(r["canonical_name"])}
    n_debris = sum(1 for e in evidence if e["entity_id"] in debris_ids)

    # Categories naming a person's own office, as against an organ holding a
    # seat. Counted on distinct title text: the evidence carries no resolved
    # person id, so this is an occurrence count and is described as one.
    PERSONAL = {"minister", "secretary_of_state", "governor", "parliament",
                "cabinet_staff", "ministerial_adviser"}
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in evidence:
        if e["channel"] == "officeholder" and e["category"] in PERSONAL:
            seen[(e["category"], e["tenure"])].add(norm(e["detail"])[:60])
    personal_titles = sorted(((k, len(v)) for k, v in seen.items()),
                             key=lambda kv: (-kv[1], kv[0]))

    lines = [
        "# Political connections",
        "",
        "Firms are coded connected through four observable channels, each",
        "flagged separately so a narrow or a broad definition can be applied",
        "without recoding. Rules live in `config/bourse_political_connections.csv`.",
        "",
        f"**{len(firms)} firms** carry at least one connection in at least one year, "
        f"over {len(years)} years ({years[0]}–{years[-1]}), on "
        f"**{len(evidence)} pieces of evidence** ({ocr} of them from OCR'd pages).",
        "",
        "| Channel | Firms | Definition followed |",
        "|---|---:|---|",
        f"| `state_ownership` | {by_channel['state_ownership']} | A state body holds equity (Boubakri et al. 2008) |",
        f"| `state_board` | {by_channel['state_board']} | A state body holds a board seat |",
        f"| `officeholder` | {by_channel['officeholder']} | A director's title names a political or senior bureaucratic office (Faccio 2006) |",
        f"| `public_bank` | {by_channel['public_bank']} | Board or equity tie to a majority state-owned bank (Khwaja and Mian 2005) |",
        f"| `political_figure` | {by_channel['political_figure']} | Director matches a named roster (Rijkers et al. 2017) — **roster ships empty** |",
        "",
        f"`pc_narrow` — a sitting officeholder, a roster match, or a state stake "
        f"at or above Faccio's 10% — holds for **{len(narrow)} firms**. "
        f"`pc_broad` (any channel) holds for {len(firms)}.",
        "",
        "## What the zeros mean",
        "",
        "A zero is *not* evidence that a firm is unconnected. It means no",
        "filing in this corpus printed a connection the rules can see. Three",
        "things follow, and they bound what the variable can be used for.",
        "",
        "**Connection is coded from titles that firms chose to print.** A",
        "board table that lists a director's occupation will reveal a ministry",
        "post; one that lists only names will not, and both are common. The",
        "measure is therefore closer to *disclosed* connection than to actual",
        "connection, and the gap between them is not random: a firm with more",
        "to disclose may disclose less.",
        "",
        "**The channel that identifies Tunisian connection best is empty.**",
        "Rijkers, Freund and Nucifora (2017) code connection by matching owners",
        "against the Ben Ali confiscation lists. That is the design this",
        "dataset should eventually carry, and the matching code is here and",
        "tested. It has no names in it because a name in that file asserts that",
        "a real, often living person was tied to an authoritarian regime, which",
        "needs a citable primary source per row rather than recall. Until it is",
        "populated from the Journal Officiel decrees, `pc_political_figure` is",
        "structurally zero and any claim about regime connection specifically —",
        "as against state connection generally — is out of reach.",
        "",
        "**Coverage is filings-driven.** Connections can only appear in years",
        "and firms the corpus covers; see §6.4 of the codebook. Counting",
        "connected firms per year measures filings as much as politics.",
        "",
        "## Where the officeholder channel actually is",
        "",
        f"Of the firms carrying an officeholder tie, the great majority are "
        f"banks — {', '.join(office_firms[:8])}"
        + (", …" if len(office_firms) > 8 else "") + ".",
        "",
        "That is a finding rather than a defect: Tunisian bank boards seat",
        "ministry officials, central-bank staff and named state",
        "representatives, and they say so in their filings. But it means the",
        "officeholder channel is close to a *bank* indicator in this corpus,",
        "and should not be entered into a regression alongside a sector",
        "control without checking what is left of it.",
        "",
        "Note also what is absent. **No sitting minister appears on any board",
        "in this corpus.** The strongest personal ties observed are, counted",
        "as distinct printed titles rather than as people:",
        "",
        *[f"- {n} × `{cat}` ({tenure})" for (cat, tenure), n in personal_titles],
        "",
        "Those are title *occurrences*, deduplicated on the text. They are not",
        "a headcount: one director at BIAT is an ex-minister and an ex-deputy",
        "governor of the central bank and so appears under both, and a name",
        "printed once in capitals and once in mixed case counts twice. The",
        "evidence file carries no resolved person id, so a true headcount",
        "needs the person layer joined on `counterpart`. Either way the order",
        "of magnitude is the point: Faccio's own definition, applied strictly,",
        "is close to empty in this corpus.",
        "",
        f"## Entity-resolution debris: {n_debris} evidence rows ({n_debris / max(len(evidence), 1):.1%})",
        "",
        f"{len(debris)} of the coded 'firms' are not companies at all but",
        "extraction debris — a prospectus title fragment, a parenthetical",
        "date, a committee name — carrying "
        f"{n_debris} evidence rows between them"
        + (f": {', '.join(repr(d) for d in debris[:4])}." if debris else "."),
        "",
        "The *evidence* on them is usually real: `D'ADMISSION` carries a",
        "ministry representative on a 1990 board, correctly read from the",
        "page, but attached to the issuer name a scanned prospectus title",
        "yielded instead of the bank's. These rows are left in the output",
        "rather than filtered, because dropping them would hide the defect",
        "instead of measuring it. Exclude them on `entity_id` if the firm",
        "list matters for your specification.",
        "",
        "## Choices a reader should check rather than inherit",
        "",
        "- **Civil servants count as officeholders.** Tunisian boards seat",
        "  ministry staff far more often than ministers. They are a separate",
        "  `category`, so they can be dropped, but they are in `pc_officeholder`.",
        "- **Former office is flagged, not dropped** (`pc_officeholder_former`),",
        "  after Hillman (2005). It is excluded from `pc_narrow`.",
        "- **Public-bank subsidiaries are excluded.** A stake in a bank's",
        "  leasing arm is not a credit relationship with the bank.",
        "- **The public-bank channel is a governance tie, not lending.** The",
        "  filings do not show loans, so it is outside `pc_narrow`.",
        "",
        "## Files",
        "",
        "`political_connections.csv` is the firm-year panel.",
        "`political_connection_evidence.csv` is one row per supporting record,",
        "each carrying the document URL and page, so every coded 1 can be read",
        "back to the filing that produced it.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    rules = load_rules()
    log.info("rules: %d office titles, %d state-owned firms, %d named figures",
             len(rules.office), len(rules.state_firm), len(rules.figures))
    if not rules.figures:
        log.warning("the political_figure roster is empty; pc_political_figure "
                    "will be zero everywhere (see the config file for why)")

    res = Resolver()
    from .build_dataset import seed_evidence
    seed_evidence(res)

    evidence = from_edges(read_edges(), rules) + from_records(rules, res)
    evidence.sort(key=lambda e: (e["canonical_name"], e["year"], e["channel"]))
    panel = to_panel(evidence)

    write_csv(EVIDENCE_OUT, evidence, EVIDENCE_FIELDS)
    write_csv(PANEL_OUT, panel, PANEL_FIELDS)
    text = report(panel, evidence, rules)
    REPORT_OUT.write_text(text, encoding="utf-8")
    log.info("wrote %s", REPORT_OUT)
    print(text)


if __name__ == "__main__":
    main()
