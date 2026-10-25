"""Write public/data/* (docs/DATA.md §4). Only aggregates per commune are ever written here."""

import json
import math
import shutil
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline import build_geo
from pipeline.build_local import SIZE_GROUPS
from pipeline.build_stats import AGE_BANDS
from pipeline.config import (
    BPE_CODES,
    COG_YEAR,
    CRIME_YEAR,
    CRITERIA,
    GROWTH_FROM,
    GROWTH_TO,
    HISTORY_FROM,
    OUT,
    SOURCES,
)

NEARBY_KM = 10
NEARBY_ROWS = 8


def _clean(x):
    """JSON-safe value: NaN -> None, numpy scalars -> Python, floats rounded to 5 decimals."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) else round(float(x), 5)
    return x


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), ensure_ascii=False, separators=(",", ":")))


def _round(s: pd.Series, digits: int) -> list:
    return [None if pd.isna(v) else (int(round(v, digits)) if digits <= 0 else round(float(v), digits)) for v in s]


def meta(manifest: dict, deps: list[str], checks: dict) -> dict:
    sources = []
    for sid, spec in SOURCES.items():
        m = manifest.get(sid, {})
        sources.append(
            {
                "id": sid,
                "name": spec["name"],
                "producer": spec["producer"],
                "vintage": spec["vintage"],
                "licence": spec["licence"],
                "url": spec["page"],
                "fetched": m.get("fetched"),
                "published": m.get("published"),
            }
        )
    return {
        "cog_year": COG_YEAR,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "departements": deps,
        "percentiles": "France métropolitaine et Corse",
        "years": {"census": GROWTH_TO, "growth_from": GROWTH_FROM, "crime": CRIME_YEAR, "income": 2023, "bpe": 2025, "election": 2026},
        "checks": checks,
        "sources": sources,
    }


def index(df: pd.DataFrame, centres: pd.DataFrame, raw: pd.DataFrame, pct: pd.DataFrame) -> dict:
    """communes-index.json: one entry per commune, columnar arrays with short keys."""
    # Kept lean (DATA.md §4): ~100 m positions, income to the nearest 10 €, criteria without any data omitted.
    digits = {"per_bakery": 0, "income": -1, "growth": 2, "crime": 1, "sell_soon": 0}
    present = [c for c in CRITERIA if raw[c].notna().any()]
    return {
        "code": list(df.index),
        "name": list(df["name"]),
        "dep": list(df["dep"]),
        "lat": _round(centres.lat, 3),
        "lon": _round(centres.lon, 3),
        "pop": _round(df["pop"], 0),
        "bakeries": _round(df["bakeries"], 0),
        "v": {c: _round(raw[c], digits[c]) for c in present},
        "pct": {c: _round(pct[c], 0) for c in present},
    }


def commune_page(code, row, all_rows, centres, dep_names, income_ref, raw, pct, neighbours, employers, politics) -> dict:
    hist = [[int(c[4:]), int(row[c])] for c in all_rows.columns if c.startswith("pop_") and pd.notna(row[c])]
    bands = [label for _, label in AGE_BANDS]
    here = centres.loc[[code]]
    dist = build_geo.distances_km(here, centres)[0]
    near = pd.DataFrame({"km": dist}, index=centres.index)
    near = near[near.km <= NEARBY_KM].join(all_rows[["name", "pop", "bakeries"]]).sort_values("km")
    return {
        "code": code,
        "name": row["name"],
        "dep": row["dep"],
        "dep_name": dep_names.get(row["dep"]),
        "lat": round(float(centres.lat[code]), 5),
        "lon": round(float(centres.lon[code]), 5),
        "pop": int(row["pop"]),
        "bakeries": int(row["bakeries"]),
        "criteria": {c: {"v": raw.at[code, c], "pct": pct.at[code, c]} for c in CRITERIA},
        "history": hist,
        "pyramid": {
            "year": GROWTH_TO,
            "bands": bands,
            "m": [row.get(f"m_{a}") for a, _ in AGE_BANDS],
            "f": [row.get(f"f_{a}") for a, _ in AGE_BANDS],
        },
        "housing": {
            "year": GROWTH_TO,
            "dwellings": row["dwellings"],
            "second_homes_pct": round(row["second_homes_pct"], 1) if pd.notna(row["second_homes_pct"]) else None,
            "vacant_pct": round(row["vacant_pct"], 1) if pd.notna(row["vacant_pct"]) else None,
        },
        "income": {
            "median": row["income"],
            "poverty_pct": row["poverty_pct"],
            "dep_median": income_ref["dep"].get(row["dep"]),
            "france_median": income_ref["france"],
        },
        "amenities": {k: int(row[k]) for k in ["bakeries", *BPE_CODES]},
        "businesses": {
            "total": int(row["est_total"]),
            "sectors": {
                k[4:]: int(row[k])
                for k in all_rows.columns
                if k.startswith("est_") and k != "est_total"
            },
            "sirene_bakeries": int(row["sirene_bakeries"]),
            "sirene_pastry": int(row["sirene_pastry"]),
            "cafes": int(row["cafes"]),
            "by_size": {k: int(row[f"size_{k}"]) for k in SIZE_GROUPS},
            "main_employers": employers.get(code, []),
        },
        "politics": politics.get(code),
        "bakery_history": {
            "since": int(HISTORY_FROM[:4]),
            "takeovers": int(row["hist_takeovers"]),
            "openings": int(row["hist_openings"]),
            "closures": int(row["hist_closures"]),
        },
        "competition": {
            "km": NEARBY_KM,
            "communes": int(len(near)),
            "bakeries": int(near.bakeries.sum()),
            "communes_without_bakery": int((near.bakeries == 0).sum()),
        },
        "nearby": [
            {"code": c, "name": r["name"], "km": round(r.km, 1), "pop": int(r["pop"]), "bakeries": int(r.bakeries)}
            for c, r in near.head(NEARBY_ROWS).iterrows()
        ],
        "neighbours": neighbours,
    }


def write_all(
    df, centres, raw, pct, display_geom, deps_gdf, adjacency, income_ref, fonds, employers, politics, manifest, deps,
    checks,
):
    """Replace public/data with the outputs for the given départements."""
    if OUT.exists():
        shutil.rmtree(OUT)
    scope = df[df.dep.isin(deps)]
    dep_names = deps_gdf["name"].to_dict()

    _write(OUT / "meta.json", meta(manifest, deps, checks))
    _write(OUT / "fonds.json", fonds)

    counts = df.groupby("dep").size()
    d = deps_gdf.assign(code=deps_gdf.index, n_communes=counts.reindex(deps_gdf.index).fillna(0).astype(int))
    d[["code", "name", "n_communes", "geometry"]].to_file(
        OUT / "departements.geojson", driver="GeoJSON", COORDINATE_PRECISION=4
    )

    _write(OUT / "communes-index.json", index(scope, centres.loc[scope.index], raw.loc[scope.index], pct.loc[scope.index]))

    for dep in deps:
        codes = scope.index[scope.dep == dep]
        g = gpd.GeoDataFrame({"code": codes}, geometry=display_geom.loc[codes].values, crs=display_geom.crs)
        (OUT / "geo").mkdir(parents=True, exist_ok=True)
        g.to_file(OUT / "geo" / f"{dep}.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
        _write(OUT / "adj" / f"{dep}.json", {c: adjacency[c] for c in codes})

    for code, row in scope.iterrows():
        page = commune_page(
            code, row, df, centres, dep_names, income_ref, raw, pct, adjacency.get(code, []), employers, politics
        )
        _write(OUT / "commune" / f"{code}.json", page)
