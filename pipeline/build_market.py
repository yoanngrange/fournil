"""Bakery market: openings, closures and takeovers per commune (SIRENE), business prices (BODACC).

Only aggregates leave this module: counts per commune, price statistics per département.
"""

import json
import re
from datetime import date

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pipeline import cog, fetch
from pipeline.config import (
    FONDS_MIN_SALES,
    FONDS_PRICE_RANGE,
    FONDS_YEARS,
    HISTORY_FROM,
    NAF_BAKERY,
    TAKEOVER_WINDOW_DAYS,
)


# ---------- Openings, closures, takeovers (SIRENE) ----------


def _bakery_events() -> pd.DataFrame:
    """Every bakery establishment (10.71C) opened or closed since HISTORY_FROM, one row per event."""
    t = pq.read_table(
        fetch.path("sirene"),
        columns=[
            "siret",
            "codeCommuneEtablissement",
            "etatAdministratifEtablissement",
            "dateCreationEtablissement",
            "dateDebut",
        ],
        filters=pc.field("activitePrincipaleEtablissement") == NAF_BAKERY,
    ).to_pandas()
    t.columns = ["siret", "code", "state", "created", "since"]
    t = t[t.code.notna()]
    mapping = cog.code_mapping()
    t["code"] = t.code.map(lambda c: mapping.get(c, c))
    t["siren"] = t.siret.str[:9]
    for col in ("created", "since"):
        t[col] = pd.to_datetime(t[col], errors="coerce")
    start = pd.Timestamp(HISTORY_FROM)
    # For a closed establishment, dateDebut is the start of its last period, i.e. the closure date.
    opened = t[t.created >= start].assign(kind="open", day=lambda d: d.created)
    closed = t[(t.state == "F") & (t.since >= start)].assign(kind="close", day=lambda d: d.since)
    return pd.concat([opened, closed])[["code", "siren", "kind", "day"]]


def _match(events: pd.DataFrame) -> dict:
    """Pair each closure with the nearest opening by another company in the same commune."""
    window = pd.Timedelta(days=TAKEOVER_WINDOW_DAYS)
    opens = events[events.kind == "open"].sort_values("day")
    closes = events[events.kind == "close"].sort_values("day")
    used = set()
    takeovers = moves = 0
    for _, c in closes.iterrows():
        near = opens[((opens.day - c.day).abs() <= window) & ~opens.index.isin(used)]
        if near.empty:
            continue
        best = (near.day - c.day).abs().idxmin()
        used.add(best)
        if opens.at[best, "siren"] == c.siren:
            moves += 1  # same company closing one site and opening another: a move, not a sale
        else:
            takeovers += 1
    paired = takeovers + moves
    return {
        "takeovers": takeovers,
        "openings": len(opens) - paired,
        "closures": len(closes) - paired,
    }


def bakery_history(codes: set[str]) -> pd.DataFrame:
    """Per commune since HISTORY_FROM: takeovers, new bakeries, closures without a successor."""
    events = _bakery_events()
    events = events.reset_index(drop=True)
    rows = {code: _match(g) for code, g in events[events.code.isin(codes)].groupby("code")}
    out = pd.DataFrame.from_dict(rows, orient="index").reindex(sorted(codes)).fillna(0).astype(int)
    return out.add_prefix("hist_")


# ---------- Price of a bakery business (BODACC) ----------

_AMOUNT = re.compile(r"(?:prix|montant)[^0-9]{0,60}?([0-9][0-9 .,  ]*)\s*(?:€|eur)", re.I)


def parse_price(text: str) -> float | None:
    """'… au prix stipulé de 250 000,00 euros' -> 250000.0 (handles 250000.00, 250.000,00, 250 000 €)."""
    m = _AMOUNT.search(text or "")
    if not m:
        return None
    s = re.sub(r"[   ]", "", m.group(1)).rstrip(".,")
    decimals = re.search(r"[.,](\d{1,2})$", s)
    if decimals:
        s = s[: decimals.start()]
    s = re.sub(r"[.,]", "", s)
    return float(s) if s else None


def _sales() -> pd.DataFrame:
    with open(fetch.path("bodacc"), encoding="utf-8") as f:
        notices = json.load(f)
    rows = []
    for n in notices:
        if n.get("typeavis") not in (None, "annonce"):  # skip corrections and cancellations
            continue
        try:
            etab = json.loads(n.get("listeetablissements") or "{}").get("etablissement", {})
        except ValueError:
            continue
        if isinstance(etab, list):
            etab = etab[0] if etab else {}
        origin = etab.get("origineFonds") or ""
        # Purchases only: contributions in kind, leases and management contracts are not sales.
        if not re.search(r"achat|acquis|adjudication", origin, re.I) or re.search(r"apport|location", origin, re.I):
            continue
        if not re.search(r"boulang", etab.get("activite") or "", re.I):
            continue
        rows.append({"day": n.get("dateparution"), "dep": n.get("numerodepartement"), "cp": n.get("cp"), "price": parse_price(origin)})
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df.day, errors="coerce")
    lo, hi = FONDS_PRICE_RANGE
    df = df[df.price.between(lo, hi)]
    # The same sale can be published twice (provisional insertion, then registration).
    return df.assign(year=df.day.dt.year).drop_duplicates(["cp", "price", "year"])


def fonds_prices(deps: set[str], today: date | None = None) -> dict:
    """Median and quartiles of bakery business prices over the last FONDS_YEARS, per département and nationally."""
    today = today or date.today()
    since = pd.Timestamp(today.replace(year=today.year - FONDS_YEARS))
    df = _sales()
    df = df[df.day >= since]

    def stats(s: pd.Series) -> dict:
        return {
            "n": int(s.size),
            "median": int(round(s.median(), -3)),
            "q1": int(round(s.quantile(0.25), -3)),
            "q3": int(round(s.quantile(0.75), -3)),
        }

    by_dep = {
        dep: stats(g.price)
        for dep, g in df.groupby("dep")
        if dep in deps and len(g) >= FONDS_MIN_SALES
    }
    return {
        "since": since.strftime("%Y-%m-%d"),
        "min_sales": FONDS_MIN_SALES,
        "france": stats(df.price),
        "departements": by_dep,
    }
