"""Read every statistical source and join it per commune (index = code_insee, frozen COG)."""

import zipfile

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pipeline import cog, fetch
from pipeline.config import (
    BPE_BAKERY,
    BPE_CODES,
    CRIME_INDICATORS,
    CRIME_MAX_UNCERTAINTY,
    CRIME_WITHHELD,
    CRIME_YEAR,
    GROWTH_FROM,
    GROWTH_TO,
    NAF_BAKERY,
    NAF_BREAD_RETAIL,
    NAF_CAFES,
    NAF_PASTRY,
)

# Age bands published by the census for sex × age at commune level (RP 2023).
AGE_BANDS = [
    ("Y_LT15", "0–14"),
    ("Y15T24", "15–24"),
    ("Y25T39", "25–39"),
    ("Y40T54", "40–54"),
    ("Y55T64", "55–64"),
    ("Y65T79", "65–79"),
    ("Y_GE80", "80+"),
]

# NAF division (2 digits) -> sector shown on the card and commune page.
SECTORS = {
    "industry": range(5, 40),  # B–E: extraction, manufacturing, energy, water
    "construction": range(41, 44),  # F
    "retail_food": range(45, 48),  # G: trade
    "transport": range(49, 54),  # H
    "hospitality": range(55, 57),  # I: hotels, cafés, restaurants
    "business_services": range(58, 83),  # J–N
    "health_social": range(86, 89),  # Q
}


def _melodi(source: str, keep: dict, geo_objects=("COM",), usecols=None) -> pd.DataFrame:
    """Read an Insee Melodi CSV (long format) keeping rows whose columns equal the given values."""
    with zipfile.ZipFile(fetch.path(source)) as z:
        name = next(n for n in z.namelist() if n.endswith("_data.csv"))
        parts = []
        reader = pd.read_csv(z.open(name), sep=";", dtype=str, usecols=usecols, chunksize=1_000_000)
        for chunk in reader:
            mask = chunk.GEO_OBJECT.isin(geo_objects)
            for col, val in keep.items():
                mask &= chunk[col].isin(val if isinstance(val, (list, tuple, set)) else [val])
            parts.append(chunk[mask])
    df = pd.concat(parts, ignore_index=True)
    df["OBS_VALUE"] = pd.to_numeric(df.OBS_VALUE, errors="coerce")
    return df


def population(codes: set[str]) -> pd.DataFrame:
    df = _melodi("populations", {"POPREF_MEASURE": "PMUN"})
    s = df.set_index("GEO").OBS_VALUE.rename("pop")
    return cog.align(s.to_frame(), codes, "populations", additive=True)


