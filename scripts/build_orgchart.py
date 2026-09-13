"""Emit the reconstructed state organisation chart as a table.

Writes ``data/processed/org_hierarchy.csv.gz``: one row per body, carrying the
parent it was attached to, how that attachment was obtained and how much the
evidence is worth, plus the years the body was actually recorded.

The chart is a union over 1957–2026 and shows bodies that never coexisted. The
year columns are there so it can be cut back to a period; read as a snapshot
of the state at any instant it will be wrong.

Run with ``python scripts/build_orgchart.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import MINISTRY_ENGLISH, ministry_of  # noqa: E402
from orgchart import (  # noqa: E402
    MODAL_FLOOR, chain, clean, fold, modal_parent, resolve, split_parent,
    wellformed,
)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
STATE = "STATE"

# Bodies that answer to no ministry. A court belongs to the judicial order and
# a commune to its own council; both are supervised by a ministry but neither
# is a directorate of one, and the chart says so by hanging them off the state
# rather than pretending the supervision is ownership.
TOP_FORMS = {"presidence"}


def load():
    o = pd.read_csv(PROC / "organisations.csv.gz", low_memory=False)
    s = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    o["org_name"] = o.org_name.fillna("")
    o["org_form"] = o.org_form.fillna("autre")
    s["parent_org_name"] = s.parent_org_name.fillna("")
    return o, s


def build(o: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    by_name: dict[str, str] = {}
    for oid, nm in zip(o.org_id, o.org_name):
        k = fold(clean(nm))
        if k and k not in by_name:
            by_name[k] = oid

    modal = (s[s.parent_org_name != ""].groupby("org_id").parent_org_name
             .apply(lambda x: modal_parent(x)))

    rows = []
    for r in o.itertuples():
        name = clean(r.org_name)
        pid = parent_name = None
        method = "none"
        conf = 0.0

        # 1. what the body's own name says. Best evidence: it is a statement
        #    about the body rather than about an act that mentioned it.
        if wellformed(r.org_name):
            _, stated = split_parent(r.org_name)
            if stated:
                pid, how = resolve(stated, by_name, ministry_of)
                if pid and pid != r.org_id:
                    parent_name, method, conf = stated, "name", 0.95
                else:
                    pid = None

        # 2. the commonest parent its acts gave it, if they mostly agree.
        if pid is None and r.org_id in modal.index:
            cand, share = modal.loc[r.org_id]
            if cand and share >= MODAL_FLOOR:
                cid, how = resolve(cand, by_name, ministry_of)
                if cid and cid != r.org_id:
                    pid, parent_name, method, conf = cid, cand, "modal_parent", share

        # 3. the portfolio the body itself carries.
        if pid is None:
            m = ministry_of(r.org_portfolio, "")
            if m:
                pid, parent_name, method, conf = f"MIN:{m}", m, "portfolio", 0.5

        # 4. nothing said anything: hang it off the state.
        if pid is None or r.org_form in TOP_FORMS:
            pid, parent_name, method, conf = STATE, None, "form", 0.0

        rows.append({
            "org_id": r.org_id, "name": name, "form": r.org_form,
            "parent_id": pid, "parent_stated": parent_name,
            "method": method, "confidence": round(conf, 3),
            "depth_stated": len(chain(r.org_name)),
            "first_year": r.first_year, "last_year": r.last_year,
            "n_persons": r.n_persons, "n_events": r.n_events,
        })

    df = pd.DataFrame(rows)

    # The canonical ministry nodes the edges point at, plus the root.
    mins = sorted({p for p in df.parent_id if isinstance(p, str)
                   and p.startswith("MIN:")})
    extra = [{"org_id": m, "name": MINISTRY_ENGLISH.get(m[4:], m[4:]),
              "form": "ministere_canonique", "parent_id": STATE,
              "parent_stated": None, "method": "canonical", "confidence": 1.0,
              "depth_stated": 0, "first_year": pd.NA, "last_year": pd.NA,
              "n_persons": pd.NA, "n_events": pd.NA} for m in mins]
    extra.append({"org_id": STATE, "name": "État tunisien", "form": "etat",
                  "parent_id": pd.NA, "parent_stated": None, "method": "root",
                  "confidence": 1.0, "depth_stated": 0, "first_year": pd.NA,
                  "last_year": pd.NA, "n_persons": pd.NA, "n_events": pd.NA})
    return pd.concat([pd.DataFrame(extra), df], ignore_index=True)


def break_cycles(df: pd.DataFrame) -> pd.DataFrame:
    """Re-root anything that ends up in a cycle.

    Two bodies can each name the other — most often a ministry and the state
    secretariat inside it, where the register's naming runs both ways at
    different dates. A cycle is not a tree, and a renderer walking one does not
    come back, so the deeper member is cut loose to the state and the edge it
    lost is recorded in ``method``.
    """
    parent = dict(zip(df.org_id, df.parent_id))
    fixed = 0
    for oid in list(parent):
        seen, cur = {oid}, parent.get(oid)
        while isinstance(cur, str) and cur in parent:
            if cur in seen:
                parent[oid] = STATE
                fixed += 1
                break
            seen.add(cur)
            cur = parent.get(cur)
    if fixed:
        df = df.assign(parent_id=df.org_id.map(parent))
        df.loc[df.parent_id.eq(STATE) & df.method.isin(["name", "modal_parent",
               "portfolio"]), "method"] = "cycle_cut"
    print(f"  cycles broken: {fixed}")
    return df


def main() -> None:
    print("loading…")
    o, s = load()
    print("building…")
    df = build(o, s)
    df = break_cycles(df)

    out = PROC / "org_hierarchy.csv.gz"
    # mtime pinned so an unchanged rebuild produces identical bytes, as the
    # other tables in this repository do.
    df.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})
    print(f"  wrote {out.relative_to(ROOT)}  ({len(df):,} nodes)")

    print("\nattachment method:")
    print(df.method.value_counts().to_string())
    real = df[~df.org_id.isin([STATE]) & ~df.org_id.str.startswith("MIN:")]
    print(f"\nbodies: {len(real):,}")
    print(f"  attached to something other than the bare state: "
          f"{(real.parent_id != STATE).sum():,} "
          f"({(real.parent_id != STATE).mean() * 100:.1f}%)")


if __name__ == "__main__":
    main()
