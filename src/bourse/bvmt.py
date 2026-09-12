"""Harvest the Bourse de Tunis (BVMT) listed-securities roster.

The BVMT public REST API exposes the current state of the cote. It is the
authoritative spine for firm identity (ISIN + ticker), but it is a *snapshot*:
it knows nothing about firms that left the cote. Historical entries and exits
are recovered separately from CMF admission/withdrawal notices
(see :mod:`elitenet.extract.events`), which is why ``listed_status`` here is
recorded as "observed on the cote at ``snapshot_date``" rather than as a
listing-history claim.
"""

from __future__ import annotations

import csv
import json

from .common import PROCESSED, RAW, Fetcher, log, now_iso, sha256_bytes

API = "https://www.bvmt.com.tn/rest_api/rest/market/groups/11,12,52,99"

# BVMT trading-group codes, as used by the API's ``referentiel.valGroup``.
GROUP_LABELS = {
    "11": "continuous",       # Marche principal, cotation en continu
    "12": "fixing",           # Marche principal / alternatif, cotation au fixing
    "52": "alternative",      # Marche alternatif
    "99": "suspended_other",  # Suspendu, en reprise, ou regime particulier
}


def fetch_roster(fetcher: Fetcher | None = None) -> dict:
    f = fetcher or Fetcher(min_delay=0.5)
    raw = f.get(API, binary=True, min_bytes=1000)
    if raw is None:
        raise RuntimeError("BVMT roster endpoint unreachable")
    payload = json.loads(raw.decode("utf-8"))
    snap = RAW / f"bvmt_roster_{now_iso()[:10]}.json"
    snap.write_bytes(raw)
    log.info("BVMT snapshot -> %s (sha256 %s)", snap.name, sha256_bytes(raw)[:12])
    return payload


def roster_rows(payload: dict) -> list[dict]:
    rows = []
    seen = set()
    for m in payload.get("markets", []):
        ref = m.get("referentiel") or {}
        isin = (ref.get("isin") or m.get("isin") or "").strip()
        if not isin or isin in seen:
            continue
        seen.add(isin)
        group = str(ref.get("valGroup") or "").strip()
        rows.append(
            {
                "isin": isin,
                "ticker": (ref.get("ticker") or "").strip(),
                "name_fr": (ref.get("stockName") or "").strip(),
                "name_ar": (ref.get("arabName") or "").strip(),
                "bvmt_group": group,
                "bvmt_group_label": GROUP_LABELS.get(group, "unknown"),
                "last_price_tnd": m.get("last"),
                "market_cap_kdt": m.get("caps"),
                "snapshot_seance": m.get("seance"),
                "source": "BVMT REST API",
                "source_url": API,
                "retrieved_at": now_iso(),
            }
        )
    rows.sort(key=lambda r: r["name_fr"])
    return rows


def write_roster(rows: list[dict]) -> None:
    out = PROCESSED / "bvmt_listed_securities.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log.info("wrote %d securities -> %s", len(rows), out.relative_to(out.parents[2]))


def main() -> None:
    rows = roster_rows(fetch_roster())
    write_roster(rows)


if __name__ == "__main__":
    main()
