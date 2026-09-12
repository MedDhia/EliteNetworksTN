"""Stage 10 -- re-index the yearly panel into TERGM-estimable inputs.

`btergm` wants a *list of network objects*, one per period, with a declared
bipartite split, a vertex set that does not move under it, an explicit risk
set, and covariates attached. The panel tables shipped by stage 8 are none of
those: they are edge lists, and an edge list built into a network contains only
the nodes that happen to hold a tie that year, so isolates vanish and the
vertex set silently changes between periods.

This stage does not recompute the panel. It re-indexes it, and adds the four
things an edge list cannot carry:

* **A mode-blocked vertex key.** Every person takes an id below every
  organisation, so `bipartite = n1` is a true statement about the ordering.
  Without it a person-person dyad -- structurally impossible in this network --
  sits in the reference distribution and biases `edges` and every degree term.
* **A risk set.** A firm constituted in 2010 is not a non-tie in 2008; it did
  not exist. Treating it as a structural zero rather than an observed absence
  moves every coefficient.
* **Nodal covariates**, including the lagged degree that `nodecov` needs if it
  is not to be a function of the ties being modelled.
* **Dyadic covariates** projected from the seed sheet's kinship and
  shareholding ties. Those ties carry no dates, so they can never be endogenous
  in a temporal model -- but lagged into person x organisation space they are
  exactly the elite-reproduction mechanisms one would want to test.

What this stage cannot fix is the censoring: 82% of dated spells are
right-censored, because the gazette publishes arrivals far more reliably than
departures. A dissolution model fitted here would estimate when an exit gets
*printed*. See docs/TERGM-multiplex.md before specifying one.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date, datetime

from .paths import PROCESSED, ensure_dirs
from .spells import periods

OUT = PROCESSED / "exports" / "tergm"

# Person-person and organisation-organisation seed ties, by tie_class. These
# never enter the panel -- they are undated -- and are used here only to build
# lagged dyadic covariates.
KIN_CLASSES = {"kinship"}
PEDAGOGIC_CLASSES = {"pedagogic"}
OWNERSHIP_LABELS = {"SHAREHOLDER"}

# Every dyadic covariate, defaulting to absent. Named once so a new covariate
# cannot be added to the writer and forgotten in the accumulator.
BLANK_COV = {"kin_in_org": 0, "owner_of": 0, "owner_of_seed": 0,
             "prior_comembership": 0, "is_shareholder": 0}

# Administrative prefixes the segmenter leaves on an otherwise sound name.
# The organisation is real; only the label needs trimming.
LABEL_PREFIX = re.compile(r"^\s*Nom\s+de\s+l['’]association\s*:\s*", re.IGNORECASE)

# Names that are not firm names, applied only to gazette-discovered
# organisations. Length is deliberately NOT a test: Tunisian corporate names
# routinely run past sixty characters ("Societe d'Engrais et de Produits
# Chimiques de Megrine S.E.P.C.M" is a real firm), and an early version of this
# rule flagged four of them. What actually separates a clause from a name is
# clause structure -- a conjugated verb, or an opener like "Decide de" -- plus
# addresses and bare role fragments.
NOT_A_FIRM_NAME = re.compile(
    r"^\s*$"
    r"|^\("
    r"|\b(?:rue|avenue|boulevard|immeuble|r[eé]sidence)\b"
    r"|^(?:accept|d[eé]cid|approuv|autoris|nomm|d[eé]charg|d[eé]p[oô]t"
    r"|cet\s+avis|en\s+remplacement|mise\s+[aà]\s+jour|d[eé]l[eé]gu[eé]\b)"
    r"|^(?:directeur|pr[eé]sident|g[eé]rant|adjoint)\b"
    r"|\b(?:a\s+[eé]t[eé]|qui\s+a)\b",
    re.IGNORECASE,
)


def _d(iso: str) -> date | None:
    if not iso:
        return None
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _read(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        # The org-org layer is optional: tergm still builds without it, with
        # owner_of simply empty rather than the stage failing.
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def org_lifecycle(events: list[dict], resolution: list[dict]) -> tuple[dict, dict]:
    """Earliest constitution and earliest dissolution date per organisation id.

    `events.csv` names organisations by surface mention, not by node id: the
    mention-to-id map lives in `resolution.csv`. A firm can be constituted once
    and dissolved once, so the earliest of each is the whole lifecycle; taking
    the earliest dissolution is the conservative reading, since a later
    "liquidated" notice for the same firm is the same death being reported
    again rather than a second one.
    """
    # A mention that resolves to more than one organisation cannot date any of
    # them, so it is dropped rather than arbitrarily assigned to the first.
    # Exactly one mention in the corpus does this -- "Mise a jour des statuts",
    # a section heading that org_name() mistakes for a firm on 87 events -- and
    # keeping it would have stamped three unrelated firms with one birth date.
    candidates: dict[str, set[str]] = defaultdict(set)
    for r in resolution:
        om, oid = r.get("org_mention"), r.get("resolved_org_id")
        if om and oid:
            candidates[om].add(oid)
    mention_to_id = {om: next(iter(ids)) for om, ids in candidates.items()
                     if len(ids) == 1}

    birth: dict[str, date] = {}
    death: dict[str, date] = {}
    for e in events:
        oid = mention_to_id.get(e.get("org_mention") or "")
        d = _d(e.get("event_date") or "")
        if not oid or not d:
            continue
        t = e["event_type"]
        if t == "constituted" and (oid not in birth or d < birth[oid]):
            birth[oid] = d
        elif t in ("dissolved", "liquidated") and (oid not in death or d < death[oid]):
            death[oid] = d
    return birth, death


def build(panel: list[dict], spells: list[dict], seed_nodes: list[dict],
          seed_edges: list[dict], events: list[dict],
          resolution: list[dict],
          org_panel: list[dict] | None = None) -> dict:
    """Re-index the yearly panel. Returns the five tables plus a diagnostics dict."""
    pers = periods("yearly")
    period_ids = [p for p, _s, _e in pers]
    bounds = {p: (s, e) for p, s, e in pers}

    # --- vertex universe, mode-blocked -----------------------------------
    # Fixed across periods: the union over the whole window. A node with no tie
    # in a given year is an isolate that year, not an absent vertex, and the
    # difference is the entire point of carrying a separate risk set.
    persons = sorted({r["from_node_id"] for r in panel})
    orgs = sorted({r["to_node_id"] for r in panel})
    n1 = len(persons)
    vid = {n: i + 1 for i, n in enumerate(persons)}
    vid.update({n: n1 + i + 1 for i, n in enumerate(orgs)})

    seed = {r["node_id"]: r for r in seed_nodes}
    # Gazette-discovered nodes are absent from the curated seed sheet, so their
    # names come from the spell that found them.
    from_spells: dict[str, str] = {}
    for s in spells:
        for key, lbl in ((s["person_id"], s["person_label"]),
                         (s["org_id"], s["org_label"])):
            if lbl:
                from_spells.setdefault(key, lbl)

    node_key = []
    suspect = 0
    for i, n in enumerate(persons + orgs):
        label = (seed.get(n) or {}).get("label") or from_spells.get(n, "")
        label = LABEL_PREFIX.sub("", label).strip()
        # org_name() occasionally returns something that is not a firm name --
        # a registered address, a fragment of a role clause, a whole sentence.
        # Those become vertices that absorb ties and distort the degree
        # distribution every bipartite term is estimated from, so they are
        # flagged. They are not dropped here: removing them would change the
        # panel, and this stage only re-indexes it. Curated seed labels are
        # trusted and never flagged.
        bad = n not in seed and bool(NOT_A_FIRM_NAME.search(label or " "))
        suspect += bad
        node_key.append({
            "vertex_id": vid[n],
            "node_id": n,
            "label": label,
            "mode": 1 if i < n1 else 2,
            "node_type": (seed.get(n) or {}).get(
                "node_type", "PERSON" if i < n1 else "ORG"),
            "is_seed": int(n in seed),
            "label_suspect": int(bad),
        })

    # --- edges, deduplicated to binary ties ------------------------------
    # A person can hold two roles in one firm in one year, which is two panel
    # rows and one tie. TERGM is a binary-tie model, so the roles are collapsed
    # and kept in `roles` for reference rather than silently dropped.
    st = {s["spell_id"]: s for s in spells}
    CERT_RANK = {"certain": 0, "probable": 1, "possible": 2}
    agg: dict[tuple[str, int, int], dict] = {}
    for r in panel:
        key = (r["panel_id"].split(":", 1)[1], vid[r["from_node_id"]],
               vid[r["to_node_id"]])
        s = st.get(r["spell_id"], {})
        # An observed terminus, as opposed to a spell we never saw end.
        diss = int(bool(s.get("terminus")) and s.get("right_censored") == "False")
        cur = agg.get(key)
        if cur is None:
            agg[key] = {
                "period": key[0], "tail": key[1], "head": key[2],
                "roles": {r["role_canonical"]}, "certainty": r["certainty"],
                "link_status": s.get("link_status", ""),
                "dissolution_observed": diss,
            }
        else:
            cur["roles"].add(r["role_canonical"])
            # Keep the strongest evidence available for the tie.
            if CERT_RANK[r["certainty"]] < CERT_RANK[cur["certainty"]]:
                cur["certainty"] = r["certainty"]
            if s.get("link_status") == "resolved":
                cur["link_status"] = "resolved"
            cur["dissolution_observed"] = max(cur["dissolution_observed"], diss)
    edges = []
    for e in sorted(agg.values(), key=lambda x: (x["period"], x["tail"], x["head"])):
        e = dict(e)
        e["role_canonical"] = "|".join(sorted(e.pop("roles")))
        edges.append(e)

    # Ties held per period, as vertex ids -- the basis of every lag below.
    ties_by_period: dict[str, set[tuple[int, int]]] = {p: set() for p in period_ids}
    for e in edges:
        ties_by_period[e["period"]].add((e["tail"], e["head"]))

    # --- risk set ---------------------------------------------------------
    birth, death = org_lifecycle(events, resolution)
    first_year, last_year = int(period_ids[0]), int(period_ids[-1])

    # An organisation's risk window is an interval, and it is widened -- never
    # punched through -- to cover every period in which a tie is actually
    # observed. Two reasons:
    #
    #  * The risk set must contain every observed tie. Excluding a period in
    #    which a tie exists would make that tie a structural zero, which no
    #    estimator can accept.
    #  * Forcing only the contradicting periods would leave activity
    #    non-contiguous (at risk in 2008, absent 2009-2011, back in 2012),
    #    asserting that a firm blinked out of existence and returned. The
    #    dates are what is unreliable there, not the firm.
    #
    # Widening past a dissolution date is usually not even an error: a
    # dissolved company still has a liquidator appointed, and that appointment
    # is a real tie postdating the death. Widening past a constitution date
    # generally is an error -- a mis-typed re-registration, or a mention
    # resolved to the wrong firm -- so the two are counted separately.
    widened_start = widened_end = 0
    activity = []
    tie_years: dict[int, list[int]] = defaultdict(list)
    for p in period_ids:
        for _t, h in ties_by_period[p]:
            tie_years[h].append(int(p))
    for n in orgs:
        v = vid[n]
        b, d = birth.get(n), death.get(n)
        lo = b.year if b else first_year
        hi = d.year if d else last_year
        seen = tie_years.get(v)
        if seen:
            if min(seen) < lo:
                widened_start += 1
                lo = min(seen)
            if max(seen) > hi:
                widened_end += 1
                hi = max(seen)
        lo, hi = max(lo, first_year), min(hi, last_year)
        for p in period_ids:
            activity.append({
                "period": p, "vertex_id": v,
                "active": int(lo <= int(p) <= hi),
                "birth_known": int(b is not None),
                "death_known": int(d is not None),
                "risk_start": lo, "risk_end": hi,
            })
    for n in persons:
        # A person's existence is not observable from the gazette: it records
        # appointments, not births or deaths. Persons are therefore at risk
        # throughout, which is an assumption rather than a measurement.
        for p in period_ids:
            activity.append({
                "period": p, "vertex_id": vid[n], "active": 1,
                "birth_known": 0, "death_known": 0,
                "risk_start": first_year, "risk_end": last_year,
            })
    activity.sort(key=lambda r: (r["period"], r["vertex_id"]))

    # --- nodal covariates -------------------------------------------------
    kin_deg: dict[str, int] = defaultdict(int)
    ped_deg: dict[str, int] = defaultdict(int)
    owns: dict[str, set[str]] = defaultdict(set)     # company -> companies it holds
    holds_shares: dict[str, set[str]] = defaultdict(set)  # person -> companies
    kin_of: dict[str, set[str]] = defaultdict(set)   # person -> kin persons
    for r in seed_edges:
        a, b = r["from_node_id"], r["to_node_id"]
        cls, raw = r["tie_class"], r["edge_label_raw"]
        if cls in KIN_CLASSES:
            kin_deg[a] += 1
            kin_deg[b] += 1
            kin_of[a].add(b)
            kin_of[b].add(a)
        elif cls in PEDAGOGIC_CLASSES:
            ped_deg[a] += 1
            ped_deg[b] += 1
        elif raw in OWNERSHIP_LABELS:
            # from = shareholder, to = company (see seed_edges.edge_label_raw).
            # Both person-held and company-held stakes arrive here; they feed
            # different covariates, so they are separated by the mode of the
            # holder rather than lumped together.
            if (seed.get(a) or {}).get("node_type") == "PERSON":
                holds_shares[a].add(b)
            else:
                owns[a].add(b)

    # Ownership active per period, holder -> companies, from the dated layer.
    owns_at: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in (org_panel or []):
        if r.get("is_ownership") != "1" or r.get("evidence_tier") != "gazette_dated":
            continue
        period = r["panel_id"].split(":", 1)[1]
        owns_at[period][r["from_node_id"]].add(r["to_node_id"])

    first_seen: dict[int, str] = {}
    for p in period_ids:
        for t, h in ties_by_period[p]:
            first_seen.setdefault(t, p)
            first_seen.setdefault(h, p)

    node_attrs = []
    cum: dict[int, set[int]] = defaultdict(set)
    for p in period_ids:
        # Degree accumulated *before* this period. A covariate measured at t is
        # a function of the ties being modelled at t; the lag is what keeps it
        # exogenous, so it is the one to use in `nodecov`.
        lag = {v: len(alters) for v, alters in cum.items()}
        for t, h in ties_by_period[p]:
            cum[t].add(h)
            cum[h].add(t)
        for i, n in enumerate(persons + orgs):
            v = vid[n]
            fs = first_seen.get(v)
            node_attrs.append({
                "period": p, "vertex_id": v, "node_id": n,
                "mode": 1 if i < n1 else 2,
                "node_type": (seed.get(n) or {}).get(
                    "node_type", "PERSON" if i < n1 else "ORG"),
                "is_seed": int(n in seed),
                "seed_degree": (seed.get(n) or {}).get("seed_degree", "0") or "0",
                "first_seen_year": fs or "",
                "tenure_years": (int(p) - int(fs)) if fs and int(fs) <= int(p) else "",
                "cum_degree": len(cum[v]),
                "cum_degree_lag": lag.get(v, 0),
                "kin_degree": kin_deg.get(n, 0),
                "pedagogic_degree": ped_deg.get(n, 0),
            })

    # --- dyadic covariates, lagged to t-1 ---------------------------------
    # Emitted as sparse triplets: dense would be n1 x n2 per period, about 6.3
    # million cells for 2012 alone. The R side densifies.
    id_of = {v: n for n, v in vid.items()}
    dyads = []

    # A direct personal shareholding is read off the seed sheet, carries no
    # date, and is therefore exogenous without needing a lag -- so unlike the
    # other three it is emitted for every period, including the first, where it
    # is the only dyadic predictor available.
    share_dyads: dict[tuple[str, int, int], dict] = {}
    for p in period_ids:
        for pn, companies in holds_shares.items():
            if pn not in vid:
                continue
            for c in companies:
                if c in vid:
                    share_dyads[(p, vid[pn], vid[c])] = 1

    for prev, p in zip(period_ids, period_ids[1:]):
        prev_ties = ties_by_period[prev]
        orgs_of: dict[int, set[int]] = defaultdict(set)
        members_of: dict[int, set[int]] = defaultdict(set)
        for t, h in prev_ties:
            orgs_of[t].add(h)
            members_of[h].add(t)

        acc: dict[tuple[int, int], dict] = {}

        def bump(t: int, h: int, field: str) -> None:
            acc.setdefault((t, h), dict(BLANK_COV))[field] = 1

        for pn in persons:
            pv = vid[pn]
            # i is kin to someone who held a post in j at t-1.
            for kn in kin_of.get(pn, ()):
                for h in orgs_of.get(vid.get(kn, -1), ()):
                    bump(pv, h, "kin_in_org")
            # i held a post at t-1 in an organisation that is a shareholder of j.
            held = orgs_of.get(pv, set())
            for o in held:
                # Dated ownership: the holding company's stakes as they stood in
                # the lagged period, from the org-org layer. This used to be the
                # undated seed sheet applied to every period alike, which
                # asserted a 2020 shareholding in 1994.
                for company in owns_at.get(prev, {}).get(id_of[o], ()):
                    if company in vid:
                        bump(pv, vid[company], "owner_of")
                # The undated seed component is kept as its own covariate
                # rather than folded in: it carries no date, so mixing it with
                # the dated series would smuggle a time-invariant term into one
                # that is supposed to vary.
                for company in owns.get(id_of[o], ()):
                    if company in vid:
                        bump(pv, vid[company], "owner_of_seed")
            # i shared an organisation at t-1 with someone who held a post in j.
            for o in held:
                for k in members_of.get(o, ()):
                    if k == pv:
                        continue
                    for h in orgs_of.get(k, ()):
                        bump(pv, h, "prior_comembership")

        for (t, h), vals in acc.items():
            dyads.append({"period": p, "tail": t, "head": h, **vals})

    # Fold the shareholding flag into the lagged rows, adding a row wherever a
    # shareholding is the only signal on that dyad.
    by_key = {(r["period"], r["tail"], r["head"]): r for r in dyads}
    for (p, t, h) in share_dyads:
        row = by_key.get((p, t, h))
        if row is None:
            row = {"period": p, "tail": t, "head": h, **BLANK_COV}
            by_key[(p, t, h)] = row
            dyads.append(row)
        row["is_shareholder"] = 1
    dyads.sort(key=lambda r: (r["period"], r["tail"], r["head"]))

    return {
        "node_key": node_key, "edges": edges, "activity": activity,
        "node_attrs": node_attrs, "dyads": dyads,
        "diag": {"n_persons": n1, "n_orgs": len(orgs), "periods": len(period_ids),
                 "panel_rows": len(panel), "binary_ties": len(edges),
                 "risk_widened_start": widened_start,
                 "risk_widened_end": widened_end,
                 "orgs_with_birth": len(set(orgs) & set(birth)),
                 "orgs_with_death": len(set(orgs) & set(death)),
                 "dyad_cov_rows": len(dyads),
                 "label_suspect": suspect,
                 "unlabelled": sum(1 for r in node_key if not r["label"])},
    }


def run() -> dict:
    ensure_dirs()
    tables = build(
        panel=_read("panel_edges_yearly.csv"),
        spells=_read("spells.csv"),
        seed_nodes=_read("seed_nodes.csv"),
        seed_edges=_read("seed_edges.csv"),
        events=_read("events.csv"),
        resolution=_read("resolution.csv"),
        org_panel=_read("panel_org_ties_yearly.csv"),
    )
    _write(OUT / "node_key.csv", tables["node_key"],
           ["vertex_id", "node_id", "label", "mode", "node_type", "is_seed",
            "label_suspect"])
    _write(OUT / "edges_yearly.csv", tables["edges"],
           ["period", "tail", "head", "role_canonical", "certainty",
            "link_status", "dissolution_observed"])
    _write(OUT / "vertex_activity_yearly.csv", tables["activity"],
           ["period", "vertex_id", "active", "birth_known", "death_known",
            "risk_start", "risk_end"])
    _write(OUT / "node_attrs_yearly.csv", tables["node_attrs"],
           ["period", "vertex_id", "node_id", "mode", "node_type", "is_seed",
            "seed_degree", "first_seen_year", "tenure_years", "cum_degree",
            "cum_degree_lag", "kin_degree", "pedagogic_degree"])
    _write(OUT / "dyad_cov_yearly.csv", tables["dyads"],
           ["period", "tail", "head", *BLANK_COV])
    d = tables["diag"]
    print(f"TERGM panel written to {OUT}")
    print(f"  vertices: {d['n_persons']} persons (mode 1) + {d['n_orgs']} orgs "
          f"(mode 2); bipartite = {d['n_persons']}")
    print(f"  periods: {d['periods']}")
    print(f"  binary ties: {d['binary_ties']} (from {d['panel_rows']} panel rows)")
    print(f"  orgs with a constitution date: {d['orgs_with_birth']}/{d['n_orgs']}; "
          f"with a dissolution date: {d['orgs_with_death']}")
    print(f"  risk window widened to cover an observed tie: "
          f"{d['risk_widened_start']} before a constitution date, "
          f"{d['risk_widened_end']} after a dissolution date")
    print(f"  dyad covariate rows: {d['dyad_cov_rows']}")
    print(f"  vertices flagged label_suspect: {d['label_suspect']} "
          f"(still unlabelled: {d['unlabelled']})")
    return d


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Re-index the yearly panel for TERGM.").parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
