"""Local context per commune: size of businesses and main employers (SIRENE), mayor and 2026 election.

Main employers are companies or public bodies only (never a sole trader, whose name is a person's),
and only establishments that agreed to public release in SIRENE.
"""

import re

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pipeline import cog, fetch

# SIRENE workforce brackets (trancheEffectifs) grouped for display.
SIZE_GROUPS = {
    "none": ["NN", "00", None],  # no employee (or not reported)
    "1_9": ["01", "02", "03"],
    "10_49": ["11", "12"],
    "50_249": ["21", "22", "31"],
    "250_plus": ["32", "41", "42", "51", "52", "53"],
}
SIZE_LABELS = {
    "11": "10 à 19", "12": "20 à 49", "21": "50 à 99", "22": "100 à 199", "31": "200 à 249",
    "32": "250 à 499", "41": "500 à 999", "42": "1 000 à 1 999", "51": "2 000 à 4 999",
    "52": "5 000 à 9 999", "53": "10 000 et plus",
}
TOP_EMPLOYERS = 3
SOLE_TRADER = "1000"  # categorieJuridiqueUniteLegale of an entrepreneur individuel


def businesses_by_size(codes: set[str]) -> tuple[pd.DataFrame, dict]:
    """Active establishments per size group, and the largest employers (10+ employees) per commune."""
    t = pq.read_table(
        fetch.path("sirene"),
        columns=[
            "siren",
            "codeCommuneEtablissement",
            "trancheEffectifsEtablissement",
            "statutDiffusionEtablissement",
            "enseigne1Etablissement",
            "denominationUsuelleEtablissement",
            "etatAdministratifEtablissement",
        ],
        filters=pc.field("etatAdministratifEtablissement") == "A",
    ).to_pandas()
    t = t.drop(columns="etatAdministratifEtablissement")
    t.columns = ["siren", "code", "size", "public", "sign", "usual_name"]
    mapping = cog.code_mapping()
    t["code"] = t.code.map(lambda c: mapping.get(c, c))
    t = t[t.code.isin(codes)]

    group_of = {code: g for g, cs in SIZE_GROUPS.items() for code in cs if code}
    t["group"] = t["size"].map(group_of).fillna("none")
    counts = pd.crosstab(t.code, t.group).reindex(columns=list(SIZE_GROUPS), fill_value=0)
    counts = counts.reindex(sorted(codes)).fillna(0).astype(int).add_prefix("size_")

    big = t[t["size"].isin(SIZE_LABELS) & (t.public == "O")]
    ul = pq.read_table(
        fetch.path("sirene_ul"),
        columns=["siren", "denominationUniteLegale", "sigleUniteLegale", "categorieJuridiqueUniteLegale", "statutDiffusionUniteLegale"],
        filters=pc.field("siren").isin(big.siren.unique().tolist()),
    ).to_pandas()
    ul.columns = ["siren", "company", "acronym", "legal_form", "ul_public"]
    big = big.merge(ul, on="siren", how="left")
    big = big[(big.legal_form != SOLE_TRADER) & (big.ul_public == "O")]
    big["name"] = big.usual_name.fillna(big.sign).fillna(big.company).fillna(big.acronym)
    big = big[big.name.notna()].sort_values(["code", "size", "name"], ascending=[True, False, True])
    top = {
        code: [{"name": r.name, "employees": SIZE_LABELS[r.size]} for r in g.head(TOP_EMPLOYERS).itertuples()]
        for code, g in big.groupby("code")
    }
    return counts, top


# ---------- Mayor and 2026 municipal election ----------

_PARTICLES = {"de", "du", "des", "la", "le", "d'", "l'"}


def _name_case(s: str) -> str:
    """'CHOMBART DE LAUWE' -> 'Chombart de Lauwe'."""
    words = re.split(r"(\s|-)", s.strip().lower())
    return "".join(w if w in _PARTICLES or w in (" ", "-") else w.capitalize() for w in words)


def _pct(s) -> float | None:
    if not isinstance(s, str) or not s.strip():
        return None
    return float(s.replace("%", "").replace(",", ".").strip())


def _round(path) -> dict:
    df = pd.read_csv(path, sep=";", dtype=str, low_memory=False)
    n_lists = max(int(c.rsplit(" ", 1)[1]) for c in df.columns if c.startswith("Voix "))
    out = {}
    for _, r in df.iterrows():
        lists = []
        for i in range(1, n_lists + 1):
            label = r.get(f"Libellé de liste {i}")
            if not isinstance(label, str):
                label = r.get(f"Libellé abrégé de liste {i}")
            if not isinstance(label, str):
                continue
            seats = r.get(f"Sièges au CM {i}")
            lists.append(
                {
                    "name": label.strip(),
                    "nuance": r.get(f"Nuance liste {i}") if isinstance(r.get(f"Nuance liste {i}"), str) else None,
                    "pct": _pct(r.get(f"% Voix/exprimés {i}")),
                    "seats": int(seats) if isinstance(seats, str) and seats.isdigit() else 0,
                }
            )
        lists.sort(key=lambda x: -(x["pct"] or 0))
        turnout = _pct(r["% Votants"])
        if turnout is not None and not 0 < turnout <= 100:
            turnout = None  # a few rows of the official file are inconsistent (0 %, 101 %)
        out[r["Code commune"]] = {"turnout": turnout, "lists": lists}
    return out


def politics(codes: set[str]) -> dict:
    """Per commune: mayor, the mayor's list and its nuance, turnout and results of each round."""
    t1 = _round(fetch.path("municipales_t1"))
    t2 = _round(fetch.path("municipales_t2"))
    mayors = pd.read_csv(fetch.path("elus_maires"), sep=";", dtype=str)
    mayors = mayors.drop_duplicates("Code de la commune").set_index("Code de la commune")

    out = {}
    for code in codes:
        rounds = [r for r in (t1.get(code), t2.get(code)) if r]
        final = t2.get(code) or t1.get(code)
        winner = max(final["lists"], key=lambda x: x["seats"], default=None) if final else None
        mayor = None
        if code in mayors.index:
            first, last = mayors.at[code, "Prénom de l'élu"], mayors.at[code, "Nom de l'élu"]
            mayor = f"{first.strip()} {_name_case(last)}"  # name only: never birth date or occupation
        out[code] = {
            "mayor": mayor,
            "list": winner["name"] if winner else None,
            "nuance": winner["nuance"] if winner else None,
            "rounds": [
                {"round": i + 1, "turnout": r["turnout"], "lists": [{k: l[k] for k in ("name", "nuance", "pct")} for l in r["lists"]]}
                for i, r in enumerate(rounds)
            ],
        }
    return out