def history(codes: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Census population per year (wide), growth rate, and housing shares for the latest census."""
    df = _melodi("rp_history", {"RP_MEASURE": ["POP", "DWELLINGS"]})
    pop = df[df.RP_MEASURE == "POP"].pivot_table(index="GEO", columns="TIME_PERIOD", values="OBS_VALUE")
    pop = cog.align(pop, codes, "rp_history", additive=True)

    years = (pop[str(GROWTH_TO)] / pop[str(GROWTH_FROM)]).where(pop[str(GROWTH_FROM)] > 0)
    growth = ((years ** (1 / (GROWTH_TO - GROWTH_FROM)) - 1) * 100).rename("growth")

    dw = df[(df.RP_MEASURE == "DWELLINGS") & (df.TIME_PERIOD == str(GROWTH_TO))]
    dw = dw.pivot_table(index="GEO", columns="OCS", values="OBS_VALUE")
    dw = cog.align(dw, codes, "rp_history", additive=True)
    housing = pd.DataFrame(
        {
            "dwellings": dw["_T"],
            "second_homes_pct": 100 * dw["DW_SEC_DW_OCC"] / dw["_T"],
            "vacant_pct": 100 * dw["DW_VAC"] / dw["_T"],
        }
    ).where(dw["_T"] > 0)
    return pop, pd.concat([growth, housing], axis=1)


def age_sex(codes: set[str]) -> pd.DataFrame:
    """Columns m_<band>, f_<band> (people) for the latest census."""
    df = _melodi(
        "rp_age_sex",
        {"TIME_PERIOD": str(GROWTH_TO), "SEX": ["M", "F"], "AGE": [a for a, _ in AGE_BANDS]},
    )
    df["col"] = df.SEX.str.lower() + "_" + df.AGE
    wide = df.pivot_table(index="GEO", columns="col", values="OBS_VALUE")
    return cog.align(wide, codes, "rp_age_sex", additive=True)


def income() -> tuple[pd.DataFrame, dict]:
    """Median standard of living and poverty rate (commune), plus département and France medians."""
    df = _melodi(
        "filosofi",
        {"FILOSOFI_MEASURE": ["MED_SL", "PR_MD60"]},
        geo_objects=("COM", "DEP", "FRANCE"),
    )
    wide = df.pivot_table(index=["GEO_OBJECT", "GEO"], columns="FILOSOFI_MEASURE", values="OBS_VALUE")
    wide = wide.rename(columns={"MED_SL": "income", "PR_MD60": "poverty_pct"})
    com = wide.loc["COM"]
    ref = {
        "dep": wide.loc["DEP"].income.dropna().to_dict(),
        "france": float(wide.loc["FRANCE"].income.dropna().iloc[0]),
    }
    return com, ref


def amenities(codes: set[str]) -> pd.DataFrame:
    wanted = {BPE_BAKERY: "bakeries"} | {c: k for k, cs in BPE_CODES.items() for c in cs}
    df = _melodi("bpe", {"FACILITY_TYPE": list(wanted)})
    df["key"] = df.FACILITY_TYPE.map(wanted)
    wide = df.pivot_table(index="GEO", columns="key", values="OBS_VALUE", aggfunc="sum")
    wide = cog.align(wide, codes, "bpe", additive=True)
    # BPE lists only equipment that exists: a missing count means zero.
    return wide.reindex(index=sorted(codes), columns=["bakeries", *BPE_CODES]).fillna(0).astype(int)


def crime(codes: set[str]) -> pd.DataFrame:
    """Selected recorded offences per 1,000 inhabitants (see CRIME_* in config).

    Built from counts so that Paris, Lyon and Marseille (published per arrondissement) sum into one
    commune. Withheld counts (1 to 4 offences) are taken at their midpoint; the value is dropped when
    those estimates make it too uncertain.
    """
    t = pq.read_table(
        fetch.path("ssmsi"),
        columns=["CODGEO_2026", "annee", "indicateur", "nombre", "est_diffuse", "insee_pop"],
        filters=[("annee", "=", CRIME_YEAR)],
    ).to_pandas()
    t = t[t.indicateur.astype(str).isin(CRIME_INDICATORS)]
    withheld = t.est_diffuse != "diff"
    lo, hi = CRIME_WITHHELD
    per_code = pd.DataFrame(
        {
            "offences": t.nombre.where(~withheld, (lo + hi) / 2),
            "withheld": withheld.astype(int),
            "code": t.CODGEO_2026,
        }
    ).groupby("code")[["offences", "withheld"]].sum()
    per_code["insee_pop"] = t.groupby("CODGEO_2026").insee_pop.first()
    per_code = cog.align(per_code, codes, "ssmsi", additive=True)

    pop = per_code.insee_pop.where(per_code.insee_pop > 0)
    rate = 1000 * per_code.offences / pop
    uncertainty = 1000 * per_code.withheld * (hi - lo) / pop
    return pd.DataFrame({"crime": rate.where(uncertainty <= CRIME_MAX_UNCERTAINTY)})


def businesses(codes: set[str]) -> pd.DataFrame:
    """Active SIRENE establishments per commune: total, by sector, bakery-related and cafés."""
    t = pq.read_table(
        fetch.path("sirene"),
        columns=[
            "codeCommuneEtablissement",
            "activitePrincipaleEtablissement",
            "nomenclatureActivitePrincipaleEtablissement",
            "etatAdministratifEtablissement",
        ],
        filters=pc.field("etatAdministratifEtablissement") == "A",
    )
    df = t.drop_columns("etatAdministratifEtablissement").to_pandas()
    df.columns = ["code", "naf", "nomenclature"]
    df = df[df.code.notna()]
    # Old establishments may still carry a pre-2008 activity code: count them, but only as "other".
    naf = df.naf.where(df.nomenclature == "NAFRev2", "").fillna("")
    div = pd.to_numeric(naf.str[:2], errors="coerce")
    df["sector"] = "other"
    for sector, rng in SECTORS.items():
        df.loc[div.isin(rng), "sector"] = sector
    out = pd.crosstab(df.code, df.sector).add_prefix("est_")
    out["est_total"] = out.sum(axis=1)
    for col, code in [
        ("sirene_bakeries", NAF_BAKERY),
        ("sirene_pastry", NAF_PASTRY),
        ("sirene_bread_retail", NAF_BREAD_RETAIL),
        ("cafes", NAF_CAFES),
    ]:
        out[col] = df[naf == code].groupby("code").size()
    out = cog.align(out.fillna(0), codes, "sirene", additive=True)
    return out.reindex(sorted(codes)).fillna(0).astype(int)


def build(communes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """One row per commune in scope with every indicator; plus reference values for comparisons."""
    codes = set(communes.code_insee)
    print("  population, census history, age pyramid …", flush=True)
    pop = population(codes)
    hist, growth_housing = history(codes)
    ages = age_sex(codes)
    print("  income (Filosofi) …", flush=True)
    inc, income_ref = income()
    inc = cog.align(inc, codes, "filosofi", additive=False)
    print("  amenities (BPE) …", flush=True)
    bpe = amenities(codes)
    print("  crime (SSMSI) …", flush=True)
    cri = crime(codes)
    print("  businesses (SIRENE) …", flush=True)
    biz = businesses(codes)

    df = communes.set_index("code_insee")
    df = df.join([pop, growth_housing, inc, bpe, cri, biz, ages])
    df["pop"] = df["pop"].fillna(0).astype(int)
    hist.columns = [f"pop_{c}" for c in hist.columns]
    df = df.join(hist)
    return df, {"income": income_ref}
