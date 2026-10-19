"""Build public/data/ from French open data.

    uv run python -m pipeline.run --dep 44        # one or more départements
    uv run python -m pipeline.run --all           # every département in scope
    uv run python -m pipeline.run --dep 44 --refresh   # re-download every source first

Statistics and percentiles are always computed over all of metropolitan France + Corsica, so a
commune's score does not depend on which départements are exported.
"""

import argparse
import time
import zipfile

import pandas as pd

from pipeline import build_geo, build_local, build_market, build_stats, cog, export, fetch, score

MAX_POP_GAP = 0.005  # DATA.md §5: population within 0.5 % of the official total
MAX_BAKERY_GAP = 0.15  # DATA.md §5: BPE vs SIRENE bakery count, national


def official_population(deps: list[str]) -> int:
    with zipfile.ZipFile(fetch.path("populations")) as z:
        name = next(n for n in z.namelist() if n.endswith("_data.csv"))
        p = pd.read_csv(z.open(name), sep=";", dtype=str)
    p = p[(p.GEO_OBJECT == "DEP") & (p.POPREF_MEASURE == "PMUN") & p.GEO.isin(deps)]
    return int(pd.to_numeric(p.OBS_VALUE).sum())


def quality_checks(df: pd.DataFrame, deps: list[str]) -> dict:
    scope = df[df.dep.isin(deps)]
    if scope.index.duplicated().any():
        raise AssertionError("duplicate commune codes")

    official = official_population(deps)
    pop_gap = abs(scope["pop"].sum() - official) / official
    if pop_gap > MAX_POP_GAP:
        raise AssertionError(f"population {scope['pop'].sum()} vs official {official} ({pop_gap:.2%})")

    bpe = int(df.bakeries.sum())
    sirene = int((df.sirene_bakeries + df.sirene_pastry).sum())
    bakery_gap = abs(bpe - sirene) / bpe
    if bakery_gap > MAX_BAKERY_GAP:
        raise AssertionError(f"bakeries BPE {bpe} vs SIRENE 10.71C+D {sirene} ({bakery_gap:.1%})")
    by_dep = df.groupby("dep")[["bakeries", "sirene_bakeries", "sirene_pastry"]].sum()
    by_dep["gap"] = (by_dep.sirene_bakeries + by_dep.sirene_pastry) / by_dep.bakeries - 1
    worst = by_dep.gap.abs().sort_values(ascending=False).head(5)
    print("  bakery gap SIRENE vs BPE, worst départements:", {k: f"{v:+.0%}" for k, v in worst.items()})

    return {
        "population": {"total": int(scope["pop"].sum()), "official": official, "gap": round(pop_gap, 5)},
        "bakeries": {"bpe": bpe, "sirene_10_71_c_d": sirene, "gap": round(bakery_gap, 4)},
        "missing_share": {
            c: round(float(scope[c].isna().mean()), 3) for c in ["income", "growth", "crime"]
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dep", nargs="+", help="département codes, e.g. 44 2A")
    group.add_argument("--all", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-download every source")
    args = ap.parse_args(argv)
    t0 = time.time()

    print("1/5 fetch")
    manifest = fetch.fetch_all(refresh=args.refresh)

    print("2/5 statistics")
    communes = cog.communes()
    deps = sorted(communes.dep.unique()) if args.all else sorted(args.dep)
    unknown = set(deps) - set(communes.dep)
    if unknown:
        raise SystemExit(f"Unknown département(s): {sorted(unknown)}")
    df, refs = build_stats.build(communes)
    print("  bakery history (SIRENE) and business prices (BODACC) …", flush=True)
    df = df.join(build_market.bakery_history(set(df.index)))
    fonds = build_market.fonds_prices(set(communes.dep))
    print("  business sizes, main employers, mayors and 2026 election …", flush=True)
    sizes, employers = build_local.businesses_by_size(set(df.index))
    df = df.join(sizes)
    politics = build_local.politics(set(df.index))

    print("3/5 scores")
    raw = score.criteria(df)
    pct = score.percentiles(raw, df)

    print("4/5 geometry")
    g = build_geo.communes(set(df.index))
    centres = build_geo.centres(g)
    targets = set(df.index[df.dep.isin(deps)])
    adjacency = build_geo.adjacency(g, targets)
    display = build_geo.simplified(g)
    deps_gdf = build_geo.departements(set(communes.dep))

    print("5/5 checks and export")
    checks = quality_checks(df, deps)
    export.write_all(
        df, centres, raw, pct, display, deps_gdf, adjacency, refs["income"], fonds, employers, politics, manifest, deps, checks
    )
    print(f"done in {time.time() - t0:.0f}s: {len(targets)} communes in {len(deps)} département(s) -> public/data/")
    print(f"  checks: {checks}")


if __name__ == "__main__":
    main()
