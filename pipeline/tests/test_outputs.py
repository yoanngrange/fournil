"""Checks on the files written to public/data by `python -m pipeline.run` (DATA.md §5).

Run the pipeline first, then: uv run pytest
Update the Clisson snapshot after a deliberate source change: UPDATE_SNAPSHOT=1 uv run pytest
"""

import json
import os
import re
from pathlib import Path

import pytest

from pipeline.config import CRITERIA, OUT

SNAPSHOT = Path(__file__).parent / "snapshots" / "44043.json"


def load(rel):
    return json.loads((OUT / rel).read_text())


@pytest.fixture(scope="module")
def meta():
    if not (OUT / "meta.json").exists():
        pytest.skip("public/data not built: run `uv run python -m pipeline.run --dep 44` first")
    return load("meta.json")


@pytest.fixture(scope="module")
def index(meta):
    return load("communes-index.json")


def test_meta_lists_every_source_with_vintage(meta):
    assert meta["cog_year"] == 2026
    assert len(meta["sources"]) >= 10
    for s in meta["sources"]:
        assert s["name"] and s["vintage"] and s["licence"] and s["url"].startswith("https://")


def test_index_one_row_per_commune(index, meta):
    codes = index["code"]
    assert len(codes) == len(set(codes)), "duplicate commune codes"
    assert all(len(c) == 5 for c in codes)
    assert {c[:2] for c in codes} <= set(meta["departements"])
    n = len(codes)
    for key in ["name", "dep", "lat", "lon", "pop", "bakeries"]:
        assert len(index[key]) == n
    for c in index["v"]:
        assert len(index["v"][c]) == n and len(index["pct"][c]) == n


def test_index_row_count_for_loire_atlantique(index, meta):
    if meta["departements"] == ["44"]:
        assert len(index["code"]) == 207  # communes of 44 in COG 2026


def test_value_ranges(index):
    assert all(p >= 0 for p in index["pop"])
    assert all(b >= 0 for b in index["bakeries"])
    assert all(41 < lat < 52 and -6 < lon < 10 for lat, lon in zip(index["lat"], index["lon"]))
    for c in index["pct"]:
        assert all(p is None or 0 <= p <= 1000 for p in index["pct"][c])
    assert all(v is None or 5_000 < v < 80_000 for v in index["v"]["income"])
    assert all(v is None or -20 < v < 25 for v in index["v"]["growth"])
    assert all(v is None or v >= 0 for v in index["v"]["crime"])


def test_missing_values_stay_missing(index):
    """Missing data is null, never 0, and its percentile is null too."""
    for c in index["v"]:
        for v, p, b, pop in zip(index["v"][c], index["pct"][c], index["bakeries"], index["pop"]):
            if c == "per_bakery" and b == 0 and pop > 0:
                assert v is None and p is not None  # no bakery: no ratio, but ranked (boost)
            else:
                assert (v is None) == (p is None)


def test_no_bakery_ranks_above_same_size_with_one(index):
    """SPEC §4: without a bakery, a commune ranks above one of similar size that has one."""
    rows = list(zip(index["pop"], index["bakeries"], index["pct"]["per_bakery"]))
    none = [(pop, p) for pop, b, p in rows if b == 0 and pop > 1000]
    one = [(pop, p) for pop, b, p in rows if b == 1]
    for pop, p in none:
        similar = [q for pop1, q in one if abs(pop1 - pop) / pop < 0.1]
        if similar:
            assert p > max(similar)


def test_geometry_and_adjacency(index, meta):
    codes = set(index["code"])
    for dep in meta["departements"]:
        geo = load(f"geo/{dep}.geojson")
        geo_codes = {f["properties"]["code"] for f in geo["features"]}
        assert geo_codes == {c for c in codes if c.startswith(dep)}
        adj = load(f"adj/{dep}.json")
        assert set(adj) == geo_codes
        for code, nbs in adj.items():
            assert code not in nbs
            for nb in nbs:
                if nb in adj:
                    assert code in adj[nb], f"adjacency not symmetric: {code} / {nb}"
        islands = [c for c, nbs in adj.items() if not nbs]
        assert len(islands) <= 8, f"communes without neighbours: {islands}"  # islands (Morbihan has 5)


def test_departements_file(meta):
    d = load("departements.geojson")
    assert len(d["features"]) == 96  # metropolitan France + Corsica


def test_commune_pages_exist(index):
    for code in index["code"]:
        assert (OUT / "commune" / f"{code}.json").exists()


def test_privacy_no_individual_data():
    """CLAUDE.md: only aggregates per commune; never a SIRET, a person or a birth year."""
    siret = re.compile(r"\b\d{14}\b")
    forbidden_keys = re.compile(r'"[^"]*(siret|birth|naissance|dirigeant|director)[^"]*"\s*:')
    for path in OUT.rglob("*.json"):
        text = path.read_text().lower()
        assert not siret.search(text), path
        assert not forbidden_keys.search(text), path


def test_clisson_snapshot(meta):
    """Clisson (44043) values change only when a source changes."""
    if "44" not in meta["departements"]:
        pytest.skip("dep 44 not built")
    page = load("commune/44043.json")
    current = {
        "pop": page["pop"],
        "bakeries": page["bakeries"],
        "criteria": page["criteria"],
        "history": page["history"],
        "income": page["income"],
        "amenities": page["amenities"],
        "neighbours": page["neighbours"],
    }
    if os.environ.get("UPDATE_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1, ensure_ascii=False))
        pytest.skip("snapshot written")
    assert current == json.loads(SNAPSHOT.read_text())


def test_bakery_history_counts(index):
    for code in index["code"]:
        h = load(f"commune/{code}.json")["bakery_history"]
        assert h["since"] == 2016
        assert all(isinstance(h[k], int) and h[k] >= 0 for k in ("takeovers", "openings", "closures"))
    # Casson (44027): the 2020 takeover of its only bakery.
    if (OUT / "commune" / "44027.json").exists():
        assert load("commune/44027.json")["bakery_history"]["takeovers"] >= 1


def test_business_prices_are_aggregates_only(meta):
    fonds = load("fonds.json")
    assert set(fonds) == {"since", "min_sales", "france", "departements"}
    assert fonds["france"]["n"] > 1000
    for stats in [fonds["france"], *fonds["departements"].values()]:
        assert set(stats) == {"n", "median", "q1", "q3"}
        assert stats["n"] >= fonds["min_sales"], "a price shown from too few sales could identify a sale"
        assert 5_000 <= stats["q1"] <= stats["median"] <= stats["q3"] <= 3_000_000


def test_local_context(index):
    for code in index["code"]:
        page = load(f"commune/{code}.json")
        sizes = page["businesses"]["by_size"]
        assert sum(sizes.values()) == page["businesses"]["total"]
        assert len(page["businesses"]["main_employers"]) <= 3
        pol = page["politics"]
        if pol:
            assert set(pol) == {"mayor", "list", "nuance", "rounds"}  # name only: no birth date, no occupation
            for r in pol["rounds"]:
                assert r["turnout"] is None or 0 < r["turnout"] <= 100
    clisson = load("commune/44043.json")
    assert clisson["politics"]["mayor"] and clisson["politics"]["rounds"]
