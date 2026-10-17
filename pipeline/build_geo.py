"""Commune and département geometry: simplified boundaries, centre points and adjacency."""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline import fetch

LAMBERT93 = 2154
WGS84 = 4326
COMMUNE_TOLERANCE_M = 40  # coverage simplification keeps shared borders identical between neighbours
DEPARTEMENT_TOLERANCE_M = 1500
MIN_SHARED_BORDER_M = 1.0  # neighbours share a line, not just a point (DATA.md §1)


def communes(codes: set[str]) -> gpd.GeoDataFrame:
    """Full-resolution commune polygons in Lambert-93, indexed by code_insee."""
    g = gpd.read_parquet(fetch.path("admin_express_communes"), columns=["code_insee", "geometrie"])
    g = g[g.code_insee.isin(codes)].set_index("code_insee").sort_index()
    missing = codes - set(g.index)
    if missing:
        raise RuntimeError(f"No boundary for {len(missing)} communes: {sorted(missing)[:10]}")
    return g.to_crs(LAMBERT93)


def centres(g: gpd.GeoDataFrame) -> pd.DataFrame:
    """lat/lon of the town hall (chef-lieu), or a point guaranteed inside the polygon if there is none."""
    ch = gpd.read_parquet(
        fetch.path("admin_express_chefs_lieux"), columns=["code_insee_de_la_commune", "geometrie"]
    )
    ch = ch.drop_duplicates("code_insee_de_la_commune").set_index("code_insee_de_la_commune").to_crs(LAMBERT93)
    pts = ch.geometry.reindex(g.index)
    fallback = g.geometry.representative_point()
    pts = pts.where(pts.notna(), fallback)
    pts = gpd.GeoSeries(pts, crs=LAMBERT93).to_crs(WGS84)
    return pd.DataFrame({"lat": pts.y.round(5), "lon": pts.x.round(5)}, index=g.index)


def adjacency(g: gpd.GeoDataFrame, targets: set[str]) -> dict[str, list[str]]:
    """Neighbours (sharing a border line) of each target commune; may include other départements."""
    left = g[g.index.isin(targets)]
    pairs = gpd.sjoin(left, g, predicate="intersects", how="inner")
    pairs = pairs[pairs.index != pairs.code_insee_right]
    a = left.geometry.loc[pairs.index].values
    b = g.geometry.loc[pairs.code_insee_right].values
    shared = shapely.length(shapely.intersection(shapely.boundary(a), shapely.boundary(b)))
    pairs = pairs[shared >= MIN_SHARED_BORDER_M]
    out = pairs.groupby(level=0).code_insee_right.apply(lambda s: sorted(s)).to_dict()
    return {code: out.get(code, []) for code in sorted(targets)}


def simplified(g: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """Display geometry in WGS84; simplified as one coverage so borders stay gap-free."""
    geoms = shapely.coverage_simplify(g.geometry.values, COMMUNE_TOLERANCE_M)
    return gpd.GeoSeries(geoms, index=g.index, crs=LAMBERT93).to_crs(WGS84)


def departements(dep_codes: set[str]) -> gpd.GeoDataFrame:
    d = gpd.read_parquet(
        fetch.path("admin_express_departements"), columns=["code_insee", "nom_officiel", "geometrie"]
    )
    d = d[d.code_insee.isin(dep_codes)].set_index("code_insee").sort_index().to_crs(LAMBERT93)
    d = d.rename_geometry("geometry").rename(columns={"nom_officiel": "name"})
    d["geometry"] = shapely.coverage_simplify(d.geometry.values, DEPARTEMENT_TOLERANCE_M)
    return d.to_crs(WGS84)


def distances_km(a: pd.DataFrame, b: pd.DataFrame) -> np.ndarray:
    """Haversine distance matrix (km) between two sets of lat/lon points."""
    la1, lo1 = np.radians(a.lat.values)[:, None], np.radians(a.lon.values)[:, None]
    la2, lo2 = np.radians(b.lat.values)[None, :], np.radians(b.lon.values)[None, :]
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(h))
